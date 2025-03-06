import abc
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List

from ..model import OhlcvHistory, Order, AShareOrder
from ..utils.string import random_id
from ..adapter.exchange.api import ExchangeAPI
from ..adapter.exchange.crypto_exchange import BinanceExchange
from ..adapter.exchange.cn_market_exchange import cn_market as cn_market_adapter
from ..adapter.database.ohlcv_cache import CryptoOhlcvCacheFetcher
from ..adapter.database.cryto_trade import CryptoTradeHistory
from ..adapter.database.kv_store import KeyValueStore
from ..adapter.database.session import SessionAbstract, SqlAlchemySession
from ..adapter.lock import CreateLockFactory, create_db_lock, with_lock
from ..adapter.apis import get_china_holiday
from ..model import CryptoHistoryFrame, CryptoOhlcvHistory, CryptoOrder, OrderSide, OrderType, CnStockHistoryFrame
from ..logger import logger
from ..utils.time import time_length_in_frame, round_datetime_in_period, timeframe_to_second, time_ago_from

@dataclass
class ModuleDependency:
    session: SessionAbstract
    exchange: ExchangeAPI
    lock_factory: CreateLockFactory
    def __init__(self, session: SessionAbstract = None, exchange: ExchangeAPI = None, lock_factory: CreateLockFactory = None):
        self.session = session or SqlAlchemySession()
        self.exchange = exchange or BinanceExchange()
        self.lock_factory = lock_factory or create_db_lock

def get_missed_time_ranges(timerange: List[datetime], start: datetime, end: datetime, frame: CryptoHistoryFrame) -> List[List[datetime]]:
    result = []
    interval = timeframe_to_second(frame)
    rounded_start = round_datetime_in_period(start, frame)
    rounded_end = round_datetime_in_period(end, frame)

    if rounded_start < timerange[0]:
        result.append([rounded_start, timerange[0]])
    
    while len(timerange) > 0:
        while len(timerange) > 1 and (timerange[0] + timedelta(seconds=interval) == timerange[1]):
            timerange.pop(0)
        if len(timerange) > 1:
            result.append([timerange[0] + timedelta(seconds=interval), timerange[1]])
        elif timerange[0] + timedelta(seconds=interval) < rounded_end:
            result.append([timerange[0] + timedelta(seconds=interval), rounded_end])
        timerange.pop(0)
    
    return result

# 主要负责编排一些事务性的操作
class ExchangeOperationProxy(abc.ABC):
    @abc.abstractmethod
    def is_business_day(self, day: datetime) -> bool:
        pass 

    @abc.abstractmethod
    def get_current_price(self, symbol: str) -> float:
        pass

    @abc.abstractmethod
    def create_order(self, symbol: str, type: OrderType, side: OrderSide, reason: str, amount: float = None, price: float = None, spent: float = None, comment: str = None) -> Order:
        pass
    
    @abc.abstractmethod
    def get_ohlcv_history(self, symbol: str, frame: str, limit: int, start: datetime, end: datetime = datetime.now()) -> OhlcvHistory:
        pass

class CryptoProxy(ExchangeOperationProxy):
    def __init__(self, dependency: ModuleDependency = ModuleDependency()):
        self.dependency = dependency
        self.cache_store = CryptoOhlcvCacheFetcher(dependency.session)
        self.trade_log_store = CryptoTradeHistory(dependency.session)

    def is_business_day(self, _: datetime) -> bool:
        return True

    def get_current_price(self, symbol: str) -> float:
        return self.dependency.exchange.fetch_ticker(symbol).last

    def create_order(self, symbol: str, type: OrderType, side: OrderSide, reason: str, amount: float = None, price: float = None, spent: float = None, comment: str = None) -> CryptoOrder:
        logger.debug(f'createorder: {type} {side} {reason} amount: {amount}, price: {price}, spent: {spent}, comment: {comment}')
        with self.dependency.session:
            order = None
            if type == 'limit' and amount and price:
                order = self.dependency.exchange.create_order(symbol, type, side, amount, price)
            elif type =='market' and amount:
                order = self.dependency.exchange.create_order(symbol, type, side, amount)
            elif type =='market' and spent :
                if side == 'buy':
                    ticker = self.dependency.exchange.fetch_ticker(symbol)
                    amount = spent / ticker.last
                else:
                    amount = spent
                order = self.dependency.exchange.create_order(symbol, type, side, amount)
            else:
                raise Exception(f'Unsupported parameters value: {type}, {side}, {amount}, {price}, {spent}')
            self.trade_log_store.add(order, reason, comment)
            self.dependency.session.commit()
            return order
    
    def get_ohlcv_history(self, symbol: str, frame: CryptoHistoryFrame, start: datetime = None, end: datetime = datetime.now(), limit: int = None) -> CryptoOhlcvHistory:
        logger.debug(f'get_ohlcv_history with {symbol=}, {frame=}, {limit=}, {start=}, {end=}')
        if not limit and not start:
            raise ValueError("Invalid parameters: 'start' must be provided when 'limit' is not set.")

        expected_data_length = limit if limit else time_length_in_frame(start, end, frame)
        nomolized_start = round_datetime_in_period(time_ago_from(limit, frame), frame) if limit else round_datetime_in_period(start, frame)
        nomolized_end = round_datetime_in_period(datetime.now(), frame) if limit else round_datetime_in_period(end, frame)
        def is_cache_satisfy(cache_result: CryptoOhlcvHistory):
            if len(cache_result.data) == expected_data_length:
                logger.debug('local database found all required data, return directly.')
                return True
            return False
        def query_from_cache():
            cache_result = self.cache_store.range_query(symbol, frame, nomolized_start, nomolized_end)
            logger.debug(f'Found {len(cache_result.data)} records locally')
            return cache_result

        with self.dependency.session:
            cache_result = query_from_cache()
            if is_cache_satisfy(cache_result):
                return cache_result
    
        @with_lock(self.dependency.lock_factory, f'lock-{symbol}-{frame}-ohlcv-query', 1, 300, 300)
        def lock_part():
            with self.dependency.session: 
                cache_result = query_from_cache()
                if is_cache_satisfy(cache_result):
                    return cache_result
                
                if len(cache_result.data) == 0:
                    remote_result = self.dependency.exchange.fetch_ohlcv(symbol, frame, nomolized_start, nomolized_end)
                    assert expected_data_length == len(remote_result.data)
                    self.cache_store.add(remote_result)
                    self.dependency.session.commit()
                    return remote_result
                local_timerange = list(map(lambda item: item.timestamp, cache_result.data))
                result_data = cache_result.data
                miss_time_ranges = get_missed_time_ranges(local_timerange, nomolized_start, nomolized_end, frame)
                logger.debug(f'missed_time_ranges: {miss_time_ranges}')
                for time_range in miss_time_ranges:
                    remote_data = self.dependency.exchange.fetch_ohlcv(symbol, frame, time_range[0], time_range[1])
                    self.cache_store.add(remote_data)
                    result_data.extend(remote_data.data)
                self.dependency.session.commit()
                return CryptoOhlcvHistory(
                    symbol = symbol,
                    frame = frame,
                    # TODO Support other exchange
                    exchange = 'binance',
                    data = sorted(result_data, key=lambda item: item.timestamp)
                )
        return lock_part()

class CnExchangeProxy(ExchangeOperationProxy):

    def __init__(self, session: SessionAbstract):
        self.session = session
        self._holiday_cache_by_year = {}

    def is_business_day(self, day: datetime) -> bool:
        if day.weekday() >= 5:
            return False
        this_year = day.strftime('%Y')
        today = day.strftime('%Y-%m-%d')
        if this_year in self._holiday_cache_by_year.keys():
            return today not in self._holiday_cache_by_year.get(this_year)
        with self.session:
            kv_store = KeyValueStore(self.session)
            cache_key = f"{this_year}_china_holiday"
            holiday_list: List[str] | None= kv_store.get(cache_key)
            if holiday_list is None:
                holiday_list = get_china_holiday(this_year)
                kv_store.set(cache_key, holiday_list)
                self.session.commit()
            self._holiday_cache_by_year[this_year] = holiday_list
            return today not in holiday_list
        
    def get_current_price(self, symbol: str) -> float:
        return super().get_current_price(symbol)
    
    def get_ohlcv_history(self, symbol: str, frame: CnStockHistoryFrame, start: datetime = None, end: datetime = datetime.now(), limit: int = None) -> OhlcvHistory[CnStockHistoryFrame]:
        logger.debug(f'get_ohlcv_history with {symbol=}, {frame=}, {limit=}, {start=}, {end=}')
        if not limit and not start:
            raise ValueError("Invalid parameters: 'start' must be provided when 'limit' is not set.")
        if start and not end:
            end = datetime.now()
        if limit:
            end = datetime.now()
            start = end
            while limit > 0:
                start = time_ago_from(1, frame, start)
                if self.is_business_day(start):
                    limit -= 1
            return cn_market_adapter.fetch_ohlcv(symbol, frame, start, end)     
        return cn_market_adapter.fetch_ohlcv(symbol, frame, start, end)
    
    def create_order(self, symbol: str, type: OrderType, side: OrderSide, reason: str, amount: float = None, price: float = None, spent: float = None, comment: str = None) -> Order:
        return AShareOrder(
            id=random_id(10),
            timestamp=datetime.now(),
            symbol=symbol,
            type=type,
            side=side,
            price=price,
            _amount=amount,
            _cost = price * amount,
            fees=[]
        )
    
crypto = CryptoProxy()
cn_market = CnExchangeProxy(SqlAlchemySession())

__all__ = [
    'crypto', 
    'cn_market',
    'CryptoProxy',
    'ExchangeOperationProxy',
    'ModuleDependency'
]