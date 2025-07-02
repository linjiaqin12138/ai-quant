from typing import Dict, TypedDict, List, cast, Union

from lib.logger import logger
from lib.model import Ohlcv

import talib

import pandas as pd
import numpy as np


def to_df(ohlcv_list: List[Ohlcv]) -> pd.DataFrame:
    df = pd.DataFrame(ohlcv_list)
    df.sort_values(by="timestamp", ascending=True, inplace=True)
    return df.set_index("timestamp")


pick_close = lambda item: float(item.close)
change_rate = lambda item1, item2: float((item2 - item1) / item1)


# 计算给定范围内的K线图中到最后一个蜡烛柱的跌幅
def max_decline_rate(ohlcv_list: List[Ohlcv]) -> float:
    max_item = max(ohlcv_list, key=pick_close)
    return change_rate(max_item, ohlcv_list[-1].close)


# 计算给定范围内的K线图中到最后一个蜡烛柱的涨幅
def max_increase_rate(ohlcv_list: List[Ohlcv]) -> float:
    min_item = min(ohlcv_list, key=pick_close)
    return change_rate(min_item, ohlcv_list[-1].close)
