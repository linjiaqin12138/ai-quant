from typing import Union, List
import datetime
import time

import pandas as pd
from sqlalchemy import and_
import ccxt

from .exchange import exchange
from ..typedef import Scale
from .session import get_session
from .tables import get_table_class
from ..utils.logger import logger

MAX_RETRY_TIME = 5
def get_data_from_backend(function, **args):
    count = 0
    while True:
        try: 
            return getattr(exchange, function)(**args)
        except ccxt.errors.RequestTimeout as e:
            count += 1
            logger.warn(f'Retry {function} {count} times')
            time.sleep(2 ** (count - 1))
            if count > MAX_RETRY_TIME:
                raise e

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
    candles = get_data_from_backend('fetch_ohlcv', symbol=pair, timeframe=scale, limit=limit, since=since)
    df = pd.DataFrame(candles, columns=columns)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.sort_values(by='timestamp', ascending=False, inplace=True)
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
    return list(get_data_from_backend('fetch_tickers').keys())


__all__ = [
    'get_ohclv',
    'get_all_pairs'
]

