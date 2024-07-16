import abc
from datetime import datetime, timedelta

from sqlalchemy import insert, select, and_

from ...utils.time import dt_to_ts
from ...model import CryptoOhlcvHistory, CryptoHistoryFrame, Ohlcv
from ...logger import logger
from .sqlalchemy import ohlcv_cache_tables
from .session import SqlAlchemySession

class CryptoOhlcvCacheFetcherAbstract(abc.ABC):
    @abc.abstractmethod
    def range_query(self, pair: str, frame: CryptoHistoryFrame, start: datetime, end: datetime = datetime.now()) -> CryptoOhlcvHistory:
        raise NotImplementedError
    @abc.abstractmethod
    def add(self, history: CryptoOhlcvHistory):
        raise NotImplementedError
    
    
class CryptoOhlcvCacheFetcher(CryptoOhlcvCacheFetcherAbstract):
    def __init__(self, session: SqlAlchemySession):
        self.session = session

    def range_query(self, pair: str, frame: CryptoHistoryFrame, start: datetime, end: datetime = datetime.now()) -> CryptoOhlcvHistory:
        logger.debug(f'local database range_query with pair: {pair}, frame: {frame}, start: {start}, end: {end}')
        table = ohlcv_cache_tables[frame]
        stmt = select(table).filter(
            and_(
                table.c.timestamp.between(dt_to_ts(start), dt_to_ts(end - timedelta(seconds=1))), 
                table.c.pair == pair
            )
        ).order_by(
            table.c.timestamp.asc()
        )
        compiled = stmt.compile()
        result = self.session.execute(compiled.string, compiled.params)
        return CryptoOhlcvHistory(
            pair = pair,
            frame = frame,
            # TODO 目前只支持这个
            exchange = 'binance',
            data = list(
                map(
                    lambda item: Ohlcv(
                        # TODO: 某些数据库不支持datetime，能不能不这样
                        timestamp = datetime.fromtimestamp(item.timestamp / 1000),
                        open = float(item.open),
                        high = float(item.high),
                        low = float(item.low),
                        close = float(item.close),
                        volume = float(item.volume),
                    ), result.rows
                )
            )
        )
    def add(self, history: CryptoOhlcvHistory):
        for ohlcv in history.data:
            stmt = insert(ohlcv_cache_tables[history.frame]).values(
                pair = history.pair,
                timestamp = dt_to_ts(ohlcv.timestamp),
                open = str(ohlcv.open),
                high = str(ohlcv.high),
                low = str(ohlcv.low),
                close = str(ohlcv.close),
                volume = str(ohlcv.volume)
            )
            compiled = stmt.compile()
            self.session.execute(compiled.string, compiled.params)