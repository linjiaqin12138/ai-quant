import abc
from datetime import datetime, timedelta
from typing import Any, Generic, List, TypeVar

from sqlalchemy import insert, select, and_

from ...utils.time import dt_to_ts
from ...model import CryptoOhlcvHistory, CryptoHistoryFrame, Ohlcv, OhlcvHistory
from ...logger import logger
from .sqlalchemy import crypto_ohlcv_cache_tables
from .session import ExecuteResult, SqlAlchemySession

F = TypeVar('F', bound=str)
class OhlcvCacheFetcherAbstract(abc.ABC, Generic[F]):
    @abc.abstractmethod
    def range_query(self, symbol: str, frame: F, start: datetime, end: datetime = datetime.now()) -> OhlcvHistory:
        raise NotImplementedError
    @abc.abstractmethod
    def add(self, history: CryptoOhlcvHistory):
        raise NotImplementedError

def range_query(table: Any, session: SqlAlchemySession, start: datetime, end: datetime, symbol: str) -> ExecuteResult:
    stmt = select(table).filter(
        and_(
            table.c.timestamp.between(dt_to_ts(start), dt_to_ts(end - timedelta(seconds=1))), 
            table.c.symbol == symbol
        )
    ).order_by(
        table.c.timestamp.asc()
    )
    compiled = stmt.compile()
    return session.execute(compiled.string, compiled.params)

def add_ohlcv(table: Any, session: SqlAlchemySession, history: OhlcvHistory):
    for ohlcv in history.data:
        stmt = insert(table).values(
            symbol = history.symbol,
            timestamp = dt_to_ts(ohlcv.timestamp),
            open = str(ohlcv.open),
            high = str(ohlcv.high),
            low = str(ohlcv.low),
            close = str(ohlcv.close),
            volume = str(ohlcv.volume)
        )
        compiled = stmt.compile()
        session.execute(compiled.string, compiled.params)

def map_to_ohlcv(rows: List[Any]) -> List[Ohlcv]:
    return list(
        map(
            lambda item: Ohlcv(
                # TODO: 某些数据库不支持datetime，能不能不这样
                timestamp = datetime.fromtimestamp(item.timestamp / 1000),
                open = float(item.open),
                high = float(item.high),
                low = float(item.low),
                close = float(item.close),
                volume = float(item.volume),
            ), rows
        )
    )

class CryptoOhlcvCacheFetcher(OhlcvCacheFetcherAbstract[CryptoHistoryFrame]):
    def __init__(self, session: SqlAlchemySession):
        self.session = session

    def range_query(self, symbol: str, frame: CryptoHistoryFrame, start: datetime, end: datetime = datetime.now()) -> CryptoOhlcvHistory:
        logger.debug(f'local database range_query with symbol: {symbol}, frame: {frame}, start: {start}, end: {end}')
        table = crypto_ohlcv_cache_tables[frame]
        result = range_query(table, self.session, start, end, symbol)
        return CryptoOhlcvHistory(
            symbol = symbol,
            frame = frame,
            # TODO 目前只支持这个
            exchange = 'binance',
            data = map_to_ohlcv(result.rows)
        )

    def add(self, history: CryptoOhlcvHistory):
        add_ohlcv(crypto_ohlcv_cache_tables[history.frame], self.session, history)