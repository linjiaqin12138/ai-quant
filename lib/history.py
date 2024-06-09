import abc
from typing import Literal, Optional, Union, List, Any
from dataclasses import dataclass
from datetime import datetime, UTC, timedelta

from lib.utils.logger import logger
from sqlalchemy import and_

from .dao.tables import OhlcvCache1H, OhlcvCache1D, OhlcvCacheBase
from .dao.session import Session
from .utils.time import dt_to_float, curr_ts, unify_dt
from .dao.exchange import fetch_ohlcv

@dataclass(frozen=True)
class Ohlcv:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    # def __str__(self):
    #     return ''

PeriodLiteral = Literal['1h', '1d']

def period_to_table_class(period: PeriodLiteral): 
    if period == '1h':
        return OhlcvCache1H
    if period == '1d':
        return OhlcvCache1D

def period_to_timerange_in_second(period: PeriodLiteral) -> int:
    if period == '1h':
        return 3600
    if period == '1d':
        return 86400

def ohlcv_from_backend(item: List[Any]) -> Ohlcv:
    return Ohlcv(timestamp=datetime.fromtimestamp(item[0] / 1000), open = item[1], high = item[2], low = item[3], close = item[4], volume = item[5])

def print_timestamps(input: List[datetime]):
    for dt in input:
        print(dt)

def get_missed_time_ranges(timerange: List[datetime], start: datetime, end: datetime, interval: int) -> List[List[datetime]]:
    result = []
    if start < timerange[0]:
        result.append([start, timerange[0]])
    
    while len(timerange) > 0:
        while len(timerange) > 1 and (timerange[0] + timedelta(seconds=interval) == timerange[1]):
            timerange.pop(0)
        if len(timerange) > 1:
            result.append([timerange[0] + timedelta(seconds=interval), timerange[1]])
        elif timerange[0] < end:
            result.append([timerange[0] + timedelta(seconds=interval), end])
        timerange.pop(0)
    
    return result


class OhlcvCacheFetcherAbstract(abc.ABC):
    def __init__(self, pair: str, period: str):
        self.pair = pair
        self.period = period

    @abc.abstractclassmethod
    def range_query(self, start: datetime, end: datetime) -> List[Ohlcv]:
        raise NotImplementedError
    @abc.abstractclassmethod
    def get(self, time: datetime) -> Optional[Ohlcv]:
        raise NotImplementedError
    @abc.abstractclassmethod
    def add(self, lines: Union[Ohlcv, List[Ohlcv]]):
        raise NotImplementedError

class OhlcvRemoteFetcherAbstract(abc.ABC):
    def __init__(self, pair: str, period: str):
        self.pair = pair
        self.period = period
        self.period_in_sec = period_to_timerange_in_second(period)

    @abc.abstractclassmethod
    def range_query(self, start: datetime, end: datetime) -> List[Ohlcv]:
        raise NotImplementedError
    @abc.abstractclassmethod
    def get(self, time: datetime) -> Ohlcv:
        raise NotImplementedError
    
class OhlcvCache(OhlcvCacheFetcherAbstract):
    def __init__(self, pair: str, period: PeriodLiteral, session_class = Session):
        super().__init__(pair, period)
        self.table_class = period_to_table_class(period)
        self.session = session_class()

    def range_query(self, start: datetime, end: datetime) -> List[Ohlcv]:
        results = self.session.query(
            self.table_class
        ).order_by(
            self.table_class.timestamp.asc()
        ).filter(
            and_(self.table_class.timestamp.between(start, end - timedelta(seconds=1)), self.table_class.pair == self.pair)
        ).all()
        logger.debug(f"local data query results: {len(results)}")
        return list(map(lambda result: Ohlcv(
            result.timestamp, 
            float(result.open), 
            float(result.high), 
            float(result.low), 
            float(result.close), 
            float(result.volume)
        ), results))
    
    def get(self, ts: datetime) -> Optional[Ohlcv]:
        curr_dt = unify_dt(ts, period_to_timerange_in_second(self.period))
        result = self.session.query(
            self.table_class
        ).filter(
            and_(self.table_class.timestamp == curr_dt, self.table_class.pair == self.pair)
        ).first()
        return Ohlcv(
            result.timestamp, 
            float(result.open), 
            float(result.high), 
            float(result.low), 
            float(result.close), 
            float(result.volume)
        ) if result else None

    def _to_db_record(self, ohlcv: Ohlcv) -> OhlcvCacheBase:
        return self.table_class(
            pair=self.pair,
            timestamp=ohlcv.timestamp,
            open=ohlcv.open,
            high=ohlcv.high,
            low=ohlcv.low,
            close=ohlcv.close,
            volume=ohlcv.volume
        )

    def add(self, lines: Union[Ohlcv, List[Ohlcv]]):
        if type(lines) == list:
            for line in lines:
                self.session.add(self._to_db_record(line))
        else:
            self.session.add(self._to_db_record(lines))
        self.session.commit()

class OhlcvRemoteFetcher(OhlcvRemoteFetcherAbstract):
    def __init__(self, pair: str, period: Literal['1h', '1d']):
        super().__init__(pair, period)
        

    def range_query(self, start: datetime, end: datetime) -> List[Ohlcv]:
        result = []
        nomolized_start = int(dt_to_float(unify_dt(start, self.period_in_sec)) * 1000) 
        nomolized_end = int(dt_to_float(unify_dt(end, self.period_in_sec)) * 1000) 
        limit = int((nomolized_end - nomolized_start) / self.period_in_sec / 1000)
        while limit > 0:
            batch = 500 if limit > 500 else limit
            logger.debug(f"range_query from remote since {nomolized_start} ({datetime.fromtimestamp(nomolized_start / 1000)}) with limit {batch}")
            res_list = fetch_ohlcv(self.pair, self.period, since=nomolized_start, limit = batch)
            result.extend(list(map(ohlcv_from_backend, res_list)))
            limit -= batch
            nomolized_start += (batch * self.period_in_sec  * 1000)
        return result

    def get(self, ts: datetime) -> Ohlcv:
        res = None
        nomolized_ts = unify_dt(ts, self.period_in_sec)
        if nomolized_ts == unify_dt(datetime.now(), self.period_in_sec):
            res = fetch_ohlcv(self.pair, self.period, limit=1)
        else:
            res = fetch_ohlcv(self.pair, self.period, since=int(dt_to_float(nomolized_ts) * 1000), limit=1)
        return ohlcv_from_backend(res[0])


class OhlcvHistory:
    def __init__(self, pair: str, period: Literal['1h', '1d'], local_store_class: OhlcvCacheFetcherAbstract = OhlcvCache, remote_fetcher_class: OhlcvRemoteFetcherAbstract = OhlcvRemoteFetcher):
        self.pair = pair
        self.period = period
        self.local_store: OhlcvCacheFetcherAbstract = local_store_class(pair, period)
        self.remote_fetcher: OhlcvRemoteFetcherAbstract = remote_fetcher_class(pair, period)

    def current(self) -> Ohlcv:
        return self.remote_fetcher.query(datetime.now())
    
    # range query from [start_time, end_time)
    def range_query(self, start_time: datetime, end_time: datetime) -> List[Ohlcv]:
        time_interval = period_to_timerange_in_second(self.period)
        normalized_start = unify_dt(start_time, time_interval)
        normalized_end = unify_dt(end_time, time_interval)
        expected_count = int((dt_to_float(normalized_end) - dt_to_float(normalized_start)) / time_interval)
        logger.debug(f"range_query [{normalized_start}, {normalized_end}), data count: {expected_count}")

        local_data = self.local_store.range_query(normalized_start, normalized_end)
        if len(local_data) == expected_count:
            logger.debug('local database found all required data, return directly.')
            return local_data
        if len(local_data) == 0:
            remote_data = self.remote_fetcher.range_query(normalized_start, normalized_end)
            self.local_store.add(remote_data)
            return remote_data
        
        local_timerange = list(map(lambda item: item.timestamp, local_data))
        result = local_data
        miss_time_ranges = get_missed_time_ranges(local_timerange, normalized_start, normalized_end, time_interval)
        for time_range in miss_time_ranges:
            remote_data = self.remote_fetcher.range_query(time_range[0], time_range[1])
            # print_timestamps(list(map(lambda x: x.timestamp, remote_data)))
            self.local_store.add(remote_data)
            result.extend(remote_data)
        
        sorted_result = sorted(result, key=lambda item: item.timestamp)
        
        return sorted_result
        