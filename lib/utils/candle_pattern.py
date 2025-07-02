from typing import Dict, TypedDict, List, cast, Union

from lib.logger import logger
from lib.model import Ohlcv
from lib.utils.ohlcv import to_df

import talib
import pandas as pd
import numpy as np


PatternInfo = TypedDict("PatternInfo", {"name": str, "description": str})
pattern_mapping: Dict[str, PatternInfo] = {
    "CDL2CROWS": {
        "name": "两只乌鸦",
        "description": "看跌反转信号，通常出现在上升趋势的顶部。",
    },
    "CDL3BLACKCROWS": {
        "name": "三只乌鸦",
        "description": "强烈的看跌反转信号，由三根连续下降的长阴线组成。",
    },
    "CDL3INSIDE": {
        "name": "三内部上涨和下跌",
        "description": "可能的趋势反转信号，三根K线形成孕线组合。",
    },
    "CDL3LINESTRIKE": {
        "name": "三线打击",
        "description": "看涨或看跌信号，取决于三根K线后出现的第四根K线是否吞没。",
    },
    "CDL3OUTSIDE": {
        "name": "三外部上涨和下跌",
        "description": "趋势延续或反转信号，三根K线形成吞没组合。",
    },
    "CDLADVANCEBLOCK": {
        "name": "大敌当前",
        "description": "可能的看跌反转信号，由三根逐渐减弱的阳线组成。",
    },
    "CDLBELTHOLD": {
        "name": "捉腰带线",
        "description": "可能的趋势反转信号，单根K线，开盘价接近最高或最低点。",
    },
    "CDLDOJI": {
        "name": "十字线",
        "description": "表示市场的不确定性，可能是趋势反转的信号。",
    },
    "CDLENGULFING": {
        "name": "吞没形态",
        "description": "看涨或看跌反转信号，由两根K线组成，后一根完全吞没前一根。",
    },
    "CDLHAMMER": {
        "name": "锤子线",
        "description": "看涨反转信号，出现在下降趋势的底部，带长下影线。",
    },
    "CDLHANGINGMAN": {
        "name": "上吊线",
        "description": "看跌反转信号，出现在上升趋势的顶部，带长下影线。",
    },
    "CDLENGULFING": {
        "name": "吞没形态",
        "description": "可能的趋势反转信号，由一根K线完全覆盖另一根K线组成。",
    },
    "CDLDRAGONFLYDOJI": {
        "name": "蜻蜓十字",
        "description": "看涨反转信号，表明空头失去控制，可能引发反弹。",
    },
    "CDLINVERTEDHAMMER": {
        "name": "倒锤子线",
        "description": "看涨反转信号，出现在下降趋势的底部，带长上影线。",
    },
    "CDLPIERCING": {
        "name": "刺透形态",
        "description": "看涨反转信号，常见于下降趋势的底部，由两根K线组成。",
    },
    "CDLSPINNINGTOP": {
        "name": "纺锤线",
        "description": "表明市场暂时平衡，可能预示趋势反转或延续。",
    },
    "CDLSTALLEDPATTERN": {
        "name": "停顿形态",
        "description": "看涨延续信号，表示多头势能暂时停滞。",
    },
    "CDLKICKING": {
        "name": "反冲形态",
        "description": "强烈的趋势反转信号，由两根跳空K线组成。",
    },
    "CDLTAKURI": {
        "name": "探水竿",
        "description": "看涨反转信号，类似锤子线，但下影线更长。",
    },
    "CDLMORNINGSTAR": {
        "name": "早晨之星",
        "description": "强烈的看涨反转信号，常出现在下降趋势的底部。",
    },
    "CDLEVENINGSTAR": {
        "name": "黄昏之星",
        "description": "强烈的看跌反转信号，常出现在上升趋势的顶部。",
    },
    "CDL3STARSINSOUTH": {
        "name": "南方三星",
        "description": "看涨反转信号，常出现在下降趋势的底部，由三根逐渐减小的阴线组成。",
    },
    "CDL3WHITESOLDIERS": {
        "name": "三只白兵",
        "description": "强烈的看涨反转信号，由三根连续上涨的长阳线组成。",
    },
    "CDLABANDONEDBABY": {
        "name": "弃婴形态",
        "description": "强烈的反转信号，表示市场可能迅速反转，包含一根跳空的十字星。",
    },
    "CDLBREAKAWAY": {
        "name": "脱离形态",
        "description": "看涨或看跌信号，由五根K线组成，表明市场可能出现反转。",
    },
    "CDLCLOSINGMARUBOZU": {
        "name": "收盘秃线",
        "description": "强烈的趋势信号，表示市场收盘价等于最高价或最低价。",
    },
    "CDLCONCEALBABYSWALL": {
        "name": "藏婴吞没",
        "description": "罕见的反转信号，由四根K线组成，常见于剧烈波动的市场中。",
    },
    "CDLCOUNTERATTACK": {
        "name": "反击线",
        "description": "趋势反转信号，表示市场可能在开盘价附近反转。",
    },
    "CDLDARKCLOUDCOVER": {
        "name": "乌云盖顶",
        "description": "看跌反转信号，由两根K线组成，后一根开盘高于前一根收盘，但收盘深入前一根K线的实体内。",
    },
    "CDLDOJISTAR": {
        "name": "十字星",
        "description": "表明市场的不确定性，可能是趋势反转信号。",
    },
    "CDLEVENINGDOJISTAR": {
        "name": "黄昏十字星",
        "description": "强烈的看跌反转信号，常出现在上升趋势的顶部。",
    },
    "CDLGAPSIDESIDEWHITE": {
        "name": "白色并列缺口",
        "description": "趋势延续信号，由两根同方向的K线组成，通常表示趋势可能继续。",
    },
    "CDLGRAVESTONEDOJI": {
        "name": "墓碑十字",
        "description": "看跌反转信号，表示市场未能维持高价位，可能出现反转。",
    },
    "CDLHARAMI": {
        "name": "母子形态",
        "description": "可能的反转信号，由两根K线组成，后一根完全被前一根的实体包含。",
    },
    "CDLHARAMICROSS": {
        "name": "十字孕线",
        "description": "可能的反转信号，后一根K线为十字星，完全被前一根K线的实体包含。",
    },
    "CDLHIGHWAVE": {
        "name": "风高浪大线",
        "description": "表明市场犹豫不决，可能预示趋势反转或延续。",
    },
    "CDLHIKKAKE": {
        "name": "陷阱形态",
        "description": "趋势反转信号，由三根K线组成，表示突破后失败并回到原趋势。",
    },
    "CDLHIKKAKEMOD": {
        "name": "修正版陷阱形态",
        "description": "类似于陷阱形态，但更严格的识别标准。",
    },
    "CDLHOMINGPIGEON": {
        "name": "家鸽形态",
        "description": "看涨反转信号，由两根阴线组成，后一根实体完全包含在前一根实体内。",
    },
    "CDLIDENTICAL3CROWS": {
        "name": "三胞胎乌鸦",
        "description": "强烈的看跌信号，由三根连续的长阴线组成。",
    },
    "CDLINNECK": {
        "name": "颈内线",
        "description": "看跌信号，后一根K线的收盘价接近前一根K线的最低点。",
    },
    "CDLKICKINGBYLENGTH": {
        "name": "长度反冲形态",
        "description": "强烈的趋势信号，表示市场可能迅速反转方向。",
    },
    "CDLLADDERBOTTOM": {
        "name": "梯底形态",
        "description": "看涨反转信号，通常出现在下降趋势的底部。",
    },
    "CDLLONGLEGGEDDOJI": {
        "name": "长腿十字",
        "description": "表明市场高度犹豫，可能预示趋势反转。",
    },
    "CDLLONGLINE": {
        "name": "长实体线",
        "description": "表明市场的强烈趋势，通常为单根长阳线或长阴线。",
    },
    "CDLMARUBOZU": {
        "name": "光头光脚线",
        "description": "强烈的趋势信号，表示市场单边上涨或下跌，无上下影线。",
    },
    "CDLMATCHINGLOW": {
        "name": "相同低价",
        "description": "看涨反转信号，表示市场形成相同低点，支撑较强。",
    },
    "CDLMATHOLD": {
        "name": "矩形维持形态",
        "description": "看涨延续信号，表明多头趋势可能持续。",
    },
    "CDLMORNINGDOJISTAR": {
        "name": "早晨十字星",
        "description": "强烈的看涨反转信号，常出现在下降趋势的底部。",
    },
    "CDLONNECK": {
        "name": "颈上线",
        "description": "看跌信号，后一根K线的收盘价接近前一根K线的最低点，但不低于它。",
    },
    "CDLRICKSHAWMAN": {
        "name": "黄包车夫",
        "description": "表明市场犹豫不决，可能预示趋势反转。",
    },
    "CDLRISEFALL3METHODS": {
        "name": "涨跌三法",
        "description": "趋势延续信号，表示上涨或下跌趋势的中继形态。",
    },
    "CDLSEPARATINGLINES": {
        "name": "分离线",
        "description": "趋势延续信号，表明当前趋势可能继续。",
    },
    "CDLSHOOTINGSTAR": {
        "name": "射击之星",
        "description": "看跌反转信号，出现在上升趋势的顶部，带长上影线。",
    },
    "CDLSHORTLINE": {
        "name": "短实体线",
        "description": "表明市场趋势较弱，通常为单根短实体K线。",
    },
    "CDLSTICKSANDWICH": {
        "name": "条形三明治",
        "description": "看涨反转信号，由三根K线组成，中间一根低于两侧K线。",
    },
    "CDLTASUKIGAP": {
        "name": "跳空并列阳线/阴线",
        "description": "趋势延续信号，由两根跳空的K线和一根回补跳空的K线组成。",
    },
    "CDLTHRUSTING": {
        "name": "插入形态",
        "description": "看跌反转信号，表示市场未能完全反转。",
    },
    "CDLTRISTAR": {
        "name": "三星形态",
        "description": "强烈的反转信号，由三根连续的十字星组成。",
    },
    "CDLUNIQUE3RIVER": {
        "name": "奇特三河底",
        "description": "看涨反转信号，常出现在下降趋势的底部。",
    },
    "CDLUPSIDEGAP2CROWS": {
        "name": "向上跳空的两只乌鸦",
        "description": "看跌反转信号，由两根跳空K线组成。",
    },
    "CDLXSIDEGAP3METHODS": {
        "name": "三法形态",
        "description": "趋势延续信号，常见于多头或空头趋势中。",
    },
    # 可继续扩展其他形态...
}

# 获取TA-Lib支持的形态识别函数
all_candle_patterns = [func for func in dir(talib) if func.startswith("CDL")]
PatternCalulationResult = TypedDict(
    "PatternCalulationResult",
    {
        "pattern_idxs": List[int],
        "is_last_candle_pattern": bool,
        "pattern_info": PatternInfo,
    },
)
PatternCalulationResults = TypedDict(
    "PatternCalulationResults",
    {
        "pattern_results": Dict[str, PatternCalulationResult],
        "last_candle_patterns": List[PatternInfo],
    },
)


def detect_candle_patterns(ohlcv_list: List[Ohlcv]) -> PatternCalulationResults:
    """检测所有TA-Lib支持的形态和最后一条K线的形态状态."""
    assert len(ohlcv_list) >= 5
    df = to_df(ohlcv_list)
    open_prices = df["open"]
    high_prices = df["high"]
    low_prices = df["low"]
    close_prices = df["close"]

    pattern_results = {}
    last_index = len(ohlcv_list) - 1
    last_candle_patterns = []

    for pattern in all_candle_patterns:
        # 获取形态识别结果
        if pattern_mapping.get(pattern) is None:
            logger.warning(f"Skip pattern {pattern} calculation")
            continue
        result = getattr(talib, pattern)(
            open_prices, high_prices, low_prices, close_prices
        )

        # 检测形态发生的位置
        pattern_idxs = [i for i, value in enumerate(result) if value != 0]

        # 检测最后一条K线是否符合该形态
        is_last_candle_pattern = (
            bool(cast(pd.DataFrame, result).iloc[last_index] != 0)
            if last_index >= 0
            else False
        )

        # 保存结果
        if pattern_idxs:
            pattern_results[pattern] = {
                "pattern_idxs": pattern_idxs,
                "is_last_candle_pattern": is_last_candle_pattern,
                "pattern_info": pattern_mapping.get(pattern),
            }
            if is_last_candle_pattern:
                last_candle_patterns.append(pattern_mapping[pattern])

    # 返回结果和统计信息
    return {
        "pattern_results": pattern_results,
        "last_candle_patterns": last_candle_patterns,
    }
