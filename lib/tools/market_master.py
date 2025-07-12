from datetime import datetime
import json
from textwrap import dedent
from typing import List, Dict, Literal, Optional, TypedDict
from dataclasses import dataclass, field
from lib.model import Ohlcv
from lib.config import API_MAX_RETRY_TIMES
from lib.adapter.exchange.crypto_exchange import BinanceExchange
from lib.modules.notification_logger import NotificationLogger
from lib.modules.trade import ashare, crypto
from lib.utils.decorators import with_retry
from lib.utils.string import extract_json_string
from lib.utils.time import hours_ago, ts_to_dt
from lib.utils.list import map_by
from lib.utils.number import remain_significant_digits
from lib.utils.candle_pattern import detect_candle_patterns
from lib.utils.indicators import (
    sma_indicator,
    rsi_indicator,
    bollinger_bands_indicator,
    macd_indicator,
    stochastic_oscillator_indicator,
    atr_indicator,
    vwma_indicator,
    calculate_indicators
)
from lib.adapter.llm import get_llm_direct_ask
from .news_helper import NewsHelper
from .ashare_stock import get_ashare_stock_info

CRYPTO_SYSTEM_PROMPT_TEMPLATE = """
你是一位经验丰富的加密货币交易专家，擅长分析市场数据、技术指标和新闻信息，现在是一个新的交易日，并按照以下过程对{coin_name}进行技术分析
1. 请分析过去30天OHLCV日线级别数据, 结合检测到的K线形态, 判断短期和长期趋势
2. 结合技术指标(如SMA、RSI、MACD、布林带等)，确认趋势强度和潜在反转信号
3. 综合考虑新闻事件和市场情绪，评估外部因素对价格的影响；
4. 回顾交易历史，结合当前仓位和风险偏好，给出具体的交易建议。

请基于提供的数据和信息，给出一个JSON格式的响应，包含下一步的行动建议（"buy"、"sell"或"hold"），具体的交易数量，以及相应的理由，JSON字段如下：
- action: "buy"（买入）, "sell"（卖出）或 "hold"（不动）
- sell_amount: (Required when action is sell) action为sell时返回卖出的{coin_name}数量，不得超过持有的{coin_name}数量
- buy_cost: (Required when action is buy) action为buy时返回花费的USDT数量, 不得超过持有的USDT数量
- reason: 做出此决定的详细分析报告，包括对各个数据和指标的分析，内容必须包括：OHLCV数据分析、技术指标分析(必须对所有给出的指标进行评价，包括SMA,RSI,BOLL,MACD,KDJ,ATR)、新闻事件分析、仓位和风险偏好分析
- summary: 用30个字左右简要概括决策理由，用于交易历史复盘

响应格式例子：
```json
Example 1:
{{
    "action": "buy",
    "buy_cost": 100.0,
    "summary": "技术指标良好且处于低位，ETF利好",
    "reason": "OHLCV分析：当前价格100.0处于近30日低位，成交量较前期增加50%；技术指标分析：SMA5(98.5)上穿SMA20(97.8)形成黄金交叉，RSI(28)处于超卖区域，布林带(上轨102.3/中轨97.8/下轨93.3)显示价格接近下轨支撑，MACD形成金叉且趋势转好，KD指标中%K(20)低于%D(35)但即将交叉，ATR(2.5)显示波动率处于低位适合建仓；新闻分析：SEC批准比特币现货ETF，机构资金大量流入，以太坊即将完成新一轮网络升级；交易历史回顾：上次在95.0价位减仓过早导致错过部分涨幅，这次应吸取教训，在技术指标和基本面共振时果断建仓；仓位分析：当前仓位较轻(30%)，风险承受能力充足，适合增加仓位。"
}}
Example 2:
{{
    "action": "sell",
    "sell_amount": 100.0,
    "summary": "技术指标超买，交易所利空消息",
    "reason": "OHLCV分析：价格突破前期高点后量能不足，近5日成交量持续萎缩；技术指标分析：SMA5(120.5)下穿SMA20(122.3)，RSI(78)处于超买区域，布林带(上轨125.6/中轨122.3/下轨119.0)显示价格触及上轨resistance，MACD形成死叉且趋势转坏，随机指标%K(85)高于%D(75)且开始向下发散，ATR(4.8)显示波动加剧风险提升；新闻分析：某大型加密货币交易所被监管机构调查，主要公链遭受安全漏洞攻击，市场恐慌情绪上升；交易历史回顾：之前两次在类似技术形态下错过减仓机会导致回撤过大，本次应及时止盈，保护既有收益；仓位分析：当前持仓占总资金70%，风险较大，建议适当减仓。"
}}
Example 3:
{{
    "action": "hold",
    "summary": "市场震荡，缺乏明确信号",
    "reason": "OHLCV分析：价格在SMA20附近小幅震荡，成交量保持平稳；技术指标分析：SMA5(110.2)与SMA20(110.5)基本平行，RSI(55)处于中性位置，布林带(上轨115.6/中轨110.5/下轨105.4)呈现横向收敛趋势，MACD无明显金叉死叉，趋势平稳，随机指标%K(45)和%D(48)在中位盘整，ATR(1.8)显示波动率较低；新闻分析：市场关注美联储议息会议，主流币种开发进展平稳，DeFi总锁仓量保持稳定；交易历史回顾：历史数据显示在震荡市频繁交易往往造成损失，保持耐心等待明确信号是更好的选择；仓位分析：当前仓位适中(50%)，风险收益比例平衡，建议继续持有。"
}}
```

注意：
1. 交易数量应该是合理的，不要花费超过仓位信息中给出的可用的USDT余额或卖出超过{coin_name}持仓量。
2. 买入消耗不得低于5USDT，卖出的币总价值不得低于5USDT，避免资金量过低引起的交易失败
3. 交易偏好：我是一名{risk_prefer}投资者
4. 交易策略：我倾向于{strategy_prefer}策略
"""

ASHARE_SYSTEM_PROMPT_TEMPLATE = """
你是一位经验丰富的A股市场交易专家，擅长分析市场数据、技术指标和新闻信息，现在是一个新的交易日，请按照以下过程对股票或ETF进行技术分析并给出交易建议：

1. 请分析过去30天OHLCV日线级别数据，判断短期和长期趋势，注意A股市场的特点（如涨跌停限制）
2. 结合技术指标(如SMA、RSI、MACD、布林带等)，确认趋势强度和潜在反转信号
3. 综合考虑相关政策和新闻事件对股价的影响
4. 回顾交易历史，结合当前仓位和风险偏好，给出具体的交易建议

请基于提供的数据和信息，给出一个JSON格式的响应，包含下一步的行动建议（"buy"、"sell"或"hold"），具体的交易数量，以及相应的理由，JSON字段如下：
- action: 取值只有三种情况："buy"（买入）, "sell"（卖出）或 "hold"（不动）
- lots: (Required when action is buy/sell) 交易手数，必须是整数，1手=100股
- reason: 做出此决定的详细分析报告，必须是字符串，必须包括：
    1. OHLCV数据分析（包括成交量、换手率分析）
    2. 技术指标分析（必须对所有指标进行评价：SMA,RSI,BOLL,MACD,KDJ,ATR）
    3. 市场环境分析（大盘走势、板块表现、北向资金）
    4. 消息面分析（政策、行业新闻、公司公告等）
    5. 仓位和风险偏好分析
- summary:  用30个字左右简要概括决策理由，用于交易历史复盘

响应格式例子：
```json
Example 1:
{{
    "action": "buy",
    "lots": 100,
    "summary": "大盘企稳回升，北向资金流入，ETF技术指标良好",
    "reason": "OHLCV分析：当前价格3.15元处于近30日低位，成交量较前期增加30%，换手率维持在2%以上；技术指标分析：SMA5(3.18)上穿SMA20(3.12)形成黄金交叉，RSI(42)处于中位偏低，布林带(上轨3.35/中轨3.12/下轨2.89)显示价格在中轨附近，MACD形成金叉，KD指标中%K(35)低于%D(42)但即将交叉，ATR(0.08)显示波动率处于低位；市场环境：上证指数突破3200点，成交量放大，北向资金连续3日净流入，科技板块整体走强；消息面：国务院发布支持科技创新政策，行业利好明显；交易历史回顾：上次3.05元减仓过早，本次技术面和基本面共振时应适度加仓；仓位分析：当前仓位30%，建议加仓至50%，买入100手。"
}}
Example 2:
{{
    "action": "sell",
    "lots": 150,
    "summary": "大盘调整，板块走弱，降低仓位规避风险",
    "reason": "OHLCV分析：股价突破前期高点3.85元后量能不足，5日成交量持续萎缩，换手率降至1%以下；技术指标分析：SMA5(3.82)下穿SMA20(3.75)，RSI(72)处于超买区域，布林带(上轨3.88/中轨3.75/下轨3.62)显示价格触及上轨，MACD形成死叉，KDJ指标%K(85)高于%D(78)且开始向下，ATR(0.12)显示波动加大；市场环境：上证指数连续3日下跌，两市成交量萎缩，北向资金转为净流出，行业板块普跌；消息面：监管层表态防范市场风险，央行货币政策边际收紧；交易历史回顾：前期高位未能及时减仓导致回撤，本次应及时止盈；仓位分析：当前持仓占比70%，建议降至30%，卖出150手。"
}}
Example 3:
{{
    "action": "hold",
    "summary": "市场震荡整理，缺乏明确信号，维持现有仓位",
    "reason": "OHLCV分析：价格在20日均线附近震荡整理，成交量温和，换手率保持稳定；技术指标分析：SMA5(3.45)与SMA20(3.42)基本平行，RSI(52)处于中性位置，布林带(上轨3.58/中轨3.42/下轨3.26)呈现横向收敛，MACD无明显金叉死叉，KDJ指标在50轴附近交织，ATR(0.06)显示波动率较低；市场环境：上证指数横盘整理，市场成交量平稳，北向资金小幅波动，行业景气度稳定；消息面：无重大利空利好消息；交易历史回顾：震荡市保持仓位稳定收益最佳；仓位分析：当前仓位50%，风险收益平衡，维持现有仓位。"
}}
注意：
    1. 买入和卖出都必须以"手"为单位（1手=100股），lots字段必须是整数
    2. 交易手数数量不得超过可买手数或可卖手数
    3. 交易偏好：我是一名{risk_prefer}投资者
    4. 交易策略：我倾向于{strategy_prefer}策略
    5. 务必输出JSON格式的回复
    6. A股市场新闻通常"报喜不报忧"，注意甄别有价值的利好信息，关注利空消息的负面影响
"""


class JsonReplyError(Exception): ...


@dataclass(frozen=True)
class AgentAdvice:
    action: Literal["buy", "sell", "hold"]
    reason: str
    summary: str
    price: float

    buy_cost: Optional[float] = None
    sell_amount: Optional[float] = None


AccountInfo = Dict[Literal["free", "hold_amount"], float]
SupportIndicators = List[Literal["sma", "rsi", "boll", "macd", "stoch", "atr"]]
TradeLog = TypedDict(
    "TradeLog ",
    {
        "timestamp": int,  # UTC 时间戳，单位是ms
        "action": Literal["buy", "sell"],
        "sell_amount": float,  # sell时必填
        "buy_cost": float,  # buy时必填
        "price": float,  # 交易价格
        "position_ratio": float,  # buy或sell时必填，代表调整后的仓位比例
        "summary": str,  # 一段简短的总结，hold也是必填的
    },
)
TradeHistoryList = List[TradeLog]


@dataclass
class TradeContext:
    symbol: str
    account_info: AccountInfo

    trade_history: TradeHistoryList
    curr_time: datetime = field(default_factory=datetime.now)
    curr_price: Optional[float] = None
    ohlcv_list: Optional[List[Ohlcv]] = None


round_to_5 = lambda x: remain_significant_digits(x, 5)


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


def format_crypto_account_info(account_info: AccountInfo, price: float) -> str:
    free = round_to_5(account_info["free"])
    hold_amount = round_to_5(account_info["hold_amount"])
    hold_val = round_to_5(account_info["hold_amount"] * price)
    return dedent(
        f"""
    - USDT余额: {free}
    - 持仓量: {hold_amount} (价值约 {hold_val} USDT)
    """
    )


def format_crypto_history(history: TradeHistoryList) -> str:
    def format_trade_record(trade: TradeLog):
        action = trade["action"].lower()
        timestamp = ts_to_dt(trade["timestamp"]).strftime("%Y-%m-%d")
        amount = trade.get("sell_amount")
        cost = trade.get("buy_cost")
        position_ratio = int(trade["position_ratio"] * 100)
        summary = trade["summary"]
        if action == "buy":
            buy_amount = cost / trade["price"]
            return f"- {timestamp} 花费{round_to_5(cost)}USDT买入{round_to_5(buy_amount)}份, 仓位{round_to_5(position_ratio)}%, 理由：{summary}"
        else:
            return f"- {timestamp} 卖出{round_to_5(amount)}份, 仓位{round_to_5(position_ratio)}%, 理由：{summary}"

    return (
        "\n".join(format_trade_record(trade) for trade in history)
        if history
        else "暂无交易历史"
    )


def format_binance_future_info(
    global_long_short_account: float,
    top_long_short_account: float,
    top_long_short_amount: float,
    future_rate: float,
) -> str:
    return dedent(
        f"""
    - 多空持仓人数比：{global_long_short_account}
    - 大户账户数多空比: {top_long_short_account}
    - 大户持仓量多空比: {top_long_short_amount}
    - 资金费率：{future_rate}
    """
    )


def construct_crypto_user_prompt(
    coin_name: str,
    ohlcv: str,
    indicators: str,
    pattern: str,
    position: str,
    trade_history: str,
    future_info: str,
    news: str,
) -> str:
    no = 1
    user_prompt = ["分析以下加密货币的信息，并给出交易建议："]
    user_prompt.append(f"{no}. 最近30天的OHLCV数据:")
    user_prompt.append(ohlcv)
    user_prompt.append("\n")
    if pattern:
        user_prompt.append(pattern)
        user_prompt.append("\n")
    no += 1
    if indicators:
        user_prompt.append(f"{no}. 过去一段时间的技术指标:")
        user_prompt.append(indicators)
        user_prompt.append("\n")
        no += 1
    if news:
        user_prompt.append(f"{no}. 过去24h内最新相关新闻")
        user_prompt.append(f"```\n{news}\n```")
        user_prompt.append("\n")
        no += 1
    if future_info:
        user_prompt.append(f"{no}. 币安交易所{coin_name}此刻的U本位合约数据")
        user_prompt.append(future_info)
        user_prompt.append("\n")
        no += 1
    user_prompt.append(f"{no}. 当前仓位信息:")
    user_prompt.append(position)
    user_prompt.append("\n")
    no += 1
    if trade_history:
        user_prompt.append(f"{no}. 最近10次以内交易历史:")
        user_prompt.append(trade_history)
        user_prompt.append("\n")
    no += 1
    user_prompt.append("请根据这些信息分析市场趋势，并给出具体的交易建议。")
    return "\n".join(user_prompt)


def validate_crypto_advice(
    advice: str, max_cost: float, max_sell_amount: float
) -> Dict:
    try:
        advice_json = extract_json_string(advice)
        assert isinstance(advice_json, dict), "GPT回复必须是一个字典格式"
        assert "action" in advice_json, "GPT回复缺少'action'字段"
        assert advice_json["action"] in [
            "buy",
            "sell",
            "hold",
        ], f"无效的action值: {advice_json['action']}, 必须是'buy'/'sell'/'hold'之一"
        assert "reason" in advice_json, "GPT回复缺少'reason'字段"
        assert isinstance(advice_json["reason"], str), "'reason'字段必须是字符串类型"
        if advice_json["action"] != "hold":
            assert (
                "summary" in advice_json
            ), f"{advice_json['action']}操作必须包含'summary'字段"
        if advice_json["action"] == "buy":
            assert "buy_cost" in advice_json, "买入操作缺少'buy_cost'字段"
            assert isinstance(
                advice_json["buy_cost"], (int, float)
            ), "'buy_cost'字段必须是浮点数类型"
            assert advice_json["buy_cost"] > 0, "'buy_cost'必须大于0"
            assert (
                advice_json["buy_cost"] <= max_cost
            ), f"买入金额{advice_json['buy_cost']}超过可用余额{max_cost}"
        elif advice_json["action"] == "sell":
            assert "sell_amount" in advice_json, "卖出操作缺少'sell_amount'字段"
            assert isinstance(
                advice_json["sell_amount"], (int, float)
            ), "'sell_amount'字段必须是浮点数类型"
            assert advice_json["sell_amount"] > 0, "'sell_amount'必须大于0"
            # assert advice_json['amount'] <= max_sell_amount, f"卖出数量{advice_json['amount']}超过持仓数量{max_sell_amount}"
            if advice_json["sell_amount"] > max_sell_amount:
                advice_json["sell_amount"] = max_sell_amount
        return advice_json
    except Exception as err:
        raise JsonReplyError(err)


def format_ashare_account_info(account_info: AccountInfo, price: float) -> str:
    free = account_info["free"]
    hold_lots = account_info["hold_amount"] // 100
    hold_val = round_to_5(hold_lots * 100 * price)
    max_lots_can_buy = int(free / price // 100)
    return f"""
        - 可用资金: {free}RMB (可买{max_lots_can_buy}手)
        - 持有： {hold_lots}手 (价值约 {hold_val}RMB)
    """


def format_ashare_history(history: TradeHistoryList) -> str:
    def format_trade_record(trade: TradeLog):
        action = trade["action"].lower()
        timestamp = ts_to_dt(trade["timestamp"]).strftime("%Y-%m-%d")

        position_ratio = int(trade["position_ratio"] * 100)
        summary = trade["summary"]
        if action == "buy":
            cost = trade.get("buy_cost")
            buy_lots = int(cost / trade["price"] // 100)
            return f"- {timestamp} 花费{round_to_5(cost)}RMB买入{buy_lots}手, 仓位{position_ratio}%, 理由：{summary}"
        else:
            sell_lots = int(trade.get("sell_amount") // 100)
            return f"- {timestamp} 卖出{sell_lots}手, 仓位{position_ratio}%, 理由：{summary}"

    return (
        "\n".join(format_trade_record(trade) for trade in history)
        if history
        else "暂无交易历史"
    )


def construct_ashare_user_prompt(
    stock_name: str,
    ohlcv_text: str,
    indicators_text: str,
    pattern_text: str,
    position: str,
    trade_history: str,
    news: str,
) -> str:
    no = 1
    user_prompt = [f"分析以下关于{stock_name}的信息，并给出交易建议："]
    user_prompt.append(f"{no}. 最近30天的OHLCV数据:")
    user_prompt.append(ohlcv_text)
    user_prompt.append("\n")
    if pattern_text:
        user_prompt.append(pattern_text)
        user_prompt.append("\n")
    no += 1
    if indicators_text:
        user_prompt.append(f"{no}. 过去一段时间的技术指标:")
        user_prompt.append(indicators_text)
        user_prompt.append("\n")
    no += 1
    if news:
        user_prompt.append(f"{no}. 过去24h内最新相关新闻")
        user_prompt.append(f"```\n{news}\n```")
        user_prompt.append("\n")
    no += 1
    user_prompt.append(f"{no}. 当前仓位信息:")
    user_prompt.append(position)
    user_prompt.append("\n")
    no += 1
    if trade_history:
        user_prompt.append(f"{no}. 最近10次以内交易历史:")
        user_prompt.append(trade_history)
        user_prompt.append("\n")
    no += 1
    user_prompt.append("请根据这些信息分析市场趋势，并给出具体的交易建议。")
    return "\n".join(user_prompt)


def validate_ashare_advice(advice: str, max_buy_lots: float, max_sell_lots: float):
    try:
        advice_json = extract_json_string(advice)
        assert isinstance(advice_json, dict), "GPT回复必须是一个字典格式"
        assert "action" in advice_json, "GPT回复缺少'action'字段"
        assert advice_json["action"] in [
            "buy",
            "sell",
            "hold",
        ], f"无效的action值: {advice_json['action']}, 必须是'buy'/'sell'/'hold'之一"
        assert "reason" in advice_json, "GPT回复缺少'reason'字段"
        assert isinstance(advice_json["reason"], str), "'reason'字段必须是字符串类型"
        if advice_json["action"] != "hold":
            assert (
                "summary" in advice_json
            ), f"{advice_json['action']}操作必须包含'summary'字段"
        if advice_json["action"] in ["buy", "sell"]:
            assert "lots" in advice_json, "缺少'lots'字段"
            assert isinstance(advice_json["lots"], int), "'lots'字段必须是整数类型"
            assert advice_json["lots"] > 0, "'lots'必须大于0"

            if advice_json["action"] == "buy":
                if advice_json["lots"] > max_buy_lots:
                    advice_json["lots"] = max_buy_lots
            if advice_json["action"] == "sell":
                if advice_json["lots"] > max_sell_lots:
                    advice_json["lots"] = max_sell_lots

        return advice_json
    except Exception as err:
        raise JsonReplyError(err)


@dataclass
class MarketMaster:

    def __init__(
        self,
        risk_prefer: str = "风险厌恶型",
        strategy_prefer: str = "中长期投资",
        use_indicators: SupportIndicators = [
            "sma",
            "rsi",
            "boll",
            "macd",
            "stoch",
            "atr",
        ],
        detect_ohlcv_pattern: bool = True,
        use_crypto_future_info: bool = True,
        llm_provider: str = "paoluz",
        model: str = "deepseek-v3",
        temperature: float = 0.2,
        news_helper: NewsHelper = None,
        msg_logger: Optional[NotificationLogger] = None,
    ):
        self.risk_prefer = risk_prefer
        self.strategy_prefer = strategy_prefer
        self.use_indicators = use_indicators
        self.detect_ohlcv_pattern = detect_ohlcv_pattern
        self.use_crypto_future_info = use_crypto_future_info
        self.llm_provider = llm_provider
        self.model = model
        self.temperature = temperature
        self.msg_logger = msg_logger
        self.binance_exchange = BinanceExchange(future_mode=True)
        self.news_helper = news_helper or NewsHelper()

    def give_trade_adevice(self, ctx: TradeContext) -> AgentAdvice:
        return (
            self.give_crypto_trade_advice(ctx)
            if "USDT" in ctx.symbol
            else self.give_ashare_trade_advice(ctx)
        )

    def give_crypto_trade_advice(self, ctx: TradeContext) -> AgentAdvice:
        coin_name = ctx.symbol.rstrip("USDT").rstrip("/")
        future_symbol = f"{coin_name}USDT"
        if not ctx.ohlcv_list:
            ctx.ohlcv_list = crypto.get_ohlcv_history(
                ctx.symbol, frame="1d", limit=65
            ).data
        ohlcv_text = format_ohlcv_list(ctx.ohlcv_list[-30:])
        curr_price = ctx.curr_price or crypto.get_current_price(ctx.symbol)
        detected_patterns_text = ""
        if self.detect_ohlcv_pattern and len(ctx.ohlcv_list) > 5:
            detected_patterns_text = format_ohlcv_pattern(ctx.ohlcv_list[-30:])
        indicators_text = format_indicators(ctx.ohlcv_list, self.use_indicators)
        account_info_text = format_crypto_account_info(ctx.account_info, curr_price)
        history_text = format_crypto_history(ctx.trade_history[-10:])
        future_info_text = (
            format_binance_future_info(
                global_long_short_account=self.binance_exchange.get_u_base_global_long_short_account_ratio(
                    future_symbol, "15m", hours_ago(1)
                )[
                    -1
                ][
                    "longShortRatio"
                ],
                top_long_short_account=self.binance_exchange.get_u_base_top_long_short_account_ratio(
                    future_symbol, "15m", hours_ago(1)
                )[
                    -1
                ][
                    "longShortRatio"
                ],
                top_long_short_amount=self.binance_exchange.get_u_base_top_long_short_ratio(
                    future_symbol, "15m", hours_ago(1)
                )[
                    -1
                ][
                    "longShortRatio"
                ],
                future_rate=self.binance_exchange.get_latest_futures_price_info(
                    future_symbol
                )["lastFundingRate"],
            )
            if self.use_crypto_future_info
            else ""
        )
        system_prompt = CRYPTO_SYSTEM_PROMPT_TEMPLATE.format(
            coin_name=coin_name,
            risk_prefer=self.risk_prefer,
            strategy_prefer=self.strategy_prefer,
        )
        user_prompt = construct_crypto_user_prompt(
            coin_name,
            ohlcv_text,
            indicators_text,
            detected_patterns_text,
            account_info_text,
            history_text,
            future_info_text,
            news=self.news_helper.summary_crypto_news(
                coin_name, ctx.ohlcv_list[-1].timestamp, ctx.curr_time, ["cointime"]
            ),
        )
        if self.msg_logger:
            self.msg_logger.msg(user_prompt)
        llm_ask = get_llm_direct_ask(
            system_prompt,
            self.llm_provider,
            self.model,
            temperature=self.temperature,
            response_format='json_object'
        )

        @with_retry((JsonReplyError), API_MAX_RETRY_TIMES)
        def retryable():
            rsp = validate_crypto_advice(
                llm_ask(user_prompt),
                ctx.account_info["free"],
                ctx.account_info["hold_amount"],
            )
            valid_keys = {"action", "reason", "summary", "buy_cost", "sell_amount"}
            filtered_rsp = {k: v for k, v in rsp.items() if k in valid_keys}
            filtered_rsp["price"] = curr_price
            return AgentAdvice(**filtered_rsp)

        return retryable()

    def give_ashare_trade_advice(self, ctx: TradeContext) -> AgentAdvice:
        if ctx.ohlcv_list is None:
            ctx.ohlcv_list = ashare.get_ohlcv_history(
                ctx.symbol, frame="1d", limit=65
            ).data
        stock_info = get_ashare_stock_info(ctx.symbol)
        ohlcv_text = format_ohlcv_list(ctx.ohlcv_list[-30:])
        detected_patterns_text = (
            format_ohlcv_pattern(ctx.ohlcv_list) if self.detect_ohlcv_pattern else ""
        )
        indicators_text = format_indicators(ctx.ohlcv_list, self.use_indicators)
        current_price = ctx.curr_price or ashare.get_current_price(ctx.symbol)
        account_info_text = format_ashare_account_info(ctx.account_info, current_price)
        history_text = format_ashare_history(ctx.trade_history[-10:])
        system_prompt = ASHARE_SYSTEM_PROMPT_TEMPLATE.format(
            risk_prefer=self.risk_prefer, strategy_prefer=self.strategy_prefer
        )
        user_prompt = construct_ashare_user_prompt(
            stock_name=stock_info["stock_name"],
            ohlcv_text=ohlcv_text,
            indicators_text=indicators_text,
            pattern_text=detected_patterns_text,
            position=account_info_text,
            trade_history=history_text,
            news=self.news_helper.summary_ashare_news(
                ctx.symbol,
                ctx.ohlcv_list[-1].timestamp,
                ctx.curr_time,
                ["caixin", "eastmoney"],
            ),
        )
        if self.msg_logger:
            self.msg_logger.msg(user_prompt)
        llm_ask = get_llm_direct_ask(
            system_prompt,
            self.llm_provider,
            self.model,
            temperature=self.temperature,
            response_format='json_object'
        )

        @with_retry((JsonReplyError), API_MAX_RETRY_TIMES)
        def retryable():
            llm_rsp = llm_ask(user_prompt)
            if self.msg_logger:
                self.msg_logger.msg(llm_rsp)
            rsp = validate_ashare_advice(
                llm_rsp,
                int(ctx.account_info["free"] / current_price // 100),
                int(ctx.account_info["hold_amount"] // 100),
            )
            valid_keys = {"action", "reason", "summary", "lots"}
            filtered_rsp = {k: v for k, v in rsp.items() if k in valid_keys}
            if filtered_rsp.get("action") == "buy":
                filtered_rsp["buy_cost"] = filtered_rsp["lots"] * 100 * current_price
                del filtered_rsp["lots"]
            elif filtered_rsp.get("action") == "sell":
                filtered_rsp["sell_amount"] = filtered_rsp["lots"] * 100
                del filtered_rsp["lots"]
            elif "lots" in filtered_rsp:
                del filtered_rsp["lots"]
            filtered_rsp["price"] = current_price
            return AgentAdvice(**filtered_rsp)

        return retryable()


__all__ = ["MarketMaster", "AshareContext", "TradeContext", "AgentAdvice"]
