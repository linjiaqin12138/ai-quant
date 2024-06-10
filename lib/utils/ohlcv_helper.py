
from typing import TypedDict, List, Tuple, Union
from ..model import Ohlcv

import talib

import pandas as pd
import numpy as np

MacdInfo = TypedDict(
    'MacdInfo', 
    {
        'gold_cross_idxs': List[int], 
        'dead_cross_idxs': List[int], 
        'turn_good_idxs': List[int],
        'turn_bad_idxs': List[int],
        'macd_hist': List[float]
    }
)

SarInfo = TypedDict(
    'SarInfo', 
    {
        'turn_up_idxs': List[int], 
        'turn_down_idxs': List[int],
        'sar': List[float]
    }
)

BollInfo = TypedDict(
    'BollInfo', 
    {
        'upperband': List[float], 
        'middleband': List[float],
        'lowerband': List[float],
        'band_open_idxs': List[int],
        'band_close_idxs': List[int],
        'turn_good_idxs': List[int],
        'turn_bad_idxs': List[int],
        'increase_over_band_idxs': List[int],
        'decrease_over_band_idxs': List[int]
    }
)


def to_df(ohlcv_list: List[Ohlcv]) -> pd.DataFrame:
    df = pd.DataFrame(ohlcv_list)
    df.sort_values(by="timestamp", ascending=True, inplace=True)
    return df

def macd_info(ohlcv_list: List[Ohlcv]) -> MacdInfo:
    df = to_df(ohlcv_list)
    _ ,_ ,macd_hist = talib.MACD(df['close'])
    gold_cross_idxs = []
    dead_cross_idxs = []
    bad_turn_good_idxs = []
    good_turn_bad_idxs = []
    for i in range(1, len(macd_hist)):
        if macd_hist[i] > 0 and macd_hist[i-1] <= 0:
            gold_cross_idxs.append(i)
        elif macd_hist[i] < 0 and macd_hist[i-1] >= 0:
            dead_cross_idxs.append(i)
        elif macd_hist[i] - macd_hist[i-1] > 0 and macd_hist[i-1] - macd_hist[i-2] < 0 and macd_hist[i] < 0:
            bad_turn_good_idxs.append(i)
        elif macd_hist[i] - macd_hist[i-1] < 0 and macd_hist[i-1] - macd_hist[i-2] > 0 and macd_hist[i] > 0:
            good_turn_bad_idxs.append(i)
    return {
        "gold_cross_idxs": gold_cross_idxs,
        "dead_cross_idxs": dead_cross_idxs,
        "turn_good_idxs": bad_turn_good_idxs,
        "turn_bad_idxs": good_turn_bad_idxs,
        "macd_hist": macd_hist
    }


def sar_info(ohlcv_list: List[Ohlcv]) -> SarInfo:
    df = to_df(ohlcv_list)
    df['sar'] = talib.SAR(df['high'], df['low'], acceleration=0.02, maximum=0.2)
    turn_up_idxs = []
    turn_down_idxs = []

    for i in range(1, len(df)):
        if df['close'].iloc[i] > df['sar'].iloc[i] and df['close'].iloc[i-1] < df['sar'].iloc[i-1]:
            turn_up_idxs.append(i)
        elif df['close'].iloc[i] < df['sar'].iloc[i] and df['close'].iloc[i-1] > df['sar'].iloc[i-1]:
            turn_down_idxs.append(i)

    return {
        "turn_up_idxs": turn_up_idxs,
        "turn_down_idxs": turn_down_idxs,
        "sar": df['sar']
    }

def boll_info(ohlcv_list: List[Ohlcv]) -> BollInfo: 
    assert len(ohlcv_list) > 20
    df = to_df(ohlcv_list)
    df['upperband'], df['middleband'], df['lowerband'] = talib.BBANDS(df['close'], timeperiod=20)
    df['bandwidth'] = (df['upperband'] - df['lowerband']) / df['middleband']
    # df['band_open_signal'] = df['bandwidth'].where((df['bandwidth'] /  df['bandwidth'].shift(1) - 1) > 0.2, 1, 0)
    # df['band_close_signal'] = df['bandwidth'].where((df['bandwidth'] /  df['bandwidth'].shift(1) - 1) < -0.2, 1, 0)
    band_open_idxs = []
    band_close_idxs = []
    turn_good_idxs = []
    turn_bad_idxs = []
    increase_over_band_idxs = []
    decrease_over_band_idxs = []
    
    for i in range(1, len(df)):
        if (df['bandwidth'].iloc[i] /  df['bandwidth'].iloc[i - 1]  - 1) > 0.2 and ((len(band_open_idxs) > 0 and len(band_close_idxs) > 0 and band_open_idxs[-1] < band_close_idxs[-1]) or len(band_open_idxs) == 0):
            band_open_idxs.append(i)
        if (df['bandwidth'].iloc[i] /  df['bandwidth'].iloc[i - 1]  - 1) < -0.2 and (len(band_open_idxs) > 0 and len(band_close_idxs) > 0 and band_open_idxs[-1] > band_close_idxs[-1] or len(band_close_idxs) == 0):
            band_close_idxs.append(i)
        if df['close'].iloc[i] > df['bandwidth'].iloc[i] and df['close'].iloc[i - 1] < df['bandwidth'].iloc[i - 1]:
            turn_good_idxs.append(i)
        if df['close'].iloc[i] < df['bandwidth'].iloc[i] and df['close'].iloc[i - 1] > df['bandwidth'].iloc[i - 1]:
            turn_bad_idxs.append(i)
        if df['close'].iloc[i] > df['upperband'].iloc[i]:
            increase_over_band_idxs.append(i)
        if df['close'].iloc[i] < df['lowerband'].iloc[i]:
            decrease_over_band_idxs.append(i)
    return {
        'lowerband': df['lowerband'],
        'middleband': df['middleband'],
        'upperband': df['upperband'],
        'band_open_idxs': band_open_idxs,
        'band_close_idxs': band_close_idxs,
        'turn_good_idxs': turn_good_idxs,
        'turn_bad_idxs': turn_bad_idxs,
        'increase_over_band_idxs': increase_over_band_idxs,
        'decrease_over_band_idxs': decrease_over_band_idxs
    }

pick_close = lambda item: item.close
change_rate = lambda item1, item2: (item2 - item1) / item1

def idxs_to_values_list(ohlcv: List[Ohlcv], idxs: List[int], column = 'close') -> Union[List[Union[float, np.nan]], None]:
    if len(ohlcv) == 0 or len(ohlcv) == 0:
        return None
    result = [np.nan] * len(ohlcv)
    for idx in idxs:
        result[idx] = getattr(ohlcv[idx], column)

    return result


# 计算给定范围内的K线图中到最后一个蜡烛柱的跌幅
def max_decline_rate(ohlcv_list: List[Ohlcv]) -> Tuple[float]:
    max_item = max(ohlcv_list, key=pick_close)
    return change_rate(max_item, ohlcv_list[-1].close)

# 计算给定范围内的K线图中到最后一个蜡烛柱的跌幅
def max_increase_rate(ohlcv_list: List[Ohlcv]) -> Tuple[float]:
    min_item = min(ohlcv_list, key=pick_close)
    return change_rate(min_item, ohlcv_list[-1].close)