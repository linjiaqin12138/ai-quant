from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List

from ..adapter.crypto_exchange import CryptoExchangeAbstract, BinanceExchange
from ..adapter.database.crypto_cache import CryptoOhlcvCacheFetcher
from ..adapter.database.cryto_trade import CryptoTradeHistory
from ..adapter.database.session import SessionAbstract, SqlAlchemySession
from ..model import CryptoHistoryFrame, CryptoOhlcvHistory, CryptoOrderSide, CryptoOrderType
from ..logger import logger
from ..utils.time import time_length_in_frame, round_datetime, timeframe_to_second

@dataclass
class ModuleDependency:
    session: SessionAbstract
    exchange: CryptoExchangeAbstract

    def __init__(self, session: SessionAbstract = None, exchange: CryptoExchangeAbstract = None):
        self.session = session or SqlAlchemySession()
        self.exchange = exchange or BinanceExchange()

def get_missed_time_ranges(timerange: List[datetime], start: datetime, end: datetime, frame: CryptoHistoryFrame) -> List[List[datetime]]:
    result = []
    interval = timeframe_to_second(frame)
    rounded_start = round_datetime(start, frame)
    rounded_end = round_datetime(end, frame)

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

class CryptoOperationModule:
    def __init__(self, dependency: ModuleDependency = ModuleDependency()):
        self.dependency = dependency
        self.cache_store = CryptoOhlcvCacheFetcher(dependency.session)
        self.trade_log_store = CryptoTradeHistory(dependency.session)

    def create_order(self, pair: str, type: CryptoOrderType, side: CryptoOrderSide, reason: str, amount: float = None, price: float = None, spent: float = None):
        logger.debug(f'createorder: {type} {side} {reason} amount: {amount}, price: {price}, spent: {spent}')
        with self.dependency.session:
            order = None
            if type == 'limit' and amount and price:
                order = self.dependency.exchange.create_order(pair, type, side, amount, price)
            elif type =='market' and amount:
                order = self.dependency.exchange.create_order(pair, type, side, amount)
            elif type =='market' and spent :
                if side == 'buy':
                    ticker = self.dependency.exchange.fetch_ticker(pair)
                    amount = spent / ticker.last
                else:
                    amount = spent
                order = self.dependency.exchange.create_order(pair, type, side, amount)
            else:
                raise Exception(f'Unsupported parameters value: {type}, {side}, {amount}, {price}, {spent}')
            self.trade_log_store.add(order, reason)
            return order
    
    def get_ohlcv_history(self, pair: str, frame: CryptoHistoryFrame, start: datetime, end: datetime = datetime.now()) -> CryptoOhlcvHistory:
        logger.debug(f'get_ohlcv_history with pair: {pair}, frame: {frame}, start: {start}, end: {end}')
        with self.dependency.session: 
            expected_data_length = time_length_in_frame(start, end, frame)
            nomolized_start = round_datetime(start, frame)
            nomolized_end = round_datetime(end, frame)
            
            cache_result = self.cache_store.range_query(pair, frame, nomolized_start, nomolized_end)
            logger.debug(f'Found {len(cache_result.data)} records locally')
            if len(cache_result.data) == expected_data_length:
                logger.debug('local database found all required data, return directly.')
                return cache_result
            
            if len(cache_result.data) == 0:
                remote_result = self.dependency.exchange.fetch_ohlcv(pair, frame, nomolized_start, nomolized_end)
                assert expected_data_length == len(remote_result.data)
                self.cache_store.add(remote_result)
                self.dependency.session.commit()
                return remote_result
            local_timerange = list(map(lambda item: item.timestamp, cache_result.data))
            result_data = cache_result.data
            miss_time_ranges = get_missed_time_ranges(local_timerange, nomolized_start, nomolized_end, frame)
            logger.debug(f'missed_time_ranges: {miss_time_ranges}')
            for time_range in miss_time_ranges:
                remote_data = self.dependency.exchange.fetch_ohlcv(pair, frame, time_range[0], time_range[1])
                self.cache_store.add(remote_data)
                result_data.extend(remote_data.data)
            self.dependency.session.commit()
            return CryptoOhlcvHistory(
                pair = pair,
                frame = frame,
                # TODO Support other exchange
                exchange = 'binance',
                data = sorted(result_data, key=lambda item: item.timestamp)
            )

crypto = CryptoOperationModule()