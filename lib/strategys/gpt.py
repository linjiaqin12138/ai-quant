from dataclasses import dataclass
import json
import abc
from typing import List, Optional, TypedDict, Literal, Union, Dict
from datetime import datetime, timedelta

import g4f

from ..model import CryptoOrder, NewsInfo, Ohlcv
from ..utils.retry import with_retry
from ..utils.list import filter_by, map_by
from ..utils.string import extract_json_string
from ..utils.ohlcv import atr_info, boll_info, macd_info, sam20_info, sam5_info,rsi_info, stochastic_oscillator_info
from ..utils.number import get_total_assets, is_nan, mean, remain_significant_digits
from ..utils.time import dt_to_ts, timeframe_to_second, to_utc_isoformat, minutes_ago, ts_to_dt
from ..adapter.database.session import SessionAbstract
from ..adapter.exchange.crypto_exchange import BinanceExchange
from ..adapter.gpt import GptAgentAbstract, get_agent_by_model
from ..adapter.news import news, NewsAbstract
from ..modules.notification_logger import NotificationLogger
from ..modules.strategy import CryptoDependency, ParamsBase, ResultBase, ContextBase
from ..modules.crypto import CryptoOperationAbstract

ContextDict = TypedDict('Context', {
    'account_usdt_amount': float,
    'account_coin_amount': float,
    'operation_history': List[str]
})

GptAdviceDict = Union[
    TypedDict('GptAdviceDictBuy', {
        "action": Literal["buy"],
        "cost": float,
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

OperationRecord = TypedDict('OperationRecord', {
    'timestamp': int,
    'price': float,
    'action': Literal['buy', 'sell'],
    'amount': float,
    'cost': float,
    'remaining_usdt': float,
    'remaining_coin': float,
    'position_ratio': float,
    'summary': str
})

round_to_5 = lambda x: remain_significant_digits(x, 5)
map_by_round_to_5 = lambda x: map_by(x, round_to_5)

def format_operation_record(record: OperationRecord, coin_name: str) -> str:
    date_str = ts_to_dt(record['timestamp']).strftime('%Y-%m-%d')
    action_desc = {
        'buy': f"买入{round_to_5(record['amount'])}{coin_name}",
        'sell': f"卖出{round_to_5(record['amount'])}{coin_name}"
    }[record['action']]
    
    return f"{date_str} {action_desc}, 仓位{int(record['position_ratio']*100)}%, 原因: {record['summary']}"

class GptReplyNotValid(Exception):
    pass

@dataclass
class GptStrategyParams(ParamsBase):
    strategy_prefer: Optional[str]
    risk_prefer: Optional[str]

class OtherDataFetcherAbstract(abc.ABC):
    @abc.abstractmethod
    def get_u_base_global_long_short_account_ratio(self, symbol: str) -> float:
        pass 
    @abc.abstractmethod
    def get_u_base_top_long_short_account_ratio(self, symbol: str) -> float:
        pass
    @abc.abstractmethod
    def get_u_base_top_long_short_ratio(self, symbol: str) -> float:
        pass 
    @abc.abstractmethod
    def get_latest_futures_price_info(self, symbol: str) -> float:
        pass

class OtherDataFetcher(OtherDataFetcherAbstract):
    binance_exchange = BinanceExchange()

    def get_latest_futures_price_info(self, symbol: str) -> float:
        return self.binance_exchange.get_latest_futures_price_info(symbol)[-1]['lastFundingRate']
    
    def get_u_base_global_long_short_account_ratio(self, symbol: str) -> float:
        return self.binance_exchange.get_u_base_global_long_short_account_ratio(symbol, '15m', start=minutes_ago(30))[-1]['longShortRatio']
    
    def get_u_base_top_long_short_account_ratio(self, symbol: str) -> float:
        return self.binance_exchange.get_u_base_top_long_short_account_ratio(symbol, '15m', start=minutes_ago(30))[-1]['longShortRatio']
    
    def get_u_base_top_long_short_ratio(self, symbol: str) -> float:
        return self.binance_exchange.get_u_base_top_long_short_ratio(symbol, '15m', start=minutes_ago(30))[-1]['longShortRatio']

class GptStrategyDependency(CryptoDependency):
    def __init__(self, notification: NotificationLogger, news_summary_agent: GptAgentAbstract, voter_agents: List[GptAgentAbstract], crypto: CryptoOperationAbstract = None, session: SessionAbstract = None, news_adapter: NewsAbstract = news, future_data: OtherDataFetcherAbstract = None):
        super().__init__(notification = notification, crypto=crypto, session=session)
        self.news_summary_agent = news_summary_agent
        self._curr_voter_idx = -1
        self.voter_agents = voter_agents
        self.news_modules = news_adapter
        self.future_data = future_data or OtherDataFetcher()

    def get_a_voter_agent(self) -> GptAgentAbstract:
        self._curr_voter_idx = (self._curr_voter_idx + 1) % len(self.voter_agents)
        return self.voter_agents[self._curr_voter_idx]

    def _get_latest_crypto_news(self) -> List[NewsInfo]:
        return self.news_modules.get_latest_news_of_platform('cointime')
    
    def gpt_summary_news(self, coin_name: str) -> str:
        """
        使用GPT总结最新的加密货币新闻，返回总结后的文本

        1. 提取出对<coin_name>有影响的新闻，包括市场、政策、国际局势、宏观数据、主流币的行情，<coin_name>币的相关新闻、<coin_name>项目进展等
        2. 使用中文总结分点叙述上述新闻内容
        """
        # 获取最新的加密货币新闻
        latest_news = self._get_latest_crypto_news()
        # 使用GPT代理生成总结
        sys_prompt = f"""
你是一位资深的加密货币新闻分析师，擅长总结和分析加密货币新闻。
请总结加密货币新闻，特别关注对{coin_name}有影响的内容：
1. 提取出对{coin_name}有影响的新闻，包括：
    - 市场动态
    - 政策变化
    - 国际局势
    - 宏观经济数据
    - 主流加密货币的行情
    - {coin_name}币的相关新闻
    - {coin_name}项目的最新进展

2. 发给你的新闻内容是json格式，请使用中文对上述内容进行总结，并以分点形式呈现。
        """
        self.news_summary_agent.set_system_prompt(sys_prompt)
        return self.news_summary_agent.ask(json.dumps([{'title': news.title, 'description': news.description} for news in latest_news], ensure_ascii=False))
        
class Context(ContextBase[GptStrategyDependency, GptStrategyParams]):
    def __init__(self, params: GptStrategyParams, deps: GptStrategyDependency):
        super().__init__(params, deps)
        
    def init_id(self, params: ParamsBase) -> str:
        return f'{super().init_id(params)}_GPT'

    def init_context(self, params: ParamsBase) -> ContextDict:
        return {
            'account_usdt_amount': params.money,
            'account_coin_amount': 0,
            'operation_history': []
        }

def gpt_analysis(context: Context, data: List[Ohlcv]) -> GptAdviceDict:
    # 将数据转换为适合GPT分析的格式
    data_for_gpt = [
        {
            "timestamp": to_utc_isoformat(ohlcv.timestamp),
            "open": ohlcv.open,
            "high": ohlcv.high,
            "low": ohlcv.low,
            "close": ohlcv.close,
            "volume": ohlcv.volume
        } for ohlcv in data[-30:]  # 使用最近的30个数据点
    ]

    coin_name = context._params.symbol.split('/')[0]
    # 计算一些技术指标
    data_length = 20
    sma_5 = map_by_round_to_5(sam5_info(data)['sma5'][-data_length:])
    sma_20 = map_by_round_to_5(sam20_info(data)['sma20'][-data_length:])
    rsi = map_by_round_to_5(rsi_info(data)['rsi'][-data_length:])
    boll = boll_info(data)
    bb_upper = map_by_round_to_5(boll['upperband'][-data_length:])
    bb_middle = map_by_round_to_5(boll['middleband'][-data_length:])
    bb_lower = map_by_round_to_5(boll['lowerband'][-data_length:])
    macd = macd_info(data)
    macd_histogram = map_by_round_to_5(filter_by(macd['macd_hist'][-data_length:], lambda x: not is_nan(x)))
    stochastic_oscillator = stochastic_oscillator_info(data)
    stoch_k = map_by_round_to_5(stochastic_oscillator['stoch_k'][-data_length:])
    stoch_d = map_by_round_to_5(stochastic_oscillator['stoch_d'][-data_length:])
    atr = map_by_round_to_5(atr_info(data)['atr'][-data_length:])
    # 获取最新的加密货币新闻
    latest_news = context._deps.gpt_summary_news(coin_name)
   
    global_long_short_account = context._deps.future_data.get_u_base_global_long_short_account_ratio(symbol=context._params.symbol)
    top_long_short_account = context._deps.future_data.get_u_base_top_long_short_account_ratio(symbol=context._params.symbol)
    top_long_short_amount = context._deps.future_data.get_u_base_top_long_short_ratio(symbol=context._params.symbol)
    future_rate = round_to_5(context._deps.future_data.get_latest_futures_price_info(context._params.symbol))
    trade_history_arr = context.get('operation_history')[-10:] if len(context.get('operation_history')) > 10 else context.get('operation_history')
    trade_history_text = "\n".join(map_by(trade_history_arr, lambda x: '- ' + format_operation_record(x, coin_name)) if len(trade_history_arr) > 0 else "暂无交易历史")

    ohlcv_text = '\n'.join([
        '[', 
            ',\n'.join(
                map_by(data_for_gpt, lambda x : '    ' + json.dumps(x))
            ), 
        ']'
    ])
    voter_system_prompt = f"""
你是一位经验丰富的加密货币交易专家，擅长分析市场数据、技术指标和新闻信息，现在是一个新的交易日，并按照以下过程对{coin_name}进行技术分析
1. 请分析过去30天OHLCV日线级别数据, 判断短期和长期趋势
2. 结合技术指标(如SMA、RSI、MACD、布林带等)，确认趋势强度和潜在反转信号
3. 综合考虑新闻事件和市场情绪，评估外部因素对价格的影响；
4. 回顾交易历史，结合当前仓位和风险偏好，给出具体的交易建议。

请基于提供的数据和信息，给出一个JSON格式的响应，包含下一步的行动建议（"buy"、"sell"或"hold"），具体的交易数量，以及相应的理由，JSON字段如下：
- action: "buy"（买入）, "sell"（卖出）或 "hold"（不动）
- amount: (Required when action is sell) action为sell时返回卖出的{coin_name}数量，不得超过持有的{coin_name}数量
- cost: (Required when action is buy) action为buy时返回花费的USDT数量, 不得超过持有的USDT数量
- reason: 做出此决定的详细分析报告，包括对各个数据和指标的分析，内容必须包括：OHLCV数据分析、技术指标分析(必须对所有给出的指标进行评价，包括SMA,RSI,BOLL,MACD,KDJ,ATR)、新闻事件分析、仓位和风险偏好分析
- summary: (Required when action is buy/sell) 用30个字左右简要概括交易理由，用于交易历史复盘

响应格式例子：
```json
Example 1:
{{
    "action": "buy",
    "cost": 100.0,
    "summary": "技术指标良好且处于低位，ETF利好",
    "reason": "OHLCV分析：当前价格100.0处于近30日低位，成交量较前期增加50%；技术指标分析：SMA5(98.5)上穿SMA20(97.8)形成黄金交叉，RSI(28)处于超卖区域，布林带(上轨102.3/中轨97.8/下轨93.3)显示价格接近下轨支撑，MACD形成金叉且趋势转好，KD指标中%K(20)低于%D(35)但即将交叉，ATR(2.5)显示波动率处于低位适合建仓；新闻分析：SEC批准比特币现货ETF，机构资金大量流入，以太坊即将完成新一轮网络升级；交易历史回顾：上次在95.0价位减仓过早导致错过部分涨幅，这次应吸取教训，在技术指标和基本面共振时果断建仓；仓位分析：当前仓位较轻(30%)，风险承受能力充足，适合增加仓位。"
}}
Example 2:
{{
    "action": "sell",
    "amount": 100.0,
    "summary": "技术指标超买，交易所利空消息",
    "reason": "OHLCV分析：价格突破前期高点后量能不足，近5日成交量持续萎缩；技术指标分析：SMA5(120.5)下穿SMA20(122.3)，RSI(78)处于超买区域，布林带(上轨125.6/中轨122.3/下轨119.0)显示价格触及上轨resistance，MACD形成死叉且趋势转坏，随机指标%K(85)高于%D(75)且开始向下发散，ATR(4.8)显示波动加剧风险提升；新闻分析：某大型加密货币交易所被监管机构调查，主要公链遭受安全漏洞攻击，市场恐慌情绪上升；交易历史回顾：之前两次在类似技术形态下错过减仓机会导致回撤过大，本次应及时止盈，保护既有收益；仓位分析：当前持仓占总资金70%，风险较大，建议适当减仓。"
}}
Example 3:
{{
    "action": "hold",
    "reason": "OHLCV分析：价格在SMA20附近小幅震荡，成交量保持平稳；技术指标分析：SMA5(110.2)与SMA20(110.5)基本平行，RSI(55)处于中性位置，布林带(上轨115.6/中轨110.5/下轨105.4)呈现横向收敛趋势，MACD无明显金叉死叉，趋势平稳，随机指标%K(45)和%D(48)在中位盘整，ATR(1.8)显示波动率较低；新闻分析：市场关注美联储议息会议，主流币种开发进展平稳，DeFi总锁仓量保持稳定；交易历史回顾：历史数据显示在震荡市频繁交易往往造成损失，保持耐心等待明确信号是更好的选择；仓位分析：当前仓位适中(50%)，风险收益比例平衡，建议继续持有。"
}}
```

注意：
1. 交易数量应该是合理的，不要超过仓位信息中给出的可用的USDT余额或{coin_name}持仓量。
2. 买入消耗不得低于5USDT，卖出的币总价值不得低于5USDT，避免资金量过低引起的交易失败
3. 交易偏好：我是一名{context._params.risk_prefer or "风险厌恶型"}投资者
4. 交易策略：我倾向于{context._params.strategy_prefer or "中长期投资"}策略
"""
    # 交易偏好等级：风险厌恶型/风险中性型/风险喜好型
    # 交易策略分级：短期投资策略(3d-3m)/中期投资策略(3m-1y)/中长期投资策略(/长期投资策略(1-10y)/超长期投资策略(10-100y)
    # 准备发送给GPT的提示
    voter_asking_prompt = f"""
分析以下加密货币的信息，并给出交易建议：

1. 最近{len(data_for_gpt)}天的OHLCV数据:
{ohlcv_text}

2. 过去一段时间的技术指标:
- 过去{len(sma_5)}天5日简单移动平均线 (SMA5): {sma_5}
- 过去{len(sma_20)}天20日简单移动平均线 (SMA20): {sma_20}
- 过去{len(rsi)}天相对强弱指标 (RSI): {rsi}
- 布林带 (Bollinger Bands):
    - 过去{len(bb_upper)}天上轨: {bb_upper}
    - 过去{len(bb_middle)}天中轨: {bb_middle}
    - 过去{len(bb_lower)}天下轨: {bb_lower}
- MACD:
    - 金叉: {'是' if macd['is_gold_cross'] else '否'}
    - 死叉: {'是' if macd['is_dead_cross'] else '否'}
    - 趋势转好: {'是' if macd['is_turn_good'] else '否'}
    - 趋势转坏: {'是' if macd['is_turn_bad'] else '否'}
    - 过去{len(macd_histogram)}天的MACD柱状图: {macd_histogram}
- 过去{len(stoch_k)}天随机指标 (Stochastic Oscillator):
    - %K: {stoch_k}
    - %D: {stoch_d}
- 过去{len(atr)}天平均真实范围 (ATR): {atr}

3. 过去24h内最新相关新闻:
```
{latest_news}
```

4. 币安交易所{coin_name}此刻的U本位合约数据：
- 多空持仓人数比：{global_long_short_account}
- 大户账户数多空比: {top_long_short_account}
- 大户持仓量多空比: {top_long_short_amount}
- 资金费率：{'{:.20f}'.format(future_rate).rstrip('0').rstrip('.')}

5. 当前仓位信息:
- USDT余额: {round_to_5(context.get('account_usdt_amount'))}
- {coin_name}持仓量: {round_to_5(context.get('account_coin_amount'))} (价值约{round_to_5(context.get('account_coin_amount') * data[-1].close)} USDT)

6. 最近10次以内交易历史
{trade_history_text}

请根据这些信息分析市场趋势，并给出具体的交易建议。
"""
    #TODO: 添加历史交易情况
    context._deps.notification_logger.msg(voter_asking_prompt)

    vote_result: Dict[str, List[GptAdviceDict]] = { 'buy': [], 'sell':[], 'hold': [] }

    def validate_gpt_advice(advice: str) -> GptAdviceDict:
        try:
            advice_json = extract_json_string(advice)
            assert isinstance(advice_json, dict), "GPT回复必须是一个字典格式"
            assert 'action' in advice_json, "GPT回复缺少'action'字段"
            assert advice_json['action'] in ['buy', 'sell', 'hold'], f"无效的action值: {advice_json['action']}, 必须是'buy'/'sell'/'hold'之一"
            assert 'reason' in advice_json, "GPT回复缺少'reason'字段"
            assert isinstance(advice_json['reason'], str), "'reason'字段必须是字符串类型"
            if advice_json['action'] != 'hold':
                assert 'summary' in advice_json, f"{advice_json['action']}操作必须包含'summary'字段"
            if advice_json['action'] == 'buy':
                assert 'cost' in advice_json, "买入操作缺少'cost'字段"
                assert isinstance(advice_json['cost'], float), "'cost'字段必须是浮点数类型"
                assert advice_json['cost'] > 0, "'cost'必须大于0"
                assert advice_json['cost'] <= context.get('account_usdt_amount'), f"买入金额{advice_json['cost']}超过可用USDT余额{context.get('account_usdt_amount')}"
            elif advice_json['action'] == 'sell':   
                assert 'amount' in advice_json, "卖出操作缺少'amount'字段"
                assert isinstance(advice_json['amount'], float), "'amount'字段必须是浮点数类型"
                assert advice_json['amount'] > 0, "'amount'必须大于0"
                assert advice_json['amount'] <= context.get('account_coin_amount'), f"卖出数量{advice_json['amount']}超过持仓数量{context.get('account_coin_amount')}"
            return advice_json
        except Exception as err:
            raise GptReplyNotValid(err)

    @with_retry((GptReplyNotValid, g4f.errors.RetryProviderError, g4f.errors.RateLimitError, g4f.errors.ResponseError, g4f.errors.ResponseStatusError), 3)
    def retryable_part() -> GptAdviceDict:
        agent = context._deps.get_a_voter_agent()
        agent.clear()
        agent.set_system_prompt(voter_system_prompt)
        advice_rsp = agent.ask(voter_asking_prompt)
        advice_json = validate_gpt_advice(advice_rsp)
        context._deps.notification_logger.msg(f"{agent.model}: {advice_json}")
        return advice_json
    
    def combine_reason(votes: List[GptAdviceDict]) -> str:
        reason1 = votes[0]['reason']
        reason2 = votes[1]['reason']
        return f"1. {reason1}\n2. {reason2}"
    
    def mean_result(action: Literal['cost', 'amount'], votes: List[GptAdviceDict]) -> float:
        return mean(votes[0][action], votes[1][action])
    
    while len(vote_result['buy']) < 2 and len(vote_result['sell']) < 2 and len(vote_result['hold']) < 2:
        gpt_advice = retryable_part()
        vote_result[gpt_advice['action']].append(gpt_advice)

    if len(vote_result['buy']) == 2:
        return {
            'action': 'buy',
            'cost': mean_result('cost', vote_result['buy']),
            'summary': vote_result['buy'][0]['summary'],
            'reason': combine_reason(vote_result['buy'])
        }
    if len(vote_result['sell']) == 2:
        return {
            'action': 'sell',
            'amount': mean_result('amount', vote_result['sell']),
            'summary': vote_result['sell'][0]['summary'],
            'reason': combine_reason(vote_result['sell'])
        }
    
    return {
        'action': 'hold',
        'reason': combine_reason(vote_result['hold'])
    }

def gpt(context: Context) -> ResultBase:
    params: ParamsBase = context._params
    deps = context._deps
    
    expected_data_length = 65
    data = deps.crypto.get_ohlcv_history(
        params.symbol, 
        params.data_frame, 
        datetime.now() - (expected_data_length) * timedelta(seconds = timeframe_to_second(params.data_frame)),
        datetime.now()
    ).data
    coin_name = context._params.symbol.split('/')[0]
    advice_json = gpt_analysis(context, data)
    deps.notification_logger.msg(str(advice_json))

    def update_context_after_trade(order: CryptoOrder, action: Literal['buy', 'sell'], advice_json: GptAdviceDict) -> None:
        if action == 'buy':
            context.set('account_coin_amount', context.get('account_coin_amount') + order.get_amount(True))
            context.set('account_usdt_amount', context.get('account_usdt_amount') - order.get_cost(True))
        else:  # sell
            context.set('account_coin_amount', context.get('account_coin_amount') - order.get_amount(True))
            context.set('account_usdt_amount', context.get('account_usdt_amount') + order.get_cost(True))
            
        operation_record: OperationRecord = {
            "timestamp": dt_to_ts(order.timestamp),
            "price": order.price,
            "action": action,
            "amount": order.get_amount(True),
            "cost": order.get_cost(True),
            "remaining_usdt": round_to_5(context.get("account_usdt_amount")),
            "remaining_coin": round_to_5(context.get("account_coin_amount")),
            "position_ratio": round_to_5(context.get("account_coin_amount") * order.price / (context.get("account_usdt_amount") + context.get("account_coin_amount") * order.price)),
            "summary": advice_json['summary']
        }

        context.set('operation_history', context.get('operation_history') + [operation_record])

    if advice_json['action'] == 'buy':
        order = deps.crypto.create_order(params.symbol, 'market', 'buy', f'GPT_PLAN_{params.symbol}', spent = advice_json['cost'], comment=advice_json['reason'])
        update_context_after_trade(order, 'buy', advice_json)

    elif advice_json['action'] == 'sell':
        order = deps.crypto.create_order(params.symbol, 'market', 'sell', f'GPT_PLAN_{params.symbol}', amount = advice_json['amount'], comment=advice_json['reason'])
        update_context_after_trade(order, 'sell', advice_json)

    deps.notification_logger.msg('\n'.join(map_by(context.get('operation_history'), lambda x : '- ' + format_operation_record(x, coin_name))))

    return ResultBase(
        total_assets = get_total_assets(data[-1].close, context.get('account_coin_amount'), context.get('account_usdt_amount'))
    )

def run(cmd_params: dict, notification: NotificationLogger):
    params = GptStrategyParams(
        money=cmd_params.get('money'), 
        data_frame='1d', 
        symbol = cmd_params.get('symbol'),
        strategy_prefer=cmd_params.get('strategy_prefer'),
        risk_prefer=cmd_params.get('risk_prefer')
    )
    deps = GptStrategyDependency(
        notification=notification,
        news_summary_agent=get_agent_by_model(cmd_params.get('news_summary_agent')),
        voter_agents=map_by(cmd_params.get('voter_agents'), lambda m: get_agent_by_model(m, {
            "temperature": 0.2,       # 控制随机性
            "top_p": 0.9,             # 核采样设置
            "frequency_penalty": 0.3, # 减少重复
            "presence_penalty": 0.2   # 保持适当的新词
        }))
    )
    with Context(params = params, deps=deps) as context:
        gpt(context)