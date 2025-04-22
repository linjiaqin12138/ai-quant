from datetime import datetime, timedelta
from typing import Any, List

from sqlalchemy import insert, select, and_

from lib.utils.time import dt_to_ts
from lib.model import CryptoOhlcvHistory, Ohlcv
from lib.logger import logger
from .sqlalchemy import crypto_ohlcv_cache_tables, ashare_ohlcv_cache_tables
from .session import SessionAbstract

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

class OhlcvCacheFetcher:
    def __init__(self, session: SessionAbstract):
        self.session = session

    def _get_table(self, frame: str, market: str):
        table = crypto_ohlcv_cache_tables[frame] if market == 'crypto' else ashare_ohlcv_cache_tables[frame]
        if table is None:
            raise ValueError(f"Invalid frame: {frame} for market: {market}")
        return table

    def range_query(self, symbol: str, frame: str, start: datetime, end: datetime = datetime.now()) -> CryptoOhlcvHistory:
        logger.debug(f'local database range_query with symbol: {symbol}, frame: {frame}, start: {start}, end: {end}')
        
        table = self._get_table(frame, 'crypto' if symbol.endswith('USDT') else 'ashare')

        stmt = select(table).filter(
            and_(
                table.c.timestamp.between(dt_to_ts(start), dt_to_ts(end - timedelta(seconds=1))), 
                table.c.symbol == symbol
            )
        ).order_by(
            table.c.timestamp.asc()
        )
        compiled = stmt.compile()
        result = self.session.execute(compiled.string, compiled.params)
        return CryptoOhlcvHistory(
            symbol = symbol,
            frame = frame,
            # TODO 目前只支持这个
            exchange = 'binance',
            data = map_to_ohlcv(result.rows)
        )

    def add(self, history: CryptoOhlcvHistory):
        table = self._get_table(history.frame, 'crypto' if history.symbol.endswith('USDT') else 'ashare')
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
            self.session.execute(compiled.string, compiled.params)

__all__ = [
    'OhlcvCacheFetcher'
]