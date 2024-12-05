from dataclasses import dataclass
from datetime import datetime
from typing import Any, List, Literal, Optional, TypedDict, Union
import abc

import akshare as ak
import pandas as pd
import requests
import g4f
import aiohttp

from ...model import Ohlcv, Order
from ...logger import logger
from ...config import API_MAX_RETRY_TIMES
from ...utils.list import map_by
from ...utils.decorators import with_retry
from ...utils.string import extract_json_string, hash_str
from ...utils.time import dt_to_ts, ts_to_dt
from ...utils.ohlcv import detect_candle_patterns, PatternCalulationResults
from ...utils.number import mean
from ...utils.news import render_news_in_markdown_group_by_platform, NewsInfo
from ...adapter.news import NewsFetcherApi
from ...adapter.database.session import SessionAbstract
from ...adapter.gpt import GptAgentAbstract, get_agent_by_model
from ...adapter.database.kv_store import KeyValueStore
from ...modules.exchange_proxy import cn_market, ExchangeOperationProxy
from ...modules.notification_logger import NotificationLogger
from ...modules.news_proxy import news_proxy
from ...modules.strategy import BasicDependency, ParamsBase, BasicContext

from ...strategys.common import get_recent_data_with_at_least_count
from ...strategys.gpt_powerd.common import calculate_technical_indicators, TechnicalIndicators, format_ohlcv_list, OperationRecord, round_to_5, GptReplyNotValid

ContextDict = TypedDict('Context', {
    'account_money_amount': float,
    'account_symbol_amount': float,
    'operation_history': List[OperationRecord]
})

def format_operation_record(record: OperationRecord) -> str:
    date_str = ts_to_dt(record['timestamp']).strftime('%Y-%m-%d')
    action_desc = {
        'buy': f"买入{round_to_5(record['amount'])}",
        'sell': f"卖出{round_to_5(record['amount'])}"
    }[record['action']]
    
    return f"- {date_str} {action_desc}, 仓位{int(record['position_ratio']*100)}%, 原因: {record['summary']}"

@dataclass
class Params(ParamsBase):
    risk_prefer: str
    strategy_prefer: str

def is_etf(symbol: str):
    return symbol.startswith(('51', '15', '16'))

SymbolInfo = TypedDict('SymbolInfo', {
    'name': str,
    # 'description': str,
    'business': Optional[str], # 所属行业
})

GptAdviceDict = Union[
    TypedDict('GptAdviceDictBuy', {
        "action": Literal["buy"],
        "lots": int,
        "summary": str,
        "reason": str
    }),
    TypedDict('GptAdviceDictSell', {
        "action": Literal["sell"],
        "amount": float,
        "summary": str,
        "reason": str
    }),
    TypedDict('GptAdviceDictHold', {
        "action": Literal["hold"],
        "reason": str
    }),
]

def validate_gpt_advice(advice: str, max_buy_lots: float, max_sell_lots: float) -> GptAdviceDict:
    try:
        advice_json = extract_json_string(advice)
        assert isinstance(advice_json, dict), "GPT回复必须是一个字典格式"
        assert 'action' in advice_json, "GPT回复缺少'action'字段"
        assert advice_json['action'] in ['buy', 'sell', 'hold'], f"无效的action值: {advice_json['action']}, 必须是'buy'/'sell'/'hold'之一"
        assert 'reason' in advice_json, "GPT回复缺少'reason'字段"
        assert isinstance(advice_json['reason'], str), "'reason'字段必须是字符串类型"
        if advice_json['action'] != 'hold':
            assert 'summary' in advice_json, f"{advice_json['action']}操作必须包含'summary'字段"
        if advice_json['action'] in ['buy', 'sell']:
            assert 'lots' in advice_json, "缺少'lots'字段"
            assert isinstance(advice_json['lots'], int), "'lots'字段必须是整数类型"
            assert advice_json['lots'] > 0, "'lots'必须大于0"

            if advice_json['action'] == 'buy':
                assert advice_json['lots'] <= max_buy_lots, f"买入手数超过最大可买手数"
            if advice_json['action'] == 'sell':
                assert advice_json['lots'] <= max_sell_lots, f"卖出手数超过最大可买手数"

        return advice_json
    except Exception as err:
        raise GptReplyNotValid(err)

class OhterDataFetcherApi(abc.ABC):
    @abc.abstractmethod
    def get_symbol_information(self, symbol: str) -> SymbolInfo:
        pass

    @abc.abstractmethod
    def get_symbol_news(self, symbol: str, filter_after: datetime) -> List[NewsInfo]:
        pass 

    @abc.abstractmethod
    def is_business_day(self) -> bool:
        pass

class OtherDataFetcher(OhterDataFetcherApi):

    def __init__(self, session: SessionAbstract):
        self.session = session
        self.kv_store = KeyValueStore(session)

    def is_business_day(self) -> bool:
        if datetime.now().weekday() >= 5:
            return False
        this_year = datetime.now().strftime('%Y')
        today = datetime.now().strftime('%Y-%m-%d')
        with self.session:
            cache_key = f"{this_year}_china_holiday"
            holiday_list: List[str] | None= self.kv_store.get(cache_key)
            if holiday_list is None:
                holiday_list = list(requests.get(f"https://api.jiejiariapi.com/v1/holidays/{this_year}").json().keys())
                self.kv_store.set(cache_key, holiday_list)
                self.session.commit()
            return today not in holiday_list

    @with_retry((requests.exceptions.ConnectionError), API_MAX_RETRY_TIMES)
    def get_symbol_information(self, symbol: str) -> SymbolInfo:
        if is_etf(symbol):
            df = ak.fund_name_em()
            return {
                'name': df['基金简称'].loc[df['基金代码'] == symbol].iloc[0]
            }
        else:
            df = ak.stock_individual_info_em(symbol)
            return {
                'business': df['value'].loc[df['item'] == '行业'].iloc[0],
                'name': df['value'].loc[df['item'] == '股票简称'].iloc[0],
            }

    @with_retry((requests.exceptions.ConnectionError), API_MAX_RETRY_TIMES)
    def get_symbol_news(self, symbol: str, filter_after: datetime) -> List[NewsInfo]:
        news_100_df = ak.stock_news_em(symbol=symbol)

        news_100_df['发布时间'] = pd.to_datetime(news_100_df['发布时间'])

        # 过滤出指定datetime之前的行
        filtered_df = news_100_df[news_100_df['发布时间'] >= filter_after]

        news_info_list = []
        for _, row in filtered_df.iterrows():
            news_info = NewsInfo(
                title=row['新闻标题'], 
                timestamp=row['发布时间'],
                description=row['新闻内容'], 
                news_id = hash_str(row['新闻标题']),
                url = row['新闻链接'],
                platform = 'eastmoney'
            )
            news_info_list.append(news_info)

        return news_info_list


class Dependency(BasicDependency):
    def __init__(
            self,
            news_api: NewsFetcherApi = news_proxy,
            decision_voters_gpt_agents: List[GptAgentAbstract] = [get_agent_by_model('Baichuan3-Turbo')],
            notification: NotificationLogger = None, 
            exchange: ExchangeOperationProxy = None, 
            session: SessionAbstract = None,
            other_data_api: OhterDataFetcherApi = None
        ):
        super().__init__(notification = notification, exchange=exchange or cn_market, session=session)
        self.news = news_api
        self.other_data_api = other_data_api or OtherDataFetcher(self.session)
        self.voter_gpt_agents = decision_voters_gpt_agents
        self._curr_voter_idx = 0

    def get_a_voter_gpt(self) -> GptAgentAbstract:
        res = self.voter_gpt_agents[self._curr_voter_idx]
        self._curr_voter_idx = (self._curr_voter_idx + 1) % len(self.voter_gpt_agents)
        return res

class Context(BasicContext[ContextDict]):
    deps: Dependency

    def __init__(self, params: Params, deps: Dependency):
        super().__init__(f'{params.symbol}_{params.money}_{params.data_frame}_CN_GPT', deps)
        self.params = params

    def _initial_context(self) -> ContextDict:
        return {
            'account_money_amount': self.params.money,
            'account_symbol_amount': 0,
            'operation_history': []
        }

    def buy(self, lots: int, price: int, summary: str):
        order = self.deps.exchange.create_order(self.params.symbol, 'market', 'buy', f'CN_GPT_PLAN_{self.params.symbol}', price=price, amount=lots * 100, comment=summary)
        self.increate('account_symbol_amount', order.get_amount(True))
        self.decreate('account_money_amount', order.get_cost(True))
        self.append('operation_history', construct_operation(self, order, summary))
        self.deps.notification_logger.msg(f'{order.timestamp} 花费', order.get_cost(True), '元买入', order.get_amount(True), '份')
        return

    def sell(self, lots: float, price: int, summary: str):
        order = self.deps.exchange.create_order(self.params.symbol, 'market', 'sell', f'CN_GPT_PLAN_{self.params.symbol}', price=price, amount=lots * 100, comment=summary)
        self.increate('account_money_amount', order.get_cost(True))
        self.decreate('account_symbol_amount', order.get_amount(True))
        self.append('operation_history', construct_operation(self, order, summary))
        self.deps.notification_logger.msg(f'{order.timestamp} 卖出', order.get_amount(True), '份得到', order.get_cost(True), '元')


def construct_operation(context: Context, order: Order, reason: str) -> OperationRecord:
    return {
        'timestamp': dt_to_ts(order.timestamp),
        'price': order.price,
        'action': order.side,
        'amount': order.get_amount(True),
        'cost': order.get_cost(True),
        'position_ratio': context.get('account_symbol_amount') * order.price / (context.get('account_symbol_amount') * order.price + context.get('account_money_amount')),
        'summary': reason,
        'remaining_money': context.get('account_money_amount'),
        'remaining_symbol': context.get('account_symbol_amount')
    }

# TODO: 加入大盘指数走势/行业板块整体表现/北向资金流向（ak.stock_hsgt_fund_flow_summary_em）
def construct_gpt_question(
        data: List[Ohlcv], 
        symbol: str,
        symbol_info: SymbolInfo,
        indicator: TechnicalIndicators, 
        pattern_info: PatternCalulationResults, 
        news_text: str,
        available_money: float,
        available_stock: float,
        cur_price: float, 
        max_lots: int,
        history: List[Any]
    ) -> str:
    fresh_pattern_text = '\n'.join(map_by(pattern_info['last_candle_patterns'], lambda p: f"{p['name']}: {p['description']}"))
    ohlcv_len = 30
    ohlcv_text = format_ohlcv_list(data, ohlcv_len)
    history_text = '\n'.join(map_by(history, format_operation_record)) or '暂无交易历史'
    symbol_type = 'ETF' if is_etf(symbol) else '股票'
    symbol_business = symbol_info['business'] if symbol_info.get('business') else ''
    return f"""
分析以下关于“{symbol_info['name']}({symbol})”这支{symbol_business}{symbol_type}的信息，并给出交易建议：

1. 最近{ohlcv_len}天的OHLCV数据:
{ohlcv_text}
{f"出现技术形态:{fresh_pattern_text}" if fresh_pattern_text else ""}
2. 过去一段时间的技术指标:
- 过去{len(indicator.sma5)}天5日简单移动平均线 (SMA5): {indicator.sma5}
- 过去{len(indicator.sma20)}天20日简单移动平均线 (SMA20): {indicator.sma20}
- 过去{len(indicator.rsi)}天相对强弱指标 (RSI): {indicator.rsi}
- 布林带 (Bollinger Bands):
    - 过去{len(indicator.bollinger_upper)}天上轨: {indicator.bollinger_upper}
    - 过去{len(indicator.bollinger_middle)}天中轨: {indicator.bollinger_middle}
    - 过去{len(indicator.bollinger_lower)}天下轨: {indicator.bollinger_lower}
- MACD:
    - 金叉: {'是' if indicator.is_macd_gold_cross else '否'}
    - 死叉: {'是' if indicator.is_macd_dead_cross else '否'}
    - 趋势转好: {'是' if indicator.is_macd_turn_good else '否'}
    - 趋势转坏: {'是' if indicator.is_macd_turn_bad else '否'}
    - 过去{len(indicator.macd_histogram)}天的MACD柱状图: {indicator.macd_histogram}
- 过去{len(indicator.stoch_d)}天随机指标 (Stochastic Oscillator):
    - %K: {indicator.stoch_k}
    - %D: {indicator.stoch_d}
- 过去{len(indicator.atr)}天平均真实范围 (ATR): {indicator.atr}

3. 过去24h内最新相关新闻:
```
{news_text}
```

5. 当前仓位信息:
- 余额: {available_money}RMB (最多可买{max_lots}手)
- 持仓量: {available_stock} (价值约{cur_price * available_stock}RMB，可卖{available_stock / 100}手)

6. 最近10次以内交易历史
{history_text} 

请根据这些信息分析市场趋势，并给出具体的交易建议。
"""

def construct_system_prompt(risk_prefer: str, strategy_prefer: str) -> str:
    return f"""
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
- summary: (Required when action is buy/sell) 用30个字左右简要概括交易理由，用于交易历史复盘

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
    "reason": "OHLCV分析：价格在20日均线附近震荡整理，成交量温和，换手率保持稳定；技术指标分析：SMA5(3.45)与SMA20(3.42)基本平行，RSI(52)处于中性位置，布林带(上轨3.58/中轨3.42/下轨3.26)呈现横向收敛，MACD无明显金叉死叉，KDJ指标在50轴附近交织，ATR(0.06)显示波动率较低；市场环境：上证指数横盘整理，市场成交量平稳，北向资金小幅波动，行业景气度稳定；消息面：无重大利空利好消息；交易历史回顾：震荡市保持仓位稳定收益最佳；仓位分析：当前仓位50%，风险收益平衡，维持现有仓位。"
}}
注意：
    1. 买入和卖出都必须以"手"为单位（1手=100股），lots字段必须是整数
    2. 交易手数数量不得超过可买手数或可卖手数
    3. 交易偏好：我是一名{risk_prefer or "风险厌恶型"}投资者
    4. 交易策略：我倾向于{strategy_prefer or "中长期投资"}策略
    5. 务必输出JSON格式的回复
"""

gpt_retry_decorator = with_retry((GptReplyNotValid, g4f.errors.RetryProviderError, g4f.errors.RateLimitError, g4f.errors.ResponseError, g4f.errors.ResponseStatusError, aiohttp.ClientResponseError), 3)

@gpt_retry_decorator
def gpt_analysis(context: Context, sys_prompt: str, req_prompt: str, max_lots: int) -> GptAdviceDict:
    agent = context.deps.get_a_voter_gpt()
    agent.set_system_prompt(sys_prompt)
    gpt_reply = agent.ask(req_prompt)
    context.deps.notification_logger.msg("\n" + f"=========={agent.model}=============" + "\n" + f"{gpt_reply}")
    return validate_gpt_advice(gpt_reply, max_lots, context.get('account_symbol_amount') / 100)

@gpt_retry_decorator
def gpt_news_summary(context: Context, news_text: str, symbol_info: SymbolInfo, symbol: str):
    agent = context.deps.get_a_voter_gpt()
    agent.set_system_prompt(f"""
你是一位资深的投资新闻分析师，擅长总结和分析A股市场新闻。
请总结不同平台获取到的新闻，特别关注对"{symbol_info['name']}({symbol})"这只{symbol_info.get('business', '')}{'ETF' if is_etf(symbol) else '股票'}有影响的内容：
1. 提取出对{symbol_info['name']}有影响的新闻，包括：
    - 市场动态
    - 政策变化
    - 国际局势
    - 宏观经济数据
    - 大盘的行情
    - {symbol_info['name']}的相关新闻

2. 请使用中文对上述内容进行总结，并以分点形式呈现。
""")
    return agent.ask(news_text)

def strategy(context: Context):
    params: Params = context.params
    deps = context.deps
    if not context.deps.other_data_api.is_business_day():
        logger.info("今天不是交易日，退出")
        return 
    data = get_recent_data_with_at_least_count(65, params.symbol, params.data_frame, deps.exchange)
    latest_price = data[-1].close
    indicators_info = calculate_technical_indicators(data, 20)
    pattern_info = detect_candle_patterns(data[-20:])
    caixin_news = deps.news.get_news_from('caixin', data[-1].timestamp)
    east_news = deps.other_data_api.get_symbol_news(params.symbol, data[-1].timestamp)
    symbol_info = deps.other_data_api.get_symbol_information(params.symbol)
    news_text = render_news_in_markdown_group_by_platform({ 'caixin': caixin_news, 'eastmoney': east_news })
    history_list = context.get('operation_history')
    gpt_setting = construct_system_prompt(context.params.risk_prefer, context.params.strategy_prefer)
    news_summary = gpt_news_summary(context, news_text, symbol_info, params.symbol)
    max_lots = int(context.get('account_money_amount') / latest_price / 100)
    gpt_request = construct_gpt_question(
        data, 
        context.params.symbol,
        symbol_info,
        indicators_info, 
        pattern_info, 
        news_summary,
        context.get('account_money_amount'),
        context.get('account_symbol_amount'),
        data[-1].close, 
        max_lots,
        history_list
    )
    logger.info(gpt_setting)
    context.deps.notification_logger.msg(gpt_request)
    logger.info(gpt_request)

    # 分析决策
    voter_result = { 'buy': [], 'sell': [], 'hold': [] }
    while len(voter_result['buy']) < 2 and len(voter_result['sell']) < 2 and len(voter_result['hold']) < 2:
        result = gpt_analysis(context, gpt_setting, gpt_request, max_lots)
        if result['action'] == 'buy':
            voter_result['buy'].append(result)
        elif result['action'] == 'sell':
            voter_result['sell'].append(result)
        else:
            voter_result['hold'].append(result)

    if len(voter_result['buy']) == 2:
        buy_lots = int(mean(voter_result['buy'][0]['lots'], voter_result['buy'][1]['lots']))
        context.buy(buy_lots, data[-1].close, voter_result['buy'][0]['summary'])

    if len(voter_result['sell']) == 2:
        sell_lots = int(mean(voter_result['sell'][0]['lots'], voter_result['sell'][1]['lots']))
        context.sell(sell_lots, data[-1].close, voter_result['sell'][0]['summary'])

def run(cmd_params: dict, notification: NotificationLogger):
    params = Params(
        money=cmd_params.get('money'), 
        data_frame='1d',
        symbol = cmd_params.get('symbol'),
        strategy_prefer=cmd_params.get('strategy_prefer'),
        risk_prefer=cmd_params.get('risk_prefer')
    )
    deps = Dependency(
        notification=notification,
        decision_voters_gpt_agents=map_by(cmd_params.get('voter_agents'), lambda m: get_agent_by_model(m, { "temperature": 0.2 }))
    )
    with Context(params = params, deps=deps) as context:
        strategy(context)
