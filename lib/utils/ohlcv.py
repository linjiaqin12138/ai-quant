
from typing import Dict, TypedDict, List, cast, Union

from ..logger import logger
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
        'macd_hist': List[float],
        'macd_hist_series': pd.Series,
        'is_gold_cross': bool,
        'is_dead_cross': bool,
        'is_turn_good': bool,
        'is_turn_bad': bool
    }
)

SarInfo = TypedDict(
    'SarInfo', 
    {
        'turn_up_idxs': List[int], 
        'turn_down_idxs': List[int],
        'is_turn_up': bool,
        'is_turn_down': bool,
        'sar': List[float],
        'sar_series': pd.Series
    }
)

BollInfo = TypedDict(
    'BollInfo', 
    {
        'upperband': List[float], 
        'middleband': List[float],
        'lowerband': List[float],
        'upperband_series': pd.Series, 
        'middleband_series': pd.Series,
        'lowerband_series': pd.Series,
        'band_open_idxs': List[int],
        'band_close_idxs': List[int],
        'turn_good_idxs': List[int],
        'turn_bad_idxs': List[int],
        'increase_over_band_idxs': List[int],
        'decrease_over_band_idxs': List[int],
        'is_open': bool,
        'is_close': bool,
        'is_turn_good': bool,
        'is_turn_bad': bool,
        'is_increase_over': bool,
        'is_decrease_over': bool
    }
)

Sam5Info = TypedDict(
    'Sam5Info', 
    {
        'sma5': List[float],
        'sma5_series': pd.Series
    }
)

Sam20Info = TypedDict(
    'Sam20Info', 
    {
        'sma20': List[float],
        'sma20_series': pd.Series
    }
)

RsiInfo = TypedDict(
    'RsiInfo', 
    {
        'rsi': List[float],
        'rsi_series': pd.Series
    }
)

StochasticOscillatorInfo = TypedDict(
    'StochasticOscillatorInfo', 
    {
        'stoch_k': List[float],
        'stoch_d': List[float],
        'stoch_k_series': pd.Series,
        'stoch_d_series': pd.Series
    }
)

AtrInfo = TypedDict(
    'AtrInfo',
    {
        'atr': List[float],
        'atr_series': pd.Series
    }
)

def is_happened(points_idxs: List[int], max_len: int) -> bool:
    return len(points_idxs) > 0 and points_idxs[-1] == max_len - 1

def to_df(ohlcv_list: List[Ohlcv]) -> pd.DataFrame:
    df = pd.DataFrame(ohlcv_list)
    df.sort_values(by="timestamp", ascending=True, inplace=True)
    return df.set_index('timestamp')

def macd_info(ohlcv_list: List[Ohlcv]) -> MacdInfo:
    assert len(ohlcv_list) > 34
    df = to_df(ohlcv_list)
    _ ,_ ,macd_hist = talib.MACD(df['close'])
    gold_cross_idxs = []
    dead_cross_idxs = []
    bad_turn_good_idxs = []
    good_turn_bad_idxs = []
    for i in range(1, len(macd_hist)):
        if macd_hist.iloc[i] > 0 and macd_hist.iloc[i-1] < 0:
            gold_cross_idxs.append(i)
        elif macd_hist.iloc[i] < 0 and macd_hist.iloc[i-1] > 0:
            dead_cross_idxs.append(i)
        elif macd_hist.iloc[i] - macd_hist.iloc[i-1] > 0 and macd_hist.iloc[i-1] - macd_hist.iloc[i-2] < 0 and macd_hist.iloc[i] < 0:
            bad_turn_good_idxs.append(i)
        elif macd_hist.iloc[i] - macd_hist.iloc[i-1] < 0 and macd_hist.iloc[i-1] - macd_hist.iloc[i-2] > 0 and macd_hist.iloc[i] > 0:
            good_turn_bad_idxs.append(i)

    return {
        "gold_cross_idxs": gold_cross_idxs,
        "dead_cross_idxs": dead_cross_idxs,
        "turn_good_idxs": bad_turn_good_idxs,
        "turn_bad_idxs": good_turn_bad_idxs,
        "macd_hist": list(macd_hist),
        "macd_hist_series": macd_hist,
        'is_dead_cross': is_happened(dead_cross_idxs, len(macd_hist)),
        'is_gold_cross': is_happened(gold_cross_idxs, len(macd_hist)),
        'is_turn_bad': is_happened(good_turn_bad_idxs, len(macd_hist)),
        'is_turn_good': is_happened(bad_turn_good_idxs, len(macd_hist))
    }


def sar_info(ohlcv_list: List[Ohlcv]) -> SarInfo:
    assert len(ohlcv_list) > 1
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
        'is_turn_up': is_happened(turn_up_idxs, len(ohlcv_list)),
        'is_turn_down': is_happened(turn_down_idxs, len(ohlcv_list)),
        "sar": list(df['sar']),
        'sar_series': df['sar']
    }

def sam5_info(ohlcv_list: List[Ohlcv]) -> Sam5Info:
    assert len(ohlcv_list) > 4
    df = to_df(ohlcv_list)
    df['sma5'] = talib.SMA(df['close'], timeperiod=5)
    return {
        'sma5': list(df['sma5']),
        'sma5_series': df['sma5']
    }

def sam20_info(ohlcv_list: List[Ohlcv]) -> Sam20Info:
    assert len(ohlcv_list) > 19
    df = to_df(ohlcv_list)
    df['sma20'] = talib.SMA(df['close'], timeperiod=20)
    return {
        'sma20': list(df['sma20']),
        'sma20_series': df['sma20']
    }

def rsi_info(ohlcv_list: List[Ohlcv]) -> RsiInfo:
    assert len(ohlcv_list) > 13
    df = to_df(ohlcv_list)
    df['rsi'] = talib.RSI(df['close'], timeperiod=14)
    return {
        'rsi': list(df['rsi']),
        'rsi_series': df['rsi']
    }

def stochastic_oscillator_info(ohlcv_list: List[Ohlcv]) -> StochasticOscillatorInfo:
    assert len(ohlcv_list) > 13
    df = to_df(ohlcv_list)
    df['stoch_k'], df['stoch_d'] = talib.STOCH(df['high'], df['low'], df['close'], fastk_period=14, slowk_period=3, slowd_period=3)
    return {
        'stoch_k': list(df['stoch_k']),
        'stoch_d': list(df['stoch_d']),
        'stoch_k_series': df['stoch_k'],
        'stoch_d_series': df['stoch_d']
    }

def atr_info(ohlcv_list: List[Ohlcv]) -> AtrInfo:
    assert len(ohlcv_list) > 13  # ATR typically uses a 14-day period
    df = to_df(ohlcv_list)
    df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
    return {
        'atr': list(df['atr']),
        'atr_series': df['atr']
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
        if df['close'].iloc[i] > df['middleband'].iloc[i] and df['close'].iloc[i - 1] < df['middleband'].iloc[i - 1]:
            turn_good_idxs.append(i)
        if df['close'].iloc[i] < df['middleband'].iloc[i] and df['close'].iloc[i - 1] > df['middleband'].iloc[i - 1]:
            turn_bad_idxs.append(i)
        if df['close'].iloc[i] > df['upperband'].iloc[i]:
            increase_over_band_idxs.append(i)
        if df['close'].iloc[i] < df['lowerband'].iloc[i]:
            decrease_over_band_idxs.append(i)
    return {
        'lowerband': list(df['lowerband']),
        'middleband': list(df['middleband']),
        'upperband': list(df['upperband']),
        'lowerband_series': df['lowerband'],
        'middleband_series': df['middleband'],
        'upperband_series': df['upperband'],
        'band_open_idxs': band_open_idxs,
        'band_close_idxs': band_close_idxs,
        'turn_good_idxs': turn_good_idxs,
        'turn_bad_idxs': turn_bad_idxs,
        'increase_over_band_idxs': increase_over_band_idxs,
        'decrease_over_band_idxs': decrease_over_band_idxs,
        'is_close': is_happened(band_close_idxs, len(ohlcv_list)),
        'is_open': is_happened(band_open_idxs, len(ohlcv_list)),
        'is_turn_good': is_happened(turn_good_idxs, len(ohlcv_list)),
        'is_turn_bad': is_happened(turn_bad_idxs, len(ohlcv_list)),
        'is_increase_over': is_happened(increase_over_band_idxs, len(ohlcv_list)),
        'is_decrease_over': is_happened(decrease_over_band_idxs, len(ohlcv_list)),
    }
PatternInfo = TypedDict('PatternInfo', {
    'name': str,
    'description': str
})
pattern_mapping: Dict[str, PatternInfo] = {
    "CDL2CROWS": {
        "name": "两只乌鸦",
        "description": "看跌反转信号，通常出现在上升趋势的顶部。"
    },
    "CDL3BLACKCROWS": {
        "name": "三只乌鸦",
        "description": "强烈的看跌反转信号，由三根连续下降的长阴线组成。"
    },
    "CDL3INSIDE": {
        "name": "三内部上涨和下跌",
        "description": "可能的趋势反转信号，三根K线形成孕线组合。"
    },
    "CDL3LINESTRIKE": {
        "name": "三线打击",
        "description": "看涨或看跌信号，取决于三根K线后出现的第四根K线是否吞没。"
    },
    "CDL3OUTSIDE": {
        "name": "三外部上涨和下跌",
        "description": "趋势延续或反转信号，三根K线形成吞没组合。"
    },
    "CDLADVANCEBLOCK": {
        "name": "大敌当前",
        "description": "可能的看跌反转信号，由三根逐渐减弱的阳线组成。"
    },
    "CDLBELTHOLD": {
        "name": "捉腰带线",
        "description": "可能的趋势反转信号，单根K线，开盘价接近最高或最低点。"
    },
    "CDLDOJI": {
        "name": "十字星",
        "description": "表示市场的不确定性，可能是趋势反转的信号。"
    },
    "CDLENGULFING": {
        "name": "吞没形态",
        "description": "看涨或看跌反转信号，由两根K线组成，后一根完全吞没前一根。"
    },
    "CDLHAMMER": {
        "name": "锤子线",
        "description": "看涨反转信号，出现在下降趋势的底部，带长下影线。"
    },
    "CDLHANGINGMAN": {
        "name": "上吊线",
        "description": "看跌反转信号，出现在上升趋势的顶部，带长下影线。"
    },
    "CDLENGULFING": {
        "name": "吞没形态",
        "description": "可能的趋势反转信号，由一根K线完全覆盖另一根K线组成。"
    },
    "CDLDRAGONFLYDOJI": {
        "name": "蜻蜓十字",
        "description": "看涨反转信号，表明空头失去控制，可能引发反弹。"
    },
    "CDLINVERTEDHAMMER": {
        "name": "倒锤子线",
        "description": "看涨反转信号，出现在下降趋势的底部，带长上影线。"
    },
    "CDLPIERCING": {
        "name": "刺透形态",
        "description": "看涨反转信号，常见于下降趋势的底部，由两根K线组成。"
    },
    "CDLSPINNINGTOP": {
        "name": "纺锤线",
        "description": "表明市场暂时平衡，可能预示趋势反转或延续。"
    },
    "CDLSTALLEDPATTERN": {
        "name": "停顿形态",
        "description": "看涨延续信号，表示多头势能暂时停滞。"
    },
    "CDLKICKING": {
        "name": "反冲形态",
        "description": "强烈的趋势反转信号，由两根跳空K线组成。"
    },
    "CDLTAKURI": {
        "name": "探水竿",
        "description": "看涨反转信号，类似锤子线，但下影线更长。"
    },
    "CDLMORNINGSTAR": {
        "name": "早晨之星",
        "description": "强烈的看涨反转信号，常出现在下降趋势的底部。"
    },
    "CDLEVENINGSTAR": {
        "name": "黄昏之星",
        "description": "强烈的看跌反转信号，常出现在上升趋势的顶部。"
    },
    "CDL3STARSINSOUTH": {
        "name": "南方三星",
        "description": "看涨反转信号，常出现在下降趋势的底部，由三根逐渐减小的阴线组成。"
    },
    "CDL3WHITESOLDIERS": {
        "name": "三只白兵",
        "description": "强烈的看涨反转信号，由三根连续上涨的长阳线组成。"
    },
    "CDLABANDONEDBABY": {
        "name": "弃婴形态",
        "description": "强烈的反转信号，表示市场可能迅速反转，包含一根跳空的十字星。"
    },
    "CDLBREAKAWAY": {
        "name": "脱离形态",
        "description": "看涨或看跌信号，由五根K线组成，表明市场可能出现反转。"
    },
    "CDLCLOSINGMARUBOZU": {
        "name": "收盘秃线",
        "description": "强烈的趋势信号，表示市场收盘价等于最高价或最低价。"
    },
    "CDLCONCEALBABYSWALL": {
        "name": "藏婴吞没",
        "description": "罕见的反转信号，由四根K线组成，常见于剧烈波动的市场中。"
    },
    "CDLCOUNTERATTACK": {
        "name": "反击线",
        "description": "趋势反转信号，表示市场可能在开盘价附近反转。"
    },
    "CDLDARKCLOUDCOVER": {
        "name": "乌云盖顶",
        "description": "看跌反转信号，由两根K线组成，后一根开盘高于前一根收盘，但收盘深入前一根K线的实体内。"
    },
    "CDLDOJISTAR": {
        "name": "十字星",
        "description": "表明市场的不确定性，可能是趋势反转信号。"
    },
    "CDLEVENINGDOJISTAR": {
        "name": "黄昏十字星",
        "description": "强烈的看跌反转信号，常出现在上升趋势的顶部。"
    },
    "CDLGAPSIDESIDEWHITE": {
        "name": "白色并列缺口",
        "description": "趋势延续信号，由两根同方向的K线组成，通常表示趋势可能继续。"
    },
    "CDLGRAVESTONEDOJI": {
        "name": "墓碑十字",
        "description": "看跌反转信号，表示市场未能维持高价位，可能出现反转。"
    },
    "CDLHARAMI": {
        "name": "母子形态",
        "description": "可能的反转信号，由两根K线组成，后一根完全被前一根的实体包含。"
    },
    "CDLHARAMICROSS": {
        "name": "十字孕线",
        "description": "可能的反转信号，后一根K线为十字星，完全被前一根K线的实体包含。"
    },
    "CDLHIGHWAVE": {
        "name": "风高浪大线",
        "description": "表明市场犹豫不决，可能预示趋势反转或延续。"
    },
    "CDLHIKKAKE": {
        "name": "陷阱形态",
        "description": "趋势反转信号，由三根K线组成，表示突破后失败并回到原趋势。"
    },
    "CDLHIKKAKEMOD": {
        "name": "修正版陷阱形态",
        "description": "类似于陷阱形态，但更严格的识别标准。"
    },
    "CDLHOMINGPIGEON": {
        "name": "家鸽形态",
        "description": "看涨反转信号，由两根阴线组成，后一根实体完全包含在前一根实体内。"
    },
    "CDLIDENTICAL3CROWS": {
        "name": "三胞胎乌鸦",
        "description": "强烈的看跌信号，由三根连续的长阴线组成。"
    },
    "CDLINNECK": {
        "name": "颈内线",
        "description": "看跌信号，后一根K线的收盘价接近前一根K线的最低点。"
    },
    "CDLKICKINGBYLENGTH": {
        "name": "长度反冲形态",
        "description": "强烈的趋势信号，表示市场可能迅速反转方向。"
    },
    "CDLLADDERBOTTOM": {
        "name": "梯底形态",
        "description": "看涨反转信号，通常出现在下降趋势的底部。"
    },
    "CDLLONGLEGGEDDOJI": {
        "name": "长腿十字",
        "description": "表明市场高度犹豫，可能预示趋势反转。"
    },
    "CDLLONGLINE": {
        "name": "长实体线",
        "description": "表明市场的强烈趋势，通常为单根长阳线或长阴线。"
    },
    "CDLMARUBOZU": {
        "name": "光头光脚线",
        "description": "强烈的趋势信号，表示市场单边上涨或下跌，无上下影线。"
    },
    "CDLMATCHINGLOW": {
        "name": "相同低价",
        "description": "看涨反转信号，表示市场形成相同低点，支撑较强。"
    },
    "CDLMATHOLD": {
        "name": "矩形维持形态",
        "description": "看涨延续信号，表明多头趋势可能持续。"
    },
    "CDLMORNINGDOJISTAR": {
        "name": "早晨十字星",
        "description": "强烈的看涨反转信号，常出现在下降趋势的底部。"
    },
    "CDLONNECK": {
        "name": "颈上线",
        "description": "看跌信号，后一根K线的收盘价接近前一根K线的最低点，但不低于它。"
    },
    "CDLRICKSHAWMAN": {
        "name": "黄包车夫",
        "description": "表明市场犹豫不决，可能预示趋势反转。"
    },
    "CDLRISEFALL3METHODS": {
        "name": "涨跌三法",
        "description": "趋势延续信号，表示上涨或下跌趋势的中继形态。"
    },
    "CDLSEPARATINGLINES": {
        "name": "分离线",
        "description": "趋势延续信号，表明当前趋势可能继续。"
    },
    "CDLSHOOTINGSTAR": {
        "name": "射击之星",
        "description": "看跌反转信号，出现在上升趋势的顶部，带长上影线。"
    },
    "CDLSHORTLINE": {
        "name": "短实体线",
        "description": "表明市场趋势较弱，通常为单根短实体K线。"
    },
    "CDLSTICKSANDWICH": {
        "name": "条形三明治",
        "description": "看涨反转信号，由三根K线组成，中间一根低于两侧K线。"
    },
    "CDLTASUKIGAP": {
        "name": "跳空并列阳线/阴线",
        "description": "趋势延续信号，由两根跳空的K线和一根回补跳空的K线组成。"
    },
    "CDLTHRUSTING": {
        "name": "插入形态",
        "description": "看跌反转信号，表示市场未能完全反转。"
    },
    "CDLTRISTAR": {
        "name": "三星形态",
        "description": "强烈的反转信号，由三根连续的十字星组成。"
    },
    "CDLUNIQUE3RIVER": {
        "name": "奇特三河底",
        "description": "看涨反转信号，常出现在下降趋势的底部。"
    },
    "CDLUPSIDEGAP2CROWS": {
        "name": "向上跳空的两只乌鸦",
        "description": "看跌反转信号，由两根跳空K线组成。"
    },
    "CDLXSIDEGAP3METHODS": {
        "name": "三法形态",
        "description": "趋势延续信号，常见于多头或空头趋势中。"
    }
    # 可继续扩展其他形态...
}

# 获取TA-Lib支持的形态识别函数
all_candle_patterns = [func for func in dir(talib) if func.startswith("CDL")]
PatternCalulationResult = TypedDict('PatternCalulationResult', {
    "pattern_idxs": List[int],
    "is_last_candle_pattern": bool,
    "pattern_info": PatternInfo
})
PatternCalulationResults = TypedDict('PatternCalulationResults', {
    "pattern_results": Dict[str, PatternCalulationResult],
    "last_candle_patterns": List[PatternInfo]
})

def detect_candle_patterns(ohlcv_list: List[Ohlcv]) -> PatternCalulationResults:
    """检测所有TA-Lib支持的形态和最后一条K线的形态状态."""
    assert len(ohlcv_list) >= 5
    df = to_df(ohlcv_list)
    open_prices = df['open']
    high_prices = df['high']
    low_prices = df['low']
    close_prices = df['close']

    pattern_results = {}
    last_index = len(ohlcv_list) - 1
    last_candle_patterns = []

    for pattern in all_candle_patterns:
        # 获取形态识别结果
        if pattern_mapping.get(pattern) is None:
            logger.warning(f"Skip pattern {pattern} calculation")
            continue
        result = getattr(talib, pattern)(open_prices, high_prices, low_prices, close_prices)

        # 检测形态发生的位置
        pattern_idxs = [i for i, value in enumerate(result) if value != 0]

        # 检测最后一条K线是否符合该形态
        is_last_candle_pattern = bool(cast(pd.DataFrame, result).iloc[last_index] != 0) if last_index >= 0 else False

        # 保存结果
        if pattern_idxs:
            pattern_results[pattern] = {
                "pattern_idxs": pattern_idxs,
                "is_last_candle_pattern": is_last_candle_pattern,
                "pattern_info": pattern_mapping.get(pattern)
            }
            if is_last_candle_pattern:
                last_candle_patterns.append(pattern_mapping[pattern])

    # 返回结果和统计信息
    return {
        "pattern_results": pattern_results,
        "last_candle_patterns": last_candle_patterns
    }

pick_close = lambda item: float(item.close)
change_rate = lambda item1, item2: float((item2 - item1) / item1)

def idxs_to_values_list(ohlcv: List[Ohlcv], idxs: List[int], column = 'close') -> Union[List[Union[float, np.nan]], None]:
    if len(ohlcv) == 0 or len(ohlcv) == 0:
        return None
    result = [np.nan] * len(ohlcv)
    for idx in idxs:
        result[idx] = getattr(ohlcv[idx], column)

    return result

# 计算给定范围内的K线图中到最后一个蜡烛柱的跌幅
def max_decline_rate(ohlcv_list: List[Ohlcv]) -> float:
    max_item = max(ohlcv_list, key=pick_close)
    return change_rate(max_item, ohlcv_list[-1].close)

# 计算给定范围内的K线图中到最后一个蜡烛柱的涨幅
def max_increase_rate(ohlcv_list: List[Ohlcv]) -> float:
    min_item = min(ohlcv_list, key=pick_close)
    return change_rate(min_item, ohlcv_list[-1].close)