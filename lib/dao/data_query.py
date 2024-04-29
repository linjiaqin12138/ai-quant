from typing import Union, List
import datetime

import pandas as pd
from sqlalchemy import and_

from .exchange import load_markets, fetch_ohlcv
from .session import get_session
from .tables import get_table_class
from ..utils.logger import logger

def get_ohclv(
  pair: str, 
  scale: str, 
  limit: int = 500, 
  since: Union[datetime.datetime, None] = None,
  end: Union[datetime.datetime, None] = None,
) -> pd.DataFrame:
    table_class = get_table_class(pair, scale)
    columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    session = get_session()
    if end and table_class:
        logger.debug('get ohclv from local database')
        res = None
        if since:
            res = session.query(table_class).filter(and_(table_class.timestamp >= since, table_class.timestamp < end)).all()
        else:
            res = session.query(table_class).filter(table_class.timestamp < end).limit(limit).all()
        records = []
        for row in res:
            # records.append(list(map(lambda col: row[col], columns))) TypeError: 'BTC_USDT_1D' object is not subscriptable
            records.append([row.timestamp, row.open, row.high, row.low, row.close, row.volume])
        df = pd.DataFrame.from_records(records, columns=columns)
        if len(df):
            return df
        else:
            logger.debug('Fallback return data query')

    # TODO: Support timeout retry ccxt.base.errors.RequestTimeout
    logger.debug('get ohclv from backend')
    candles = fetch_ohlcv(symbol=pair, timeframe=scale, limit=limit, since=since)
    df = pd.DataFrame(candles, columns=columns)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.sort_values(by='timestamp', ascending=True, inplace=True)
    logger.debug('get data from backend successfully')

    if table_class:
        for _idx_, row in df.iterrows():
            if not session.query(table_class).filter(table_class.timestamp == row['timestamp']).all():
                logger.debug('Store data from backend into local database')
                session.add(table_class(
                    timestamp=row['timestamp'],
                    open=row['open'],
                    close=row['close'],
                    high=row['high'],
                    low=row['low'],
                    volume=row['volume']
                ))
                session.commit()
            else:
                logger.debug('Store data finished')
                break
    return df

def get_all_pairs() -> List[str]:
    markets = load_markets()
    return list(filter(lambda m: markets[m]['active'], markets))

__all__ = [
    'get_ohclv',
    'get_all_pairs'
]

