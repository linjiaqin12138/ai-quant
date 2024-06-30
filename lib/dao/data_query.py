import datetime
from typing import List, Union

import pandas as pd

from ..logger import logger
from ..utils.time import curr_ts, unify_ts
from .event import get_event, set_event
from .exchange import fetch_ohlcv, fetch_ticker, load_markets
from .session import get_session
from .tables import Exchange_Info


def get_ohclv(
  pair: str, 
  scale: str, 
  limit: int = 500, 
  since: Union[int, None] = None,
  end: Union[datetime.datetime, None] = None,
) -> pd.DataFrame:
    # table_class = get_table_class(pair, scale)
    columns = ["timestamp", "open", "high", "low", "close", "volume"]
    # session = get_session()
    # if end and table_class:
    #     logger.debug('get ohclv from local database')
    #     res = None
    #     if since:
    #         res = session.query(table_class).filter(and_(table_class.timestamp >= since, table_class.timestamp < end)).all()
    #     else:
    #         res = session.query(table_class).filter(table_class.timestamp < end).limit(limit).all()
    #     records = []
    #     for row in res:
    #         # records.append(list(map(lambda col: row[col], columns))) TypeError: 'BTC_USDT_1D' object is not subscriptable
    #         records.append([row.timestamp, row.open, row.high, row.low, row.close, row.volume])
    #     df = pd.DataFrame.from_records(records, columns=columns)
    #     if len(df):
    #         return df
    #     else:
    #         logger.debug('Fallback return data query')

    # TODO: Support timeout retry ccxt.base.errors.RequestTimeout
    logger.debug("get ohclv from backend")
    candles = fetch_ohlcv(symbol=pair, timeframe=scale, limit=limit, since=since)
    df = pd.DataFrame(candles, columns=columns)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.sort_values(by="timestamp", ascending=True, inplace=True)
    logger.debug("get data from backend successfully")

    # if table_class:
    #     for _idx_, row in df.iterrows():
    #         if not session.query(table_class).filter(table_class.timestamp == row['timestamp']).all():
    #             logger.debug('Store data from backend into local database')
    #             session.add(table_class(
    #                 timestamp=row['timestamp'],
    #                 open=row['open'],
    #                 close=row['close'],
    #                 high=row['high'],
    #                 low=row['low'],
    #                 volume=row['volume']
    #             ))
    #             session.commit()
    #         else:
    #             logger.debug('Store data finished')
    #             break
    return df


def get_all_pairs(disable_cache=False) -> List[str]:
    markets = load_markets()
    last_update_time_str = get_event("get_all_pairs_last_update_time")
    sess = get_session()
    # Cache data is still valid in one day.
    if (
        (last_update_time_str is not None)
        and unify_ts(float(last_update_time_str), 86400) + 86400 * 7
        > unify_ts(curr_ts(), 86400)
        and disable_cache == False
    ):
        all_pairs = sess.query(Exchange_Info).all()
        logger.debug("Try get all pairs from local database")
        if all_pairs:
            logger.debug("Get all pairs from local database success")
            return list(map(lambda item: item.pair, all_pairs))
        logger.debug("Get pairs from local database failed, try get from remote")

    all_pairs = list(
        filter(
            lambda m: markets[m]["active"]
            and m != "NBTUSDT"
            and not m.endswith("/USDT:USDT"),
            markets,
        )
    )

    if disable_cache:
        return all_pairs

    logger.debug("Get pairs from remote success, Store it into local database")
    sess.query(Exchange_Info).delete()
    sess.commit()
    for pair in all_pairs:
        quote_volume = fetch_ticker(pair)["quoteVolume"]
        sess.add(Exchange_Info(pair=pair, quote_volume=quote_volume))
        sess.commit()
    set_event("get_all_pairs_last_update_time", str(curr_ts()))

    return all_pairs


def get_good_pairs(head: int = 100, coin_pair: str = "USDT") -> List[str]:
    sess = get_session()
    pairs = (
        sess.query(Exchange_Info)
        .filter(Exchange_Info.pair.like(f"%/{coin_pair}"))
        .order_by(Exchange_Info.quote_volume.desc())
        .limit(head)
        .all()
    )
    return list(map(lambda item: item.pair, pairs))


__all__ = ["get_ohclv", "get_all_pairs", "get_good_pairs"]
