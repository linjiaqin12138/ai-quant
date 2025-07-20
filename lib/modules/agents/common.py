from datetime import datetime, timedelta
import json
from typing import List, Literal
from lib.model.common import Ohlcv
from lib.modules.news_proxy import news_proxy
from lib.modules.trade.ashare import ashare
from lib.modules.trade.crypto import crypto
from lib.utils.candle_pattern import detect_candle_patterns
from lib.utils.indicators import calculate_indicators
from lib.utils.list import map_by
from lib.utils.news import render_news_in_markdown_group_by_platform, render_news_in_markdown_group_by_time_for_each_platform
from lib.utils.number import remain_significant_digits
from lib.utils.string import escape_text_for_jinja2_temperate

SupportIndicators = List[Literal["sma", "rsi", "boll", "macd", "stoch", "atr"]]

round_to_5 = lambda x: remain_significant_digits(x, 5)

def get_ohlcv_history(symbol: str, limit=int, frame = '1d'):
    """
    获取指定symbol和时间范围的历史K线数据
    """
    if symbol.endswith('USDT'):
        return crypto.get_ohlcv_history(symbol, frame, limit=limit).data
    else:
        return ashare.get_ohlcv_history(symbol, frame, limit=limit).data
    

def format_ohlcv_list(ohlcv_list: List[Ohlcv]) -> str:
    data_for_gpt = [
        {
            "date": ohlcv.timestamp.strftime("%Y-%m-%d"),
            "open": ohlcv.open,
            "high": ohlcv.high,
            "low": ohlcv.low,
            "close": ohlcv.close,
            "volume": ohlcv.volume,
        }
        for ohlcv in ohlcv_list  # 使用最近的30个数据点
    ]
    return "\n".join(
        ["[", ",\n".join(map_by(data_for_gpt, lambda x: "    " + json.dumps(x))), "]"]
    )


def format_ohlcv_pattern(ohlcv_list: List[Ohlcv]) -> str:
    patterns = "\n".join(
        map_by(
            detect_candle_patterns(ohlcv_list)["last_candle_patterns"],
            lambda p: f"{p['name']}: {p['description']}",
        )
    )
    if patterns:
        return f"最新出现的K线形态：\n{patterns}"
    return ""


def format_indicators(
    ohlcv_list: List[Ohlcv], use_indicators: SupportIndicators, max_length=20
) -> str:
    """
    计算并格式化指定的技术指标
    :param ohlcv_list: 包含OHLCV数据的列表
    :param use_indicators: 需要计算的技术指标列表
    :return: 格式化后的技术指标文本描述
    """
    
    result_texts = []
    result = calculate_indicators(ohlcv_list=ohlcv_list, use_indicators=use_indicators)
    if "sma" in use_indicators:
        if result.sma5:
            sma5 = map_by(result.sma5.sma[-max_length:], round_to_5)
            result_texts.append(f"- 过去{len(sma5)}天5日简单移动平均线 (SMA5): {sma5}")
        if result.sma20:
            sma20 = map_by(result.sma20.sma[-max_length:], round_to_5)
            result_texts.append(
                f"- 过去{len(sma20)}天20日简单移动平均线 (SMA20): {sma20}"
            )
    if "rsi" in use_indicators and result.rsi:
        rsi_values_rounded = map_by(result.rsi.rsi[-max_length:], round_to_5)
        result_texts.append(
            f"- 过去{len(rsi_values_rounded)}天相对强弱指数 (RSI): {rsi_values_rounded}"
        )
    if "boll" in use_indicators and result.boll:
        boll = result.boll
        boll_upper = map_by(boll.upperband[-max_length:], round_to_5)
        boll_middle = map_by(boll.middleband[-max_length:], round_to_5)
        boll_lower = map_by(boll.lowerband[-max_length:], round_to_5)
        result_texts.append(f"- 过去{len(boll_upper)}天布林带上轨: {boll_upper}")
        result_texts.append(f"- 过去{len(boll_middle)}天布林带中轨: {boll_middle}")
        result_texts.append(f"- 过去{len(boll_lower)}天布林带下轨: {boll_lower}")
    if "macd" in use_indicators and result.macd:
        macd = result.macd
        macd_hist = map_by(
            macd.macdhist[-max_length:], round_to_5
        )  # 假设macdhist存储MACD柱状图数据
        result_texts.append(f"- MACD: ")
        result_texts.append(f"    - 金叉: {'是' if macd.is_gold_cross else '否'}")
        result_texts.append(f"    - 死叉: {'是' if macd.is_dead_cross else '否'}")
        result_texts.append(f"    - 趋势转好: {'是' if macd.is_turn_good else '否'}")
        result_texts.append(f"    - 趋势转坏: {'是' if macd.is_turn_bad else '否'}")
        result_texts.append(f"    - 过去{len(macd_hist)}天MACD柱状图: {macd_hist}")
    if "stoch" in use_indicators and result.stoch:
        stoch = result.stoch
        stoch_slowk = map_by(stoch.slowk[-max_length:], round_to_5)
        stoch_slowd = map_by(stoch.slowd[-max_length:], round_to_5)
        result_texts.append(
            f"- 过去{len(stoch_slowd)}天随机指标 (Stochastic Oscillator):"
        )
        result_texts.append(f"    - %K: {stoch_slowk}")
        result_texts.append(f"    - %D: {stoch_slowd}")
    if "atr" in use_indicators and result.atr:
        atr_values_rounded = map_by(result.atr.atr[-max_length:], round_to_5)
        result_texts.append(
            f"- 过去{len(atr_values_rounded)}天平均真实波幅 (ATR): {atr_values_rounded}"
        )
    if "vwma" in use_indicators and result.vwma:
        vwma = result.vwma
        vwma_values = map_by(vwma.vwma[-max_length:], round_to_5)
        result_texts.append(f"- 过去{len(vwma_values)}天成交量加权平均价 (VWMA): {vwma_values}")

    return "\n".join(result_texts)

def get_news_in_text(
    from_time: datetime,
    end_time: datetime = datetime.now(),
    platforms: List[str] = ["cointime"]
) -> str:
    news_by_platform = {
        platform: news_proxy.get_news_during(platform, from_time, end_time)
        for platform in platforms
    }
    
    return (
        render_news_in_markdown_group_by_platform(news_by_platform)
        if datetime.now() - from_time <= timedelta(hours=1)
        else render_news_in_markdown_group_by_time_for_each_platform(
            news_by_platform
        )
    )

def escape_tool_call_results(tool_call_results: List[dict]) -> List[dict]:
    """
    转义工具调用结果中的文本内容，避免Markdown解析错误
    """
    for result in tool_call_results:
        if "content" in result:
            result["content"] = escape_text_for_jinja2_temperate(result["content"])
        
    return tool_call_results