from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List

from ..adapter.crypto_exchange import CryptoExchangeAbstract, BinanceExchange
from ..adapter.database.crypto_cache import CryptoOhlcvCacheFetcherAbstract, CryptoOhlcvCacheFetcher
from ..adapter.database.cryto_trade import CryptoTradeHistory, CryptoTradeHistoryAbstract
from ..adapter.database.session import SessionAbstract, SqlAlchemySession
from ..model import CryptoHistoryFrame, CryptoOhlcvHistory, CryptoOrderSide, CryptoOrderType
from ..logger import logger
from ..utils.time import time_length_in_frame, round_datetime, timeframe_to_second

@dataclass
class ModuleDependency:
    session: SessionAbstract
    cache: CryptoOhlcvCacheFetcherAbstract
    trade_log: CryptoTradeHistoryAbstract
    exchange: CryptoExchangeAbstract

default_session = SqlAlchemySession()
default_dependency = ModuleDependency(
    session = default_session,
    cache = CryptoOhlcvCacheFetcher(default_session),
    trade_log = CryptoTradeHistory(default_session),
    exchange = BinanceExchange()
)

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
    def __init__(self, dependency: ModuleDependency = default_dependency):
        self.dependency = dependency

    def create_order(self, pair: str, type: CryptoOrderType, side: CryptoOrderSide, amount: float, reason: str, price: float = None):
        with self.dependency.session:
            order = self.dependency.exchange.create_order(pair, type, side, amount, price)
            self.dependency.trade_log.add(order, reason)
    
    def get_ohlcv_history(self, pair: str, frame: CryptoHistoryFrame, start: datetime, end: datetime = datetime.now()) -> CryptoOhlcvHistory:
        with self.dependency.session: 
            expected_data_length = time_length_in_frame(start, end, frame)
            nomolized_start = round_datetime(start, frame)
            nomolized_end = round_datetime(end, frame)
            
            cache_result = self.dependency.cache.range_query(pair, frame, nomolized_start, nomolized_end)
            logger.debug(f'Found {len(cache_result.data)} records locally')
            if len(cache_result.data) == expected_data_length:
                logger.debug('local database found all required data, return directly.')
                return cache_result
            
            if len(cache_result.data) == 0:
                remote_result = self.dependency.exchange.fetch_ohlcv(pair, frame, nomolized_start, nomolized_end)
                assert expected_data_length == len(remote_result.data)
                self.dependency.cache.add(remote_result)
                self.dependency.session.commit()
                return remote_result
            local_timerange = list(map(lambda item: item.timestamp, cache_result.data))
            result_data = cache_result.data
            miss_time_ranges = get_missed_time_ranges(local_timerange, nomolized_start, nomolized_end, frame)
            logger.debug(f'missed_time_ranges: {miss_time_ranges}')
            for time_range in miss_time_ranges:
                remote_data = self.dependency.exchange.fetch_ohlcv(pair, frame, time_range[0], time_range[1])
                self.dependency.cache.add(remote_data)
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