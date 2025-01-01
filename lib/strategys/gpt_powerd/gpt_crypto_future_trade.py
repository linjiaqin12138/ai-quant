import abc
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, TypedDict
from lib.adapter.gpt import get_agent_by_model
from lib.adapter.gpt.interface import GptAgentAbstract

from ...model.common import Ohlcv
from ...utils.list import map_by
from ...utils.string import extract_json_string

from ...logger import logger
from .common import TechnicalIndicators, calculate_technical_indicators, format_ohlcv_list, round_to_5
from ...utils.news import render_news_in_markdown_group_by_platform
from ...utils.time import hours_ago

from ...config import get_binance_config
from ...model import OhlcvHistory, Order
from ...adapter.exchange.crypto_exchange.binance import BinanceExchange
from ...adapter.database.session import SessionAbstract
from ...adapter.news import NewsFetcherApi
from ...modules.news_proxy import news_proxy
from ...modules.exchange_proxy import ExchangeOperationProxy, CryptoProxy, ModuleDependency
from ...modules.notification_logger import NotificationLogger
from ...modules.strategy import BasicDependency, ParamsBase, BasicContext
from ...model import OrderSide, OrderType, CryptoHistoryFrame
from ..common import get_recent_data_with_at_least_count

ContextDict = TypedDict('Context', {
    'account_money_amount': float,
    'account_symbol_amount': float,
})

# 1. 看下这里需不需要补充额外的参数
@dataclass
class Params(ParamsBase):
    # 杠杆倍率
    max_leverage: int = 5
    risk_prefer: str = "风险喜好型"

FutureData = TypedDict('FutureData', {
    'last_funding_rate': float,
    'global_long_short_account_ratio': float,
    'top_long_short_account_ratio': float,
    'top_long_short_ratio': float,
})

class OtherOperationsApi(abc.ABC):

    # @abc.abstractmethod
    # def get_ohlcv_history(self, symbol: str, frame: CryptoHistoryFrame, start_time: datetime, end_time: datetime) -> OhlcvHistory:
    #     pass
    @abc.abstractmethod
    def set_leverate(self, symbol: str, leverage: int):
        pass

    @abc.abstractmethod
    def create_future_order(self, symbol: str) -> Order:
        pass
    
    @abc.abstractmethod
    def market_future_data(self, symbol: str, frame: CryptoHistoryFrame) -> FutureData:
        pass 


class OtherOperations(OtherOperationsApi):
    def __init__(self):
        self.binance = BinanceExchange(future_mode=True)
    def set_leverate(self, symbol: str, leverage: int):
        self.binance.binance.fapiPrivatePostLeverage({ 'symbol': symbol, 'leverage': leverage })

    # https://developers.binance.com/docs/zh-CN/derivatives/usds-margined-futures/trade/rest-api
    def create_future_order(self, symbol: str, order_type: str, order_side: str, amount: float, postion_side: str, price: float = None, stop_price: float = None) -> Order:
        return self.binance.binance.create_order(
            symbol=symbol,
            type=order_type,
            side=order_side,
            amount=amount,
            price=price,
            params = { 'positionSide': postion_side.upper(), 'stopPrice': stop_price }
        )
    def market_future_data(self, symbol: str) -> FutureData:
        last_funding_rate = self.binance.get_latest_futures_price_info(symbol)['lastFundingRate']
        global_long_short_account_ratio = self.binance.get_u_base_global_long_short_account_ratio(symbol, '15m', hours_ago(1))[-1]['longShortRatio']
        top_long_short_account_ratio = self.binance.get_u_base_top_long_short_account_ratio(symbol, '15m', hours_ago(1))[-1]['longShortRatio']
        top_long_short_ratio = self.binance.get_u_base_top_long_short_ratio(symbol, '15m', hours_ago(1))[-1]['longShortRatio']
        return {
            'last_funding_rate': last_funding_rate,
            'global_long_short_account_ratio': global_long_short_account_ratio,
            'top_long_short_account_ratio': top_long_short_account_ratio,
            'top_long_short_ratio': top_long_short_ratio
        }

class Dependency(BasicDependency):
    def __init__(self, 
                 notification: NotificationLogger,
                 session: SessionAbstract = None,
                 other_operations: OtherOperationsApi = None,
                 news_api: NewsFetcherApi = None,
                 news_summary_agent: GptAgentAbstract = get_agent_by_model('paoluz-gpt-4o-mini'),
                 result_voter_agents: List[GptAgentAbstract] = [get_agent_by_model('paoluz-gpt-4o-mini')],
                 ):
        super().__init__(
            notification = notification, 
            session=session
            )
        self.other_operations = other_operations or OtherOperations()
        self.news_api = news_api or news_proxy
        self.news_summary_agent = news_summary_agent
        self.result_voter_agents = result_voter_agents

class Context(BasicContext[ContextDict]):
    deps: Dependency
    def __init__(self, params: Params, deps: Dependency):
        super().__init__(f'{params.symbol}_{params.money}_{params.data_frame}_future_GPT', deps)
        self.params = params

    def _initial_context(self) -> ContextDict:
        # 2. 看下初始化的运行上下文是否需要额外的参数，同时修改ContextDict定义
        return {
            'account_money_amount': self.params.money,
            'account_symbol_amount': 0,
            # 三种状态：初始化、爆仓、止盈、正常
            'status': 'init',

        }
    
    # 3. 看下买入卖出函数的参数是否需要根据策略调整参数列表，必须增加买入卖出的理由等
    def buy(self, cost: float):
        # 4. 修改一下Strategy的Slogan，sell函数也是
        order = self.deps.exchange.create_order(self.params.symbol, 'market', 'buy', spent=cost)
        self.increate('account_symbol_amount', order.get_amount(True))
        self.decreate('account_money_amount', order.get_cost(True))
        self.deps.notification_logger.msg(f'{order.timestamp} 花费', order.get_cost(True), '买入', order.get_amount(True), '份')
        return

    def sell(self, amount: float):
        order = self.deps.exchange.create_order(self.params.symbol, 'market', 'buy', amount=amount)
        self.increate('account_money_amount', order.get_cost(True))
        self.decreate('account_symbol_amount', order.get_amount(True))
        self.deps.notification_logger.msg(f'{order.timestamp} 卖出', order.get_amount(True), '份并获得', order.get_cost(True))

def summary_news(news_text: str, agent: GptAgentAbstract, coin_name: str) -> str:
    agent.set_system_prompt(f"""你是一位资深的加密货币新闻分析师，擅长总结和分析加密货币新闻。
用户将给你过去一个小时内从各大平台搜集到的新闻，请过滤并总结与加密货币相关的新闻，特别关注对{coin_name}有影响的内容：
1. 提取出对{coin_name}有影响的新闻，包括：
    - 市场动态
    - 政策变化
    - 国际局势
    - 宏观经济数据
    - 主流加密货币的行情
    - {coin_name}币的相关新闻
    - {coin_name}项目的最新进展

2. 请使用中文对上述内容进行总结，并以分点形式呈现，如果没有特别需要注意的新闻，直接输出：当前无相关新闻需要关注。""")
    return agent.ask(news_text)

def validate_gpt_reply(reply_text: str) -> dict:
    reply_json = extract_json_string(reply_text)


def analysis_by_model(agent: GptAgentAbstract, sys_prompt: str, user_prompt: str) -> dict:
    sys_prompt = ''
    agent.set_system_prompt(sys_prompt)
    rsp_text = agent.ask(user_prompt)

def construct_system_prompt(coinname: str, risk_prefer: str) -> str:
    return f"""你是一位经验丰富的加密货币交易专家，擅长分析市场数据、技术指标和新闻信息。现在是一个新的交易时段，请按照以下流程对 **{coinname}** 进行 **1小时级别** 短线技术分析，并在必要时灵活使用杠杠来放大收益。

1. **价格与K线形态分析**  
   - 分析过去若干小时到数天的OHLCV数据（1小时K线），结合检测到的短期K线形态，判断近期趋势走向以及是否存在明显的短期波动机会。

2. **短周期技术指标分析**  
   - 结合常用指标（如SMA、RSI、MACD、布林带、KDJ、ATR 等），着重关注这些指标在短周期下的快速变化、趋势强度以及潜在反转信号。
   - 由于我们将使用杠杆，请仔细评估当前波动率和风险水平，判断是否需要加快或者放缓交易动作。

3. **新闻与市场情绪分析**  
   - 综合外部信息，如市场热点事件、监管动态、行业新闻等，评估其在短期内对价格可能造成的快速影响。

4. **回顾交易历史与仓位、风险分析**  
   - 参考已有的交易历史、当前仓位和风险偏好（{risk_prefer}），在确定的买多（开多）、卖多（平多）、卖空（开空）、买入平空（平空）等策略中，给出最合理的决策。
   - 请注意：我倾向于短期交易以捕捉波段机会，但仍需考虑整体风险控制，严格设定杠杆倍数与止盈止损范围。

你的回复必须是一个JSON结构体，定义如下：  
- **action(required)**: 建议操作类型，可选值：  
  - `"buy_long"`：买入开多  
  - `"sell_long"`：卖出平多  
  - `"sell_short"`：卖出开空  
  - `"buy_short"`：买入平空  
  - `"hold"`：保持观望  
- **leverage(optional)**: 使用杠杆倍数（2至5，第一次开单时使用，后续加仓不可用）。  
- **amount(optional)**: 平单时平掉的合约数量。  
- **cost(optional)**: 开单所需USDT金额（开单时提供）。  
- **take_profit(optional)**: 止盈百分比（开单时必须提供）。  
- **stop_loss(optional)**: 止损百分比（开单时必须提供），防止爆仓。  
- **reason(required)**: 详细分析报告，必须包括：  
  1. **OHLCV分析**：1小时短周期价格走势与K线形态。  
  2. **技术指标分析**：评估 SMA、RSI、BOLL、MACD、KDJ、ATR 等。  
  3. **新闻/市场情绪分析**：评估市场热点或外部影响。  
  4. **仓位与风险偏好分析**：杠杆选择及风险收益评估。  
  5. **止盈止损设置分析**：说明设置逻辑及保护作用。  
- **summary(required)**: 30字左右总结交易理由，用于复盘。  

请注意：  
1. **不要超过**我当前可用的 USDT 余额或{coinname}合约持仓量。  
2. 开单时所需 **USDT** 不能低于 5 USDT，总价值过小会导致无法执行交易；同理，平单的仓位总价值也需至少5 USDT。  
3. 请谨慎使用杠杆，不要盲目放大头，最大可使用5倍杠杆，我的风险偏好是{risk_prefer}。  
4. 遇不确定时，可保持观望（`"hold"`）。

请注意：
1. **不要超过**我当前可用的 USDT 余额或{coinname}合约持仓量。  
2. 开单时所需 **USDT** 不能低于 5 USDT，总价值过小会导致无法执行交易；同理，平单的仓位总价值也需至少5 USDT。  
3. 请谨慎使用杠杆，不要盲目放大头，最大可使用5倍杠杆，我的风险偏好是{risk_prefer} 
4. 遇不确定时，可保持观望（`"hold"`）.

响应格式示例
```json
Example A(开多,花费100USDT做保证金，使用2倍杠杆):
{
    "action": "buy_long",
    "leverage": 2,
    "take_profit": 
    "cost": 100.0,
    "summary": "短期回调充分，配合利好新闻加杠杆布局",
    "reason": "1. OHLCV分析：1小时K线显示近6小时内价格在支撑位筑底，成交量温和放大；\n2. 技术指标分析：SMA5(0.065)上穿SMA20(0.062)，RSI(35)接近超卖区即将反弹，布林带收口但价格临近下轨，MACD金叉初现，KDJ与ATR显示短线波动加剧适合小幅杠杆进场；\n3.新闻分析：主流媒体报道某龙头交易所上线DOGE衍生品，刺激市场关注度；\n4.仓位与风险分析：当前空仓较多，风险承受度充足，使用2倍杠杆开多但需密切监控波动。"
}
Example B(开空，花费50USDT做保证金，使用3倍杠杆):
{
    "action": "sell_short",
    "leverage": 3.0,
    "cost": 50.0,
    "summary": "短线高位承压，选择3倍杠杆进场做空",
    "reason": "1. OHLCV分析：1小时K线持续上行后出现顶部十字星形态，成交量放大但价格未能继续冲高；\n2.技术指标分析：SMA5(0.075)下穿SMA20(0.078)，RSI(72)超买区域，布林带上轨被多次触及，MACD死叉形成，KDJ快速下行，ATR显示波动率上升；\n3.新闻分析：最新宏观数据利空，市场担忧情绪上升；\n4.仓位与风险分析：当前已有一部分多单获利平仓，风险较可控，可用少量资金在3倍杠杆上尝试短线做空，及时设置止损。"
}
Example C(平多，卖出一部分的合约，假设持有400份，这里卖出200份，平掉一半仓位锁定利润):
{
    "action": "sell_long",
    "amount": 200.0,
    "summary": "短期见顶信号明显，先行止盈",
    "reason": "1. OHLCV分析：1小时级别形成双顶形态并出现回落迹象，成交量相对萎缩；\n2.技术指标分析：SMA5(0.068)与SMA20(0.067)死叉，RSI(65)仍较高但开始回落，布林带中轨(0.067)附近有支撑，MACD转空，KDJ死叉延续，ATR(0.005)显示波动率平稳；3.新闻分析：缺乏重大利多消息，市场观望情绪升温；4. 仓位与风险分析：目前仓位偏重，风险较集中，卖出部分DOGE锁定收益较为稳妥。"
}
Example D(平空，买入一部分卖出的合约，假设开空了400份，这里买入200份，平掉一半仓位锁定利润):
{
    "action": "buy_short",
    "amount": 200.0,
    "summary": "短线支撑确认，适度平仓止盈。",
    "reason": "1. OHLCV分析：1小时K线触及前低，形成看涨锤子线；\n2.技术指标分析：SMA5(0.062)上穿SMA20(0.061)，RSI(35)从超卖区反弹，MACD金叉形成，ATR显示波动减弱；\n3.新闻分析：近期无重大利空消息，市场情绪趋稳；\n4.仓位与风险分析：当前空单已有较好浮盈，适度平仓降低风险。"
}
```
"""

def format_position_info(context: Context) -> str:
    position_info = context.get('position_info', {})
    account_usdt = context.get('account_money_amount', 0)
    result = [
        f'- USDT余额: {account_usdt}',
    ]

    if position_info['status'] == 'none':
        result.append(f'- 仓位状态：未开仓')
    elif position_info['status'] == 'long':
        result.append(f'- 仓位状态：开多中')
        result.append(f'- 多仓合约数量：{position_info["amount"]}')
    elif position_info['status'] == 'short':
        result.append(f'- 仓位状态：开空中')
        result.append(f'- 空仓合约数量：{position_info["amount"]}')

    return '\n'.join(result)


def construct_user_prompt(context: Context, coin_name: str, data_1h: List[Ohlcv], data_1d:List[Ohlcv], indicators_1h: TechnicalIndicators, news_1h_text: str, future_data: FutureData) -> str:
    ohlcv_1d_text = format_ohlcv_list(data_1d, 7)
    ohlcv_1h_text = format_ohlcv_list(data_1h, 30)
    position_info = context.get('positon_info')
    
    return f"""
分析以下加密货币的信息，并给出交易建议：

1. 过去7天的1d级别的OHLCV数据:
{ohlcv_1d_text}

2. 过去30个小时的1h级别的OHLCV数据:
{ohlcv_1h_text}

3. 基于1h级别K线的技术指标:
- 过去{len(indicators_1h.sma5)}小时的5h简单移动平均线 (SMA5): {indicators_1h.sma5}
- 过去{len(indicators_1h.sma20)}小时的20h简单移动平均线 (SMA20): {indicators_1h.sma20}
- 过去{len(indicators_1h.rsi)}小时相对强弱指标 (RSI): {indicators_1h.rsi}
- 布林带 (Bollinger Bands):
    - 过去{len(indicators_1h.bollinger_upper)}小时上轨: {indicators_1h.bollinger_upper}
    - 过去{len(indicators_1h.bollinger_middle)}天中轨: {indicators_1h.bollinger_middle}
    - 过去{len(indicators_1h.bollinger_lower)}天下轨: {indicators_1h.bollinger_lower}
- 过去{len(indicators_1h.macd_histogram)}小时的MACD柱状图: {indicators_1h.macd_histogram}
- 过去{len(indicators_1h.stoch_d)}小时随机指标 (Stochastic Oscillator):
    - %K: {indicators_1h.stoch_k}
    - %D: {indicators_1h.stoch_d}
- 过去{len(indicators_1h.atr)}小时平均真实范围 (ATR): {indicators_1h.atr}

3. 过去一小时内最新相关新闻:
```
{news_1h_text}
```

4. 币安交易所{coin_name}此刻的U本位合约数据：
- 多空持仓人数比：{future_data['global_long_short_account_ratio']}
- 大户账户数多空比: {future_data['top_long_short_account_ratio']}
- 大户持仓量多空比: {future_data['top_long_short_ratio']}

- 资金费率：{'{:.20f}'.format(future_data['last_funding_rate']).rstrip('0').rstrip('.')}

5. 当前仓位信息:
- USDT余额：
{format_position_info(context)}

6. 最近10次以内交易历史
{trade_history_text}

请根据这些信息分析市场趋势，并给出具体的交易建议。
"""
# def analysis_by_agent()
def gpt_analysis(context: Context, data_1h: List[Ohlcv], data_1d: List[Ohlcv], indicators_1h: TechnicalIndicators, news_1h_text: str, future_data: FutureData) -> dict:
    coin_name = context.params.symbol.rstrip('USDT').rstrip('/')
    news_summary = summary_news(news_1h_text, context.deps.news_summary_agent, coin_name)
    sys_prompt = construct_system_prompt(coin_name, context.params.risk_prefer)
    user_prompt = construct_user_prompt(coin_name, data_1h, data_1d, indicators_1h, news_1h_text, future_data)
    action_counts = { 'buy_long': 0, 'sell_short': 0, 'sell_long': 0, 'buy_short': 0 }
    while not any(count >= 2 for count in action_counts.values()):


def strategy(context: Context):
    params: Params = context.params
    deps = context.deps
    if context.get('status') == 'init':
        context.deps.other_operations.set_leverate(params.symbol, params.max_leverage)
        context.set('status', 'normal')
    
    data_1h = get_recent_data_with_at_least_count(48, params.symbol, '1h', deps.exchange)
    data_1d = get_recent_data_with_at_least_count(7, params.symbol, '1d', deps.exchange)
    indicators_1h = calculate_technical_indicators(data_1h)
    news_1h_text = render_news_in_markdown_group_by_platform({
        'contime': context.deps.news_api.get_news_during('contime', data_1h[-1].timestamp, data_1h[-1].timestamp + timedelta(hours=1)),
        'jin10': context.deps.news_api.get_news_during('jin10', data_1h[-1].timestamp, data_1h[-1].timestamp + timedelta(hours=1)),
    })
    logger.debug(news_1h_text)
    future_data = context.deps.other_operations.market_future_data(params.symbol)  
    # 5. 补充你的策略决策代码，并根据决策结果调用buy/sell函数进行交易
    # 分析决策
    result = gpt_analysis(context, data_1h, data_1d, indicators_1h, news_1h_text, future_data)

    # 判断是否买入卖出
    if result.get('action') == 'buy':
        context.buy(result.get('cost'), result.get(''))

    if result.get('xx'):
        context.sell(100)


def run(params: dict, notification: NotificationLogger):
    with Context(params = Params(**params), deps=Dependency(notification=notification)) as context:
        strategy(context)


        