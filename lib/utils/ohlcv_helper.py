
from typing import TypedDict, List
from ..model import Ohlcv

import talib

import pandas as pd

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
    for i in range(1, macd_hist):
        if macd_hist[i] > 0 and macd_hist[i-1] <= 0:
            gold_cross_idxs.append(i)
        elif macd_hist[i] < 0 and macd_hist[i-1] >= 0:
            dead_cross_idxs.append(i)
        elif macd_hist[i] - macd_hist[i-1] > 0 and macd_hist[i] < 0:
            bad_turn_good_idxs.append(i)
        elif macd_hist[i] - macd_hist[i-1] < 0 and macd_hist[i] > 0:
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

    for i in range(1, df):
        if df['close'].iloc[i] > df['sar'].iloc[i] and df['close'].iloc[i-1] < df['sar'].iloc[i-1]:
            turn_up_idxs.append(i)
        elif df['close'].iloc[i] < df['sar'].iloc[i] and df['close'].iloc[i-1] > df['sar'].iloc[i-1]:
            turn_down_idxs.append(i)

    return {
        "turn_up_idxs": turn_up_idxs,
        "turn_down_idxs": turn_down_idxs,
        "sar": df['sar']
    }