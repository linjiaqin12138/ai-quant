import json
from typing import List, TypedDict
from datetime import datetime, timedelta
from ..model import NewsInfo, Ohlcv
from ..logger import logger
from ..utils.retry import with_retry
from ..utils.list import filter_by, map_by
from ..utils.string import extract_json_string
from ..utils.ohlcv import atr_info, boll_info, macd_info, sam20_info, sam5_info,rsi_info, stochastic_oscillator_info
from ..utils.number import get_total_assets, is_nan, remain_significant_digits
from ..utils.time import timeframe_to_second
from ..adapter.database.session import SessionAbstract
from ..adapter.gpt import GptAgentAbstract, BaiChuanAgent
from ..adapter.notification import NotificationAbstract
from ..adapter.news import news, NewsAbstract
from ..modules.notification_logger import NotificationLogger
from ..modules.strategy import CryptoDependency, ParamsBase, ResultBase, ContextBase

ContextDict = TypedDict('Context', {
    'account_usdt_amount': float,
    'account_coin_amount': float,
    'operation_history': List[str]
})

round_to_5 = lambda x: remain_significant_digits(x, 5)
class GptStrategyDependency(CryptoDependency):
    def __init__(self, notification: NotificationAbstract, agent: GptAgentAbstract):
        super().__init__(notification = notification)
        self.agent = agent
        self.news = news

    def _get_latest_crypto_news(self) -> List[NewsInfo]:
        return self.news.get_latest_news_of_platform('cointime')
    
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
        self.agent.set_system_prompt(sys_prompt)
        return self.agent.ask(json.dumps([{'title': news.title, 'description': news.description} for news in latest_news], ensure_ascii=False))
        
class Context(ContextBase[GptStrategyDependency]):
    def __init__(self, params: ParamsBase, deps: GptStrategyDependency):
        super().__init__(params, deps)

    def init_id(self, params: ParamsBase) -> str:
        return f'{super().init_id(params)}_GPT'

    def init_context(self, params: ParamsBase) -> ContextDict:
        return {
            'account_usdt_amount': params.money,
            'account_coin_amount': 0,
            'operation_history': []
        }

def gpt_analysis(context: Context, data: List[Ohlcv]) -> str:
    # 将数据转换为适合GPT分析的格式
    data_for_gpt = [
        {
            "timestamp": ohlcv.timestamp.isoformat(),
            "open": ohlcv.open,
            "high": ohlcv.high,
            "low": ohlcv.low,
            "close": ohlcv.close,
            "volume": ohlcv.volume
        } for ohlcv in data[-20:]  # 使用最近的20个数据点
    ]

    coin_name = context._params.symbol.split('/')[0]
    # 计算一些技术指标
    sma_5 = round_to_5(sam5_info(data)['sma5'][-1])
    sma_20 = round_to_5(sam20_info(data)['sma20'][-1])
    rsi = round_to_5(rsi_info(data)['rsi'][-1])
    boll = boll_info(data)
    bb_upper = round_to_5(boll['upperband'][-1])
    bb_middle = round_to_5(boll['middleband'][-1])
    bb_lower = round_to_5(boll['lowerband'][-1])
    macd = macd_info(data)
    macd_histogram = map_by(filter_by(macd['macd_hist'], lambda x: not is_nan(x)), round_to_5)
    stochastic_oscillator = stochastic_oscillator_info(data)
    stoch_k = round_to_5(stochastic_oscillator['stoch_k'][-1])
    stoch_d = round_to_5(stochastic_oscillator['stoch_d'][-1])
    atr = round_to_5(atr_info(data)['atr'][-1])
    # 获取最新的加密货币新闻
    latest_news = context._deps.gpt_summary_news(coin_name)
    trade_history_text = '\n'.join(map_by(context.get('operation_history'), lambda x : '-' + x))
    ohlcv_text = '\n'.join(['[', '\n'.join(map_by(data_for_gpt, lambda x : '    ' + x)), ']'])
    # 准备发送给GPT的提示
    prompt = f"""
分析以下加密货币的信息，并给出交易建议：

1. 最近20天的OHLCV数据:
{ohlcv_text}

2. 技术指标:
- 5日简单移动平均线 (SMA5): {sma_5}
- 20日简单移动平均线 (SMA20): {sma_20}
- 相对强弱指标 (RSI): {rsi}
- 布林带 (Bollinger Bands):
    - 上轨: {bb_upper}
    - 中轨: {bb_middle}
    - 下轨: {bb_lower}
- MACD:
    - 金叉: {'是' if macd['is_gold_cross'] else '否'}
    - 死叉: {'是' if macd['is_dead_cross'] else '否'}
    - 趋势转好: {'是' if macd['is_turn_good'] else '否'}
    - 趋势转坏: {'是' if macd['is_turn_bad'] else '否'}
    - 最近{len(macd_histogram)}天的MACD柱状图: {macd_histogram}
- 随机指标 (Stochastic Oscillator):
    - %K: {stoch_k}
    - %D: {stoch_d}
- 平均真实范围 (ATR): {atr}

3. 最新相关新闻:
{latest_news}

4. 当前仓位信息:
- USDT余额: {context.get('account_usdt_amount')}
- {coin_name}持仓量: {context.get('account_coin_amount')}

5. 历史交易情况：
{trade_history_text}

请根据这些信息分析市场趋势，并给出具体的交易建议。
"""
    #TODO: 添加历史交易情况
    logger.debug(prompt)
    context._deps.agent.set_system_prompt(f"""
你是一位经验丰富的加密货币交易专家，擅长分析市场数据、技术指标和新闻信息。你的专长包括：
1. 解读OHLCV数据，识别价格趋势和交易量变化。
2. 分析技术指标如移动平均线(SMA)和相对强弱指标(RSI)等，判断市场动向。
3. 评估最新加密货币新闻对市场的潜在影响。
4. 考虑当前仓位，给出具体的仓位调整建议。

请基于提供的数据和信息，给出一个JSON格式的响应，包含下一步的行动建议（"buy"、"sell"或"hold"），具体的交易数量，以及相应的理由。
回复格式应为JSON，包含以下字段：
- action: "buy"（买入）, "sell"（卖出）或 "hold"（不动）
- amount: (Required when action is sell) action为sell时返回卖出的{coin_name}数量，action为buy时返回花费的USDT数量
- cost: (Required when action is buy) action为buy时返回花费的USDT数量
- reason: 做出此决定的简要理由

响应格式例子：
```json
Example 1:
{{
    "action": "buy",
    "cost": 100.0,
    "reason": "价格处于低位，且有上涨趋势"
}}
Example 2:
{{
    "action": "sell",
    "amount": 100.0,
    "reason": "价格处于高位，且有下跌趋势"
}}
Example 3:
{{
    "action": "hold",
    "reason": "价格波动不大，且无明显趋势"
}}
```

注意：交易数量应该是合理的，不要超过当前可用的USDT余额或持仓量。
"""
    )
    class GptReplyNotValid(Exception):
        pass

    @with_retry((GptReplyNotValid,), 3)
    def retryable_part():
        context._deps.agent.clear()
        advice_rsp = context._deps.agent.ask(prompt)
        def validate_gpt_advice(advice: str) -> dict:
            advice_json = extract_json_string(advice)
            assert isinstance(advice_json, dict)
            assert 'action' in advice_json
            assert advice_json['action'] in ['buy', 'sell', 'hold']
            assert 'reason' in advice_json
            assert isinstance(advice_json['reason'], str)
            if advice_json['action'] == 'buy':
                assert 'cost' in advice_json
                assert isinstance(advice_json['cost'], float)
                assert advice_json['cost'] > 0 and advice_json['cost'] <= context.get('account_usdt_amount')
            elif advice_json['action'] == 'sell':   
                assert 'amount' in advice_json
                assert isinstance(advice_json['amount'], float)
                assert advice_json['amount'] > 0 and advice_json['amount'] <= context.get('account_coin_amount')
            return advice_json
        try:
            return validate_gpt_advice(advice_rsp)
        except Exception as err:
            raise GptReplyNotValid(err)
    
    return retryable_part()

def gpt(context: Context) -> ResultBase:
    params: ParamsBase = context._params
    deps = context._deps
    
    expected_data_length = 60
    data = deps.crypto.get_ohlcv_history(
        params.symbol, 
        params.data_frame, 
        datetime.now() - (expected_data_length) * timedelta(seconds = timeframe_to_second(params.data_frame)),
        datetime.now()           
    ).data
    
    advice_json = gpt_analysis(context, data)
    deps.notification_logger.msg(str(advice_json))
    coin_name = params.symbol.split('/')[0]
    if advice_json['action'] == 'buy':
        order = deps.crypto.create_order(params.symbol, 'market', 'buy', f'GPT_PLAN_{params.symbol}', spent = advice_json['cost'], comment=advice_json['reason'])
        context.set('account_coin_amount', context.get('account_coin_amount') + order.get_amount())
        context.set('account_usdt_amount', context.get('account_usdt_amount') - order.get_cost())
        operation_infomation = f'{order.timestamp.isoformat()} 价格: {order.price} 花费{order.get_cost()}USDT买入{order.get_amount()}个{coin_name}, 剩余:{context.get("account_usdt_amount")}USDT, 持有{context.get("account_coin_amount")}{coin_name}'
        context.set('operation_history', context.get('operation_history') + [operation_infomation])
        deps.notification_logger.msg(operation_infomation)
    elif advice_json['action'] == 'sell':
        order = deps.crypto.create_order(params.symbol, 'market', 'sell', f'GPT_PLAN_{params.symbol}', amount = advice_json['amount'], comment=advice_json['reason'])
        context.set('account_coin_amount', context.get('account_coin_amount') - order.get_amount())
        context.set('account_usdt_amount', context.get('account_usdt_amount') + order.get_cost())
        operation_infomation = f'{order.timestamp.isoformat()} 价格: {order.price} 卖出{order.get_amount(True)}个{coin_name}, 获得{order.get_cost(True)}USDT, 剩余:{context.get("account_usdt_amount")}USDT, 持有{context.get("account_coin_amount")}{coin_name}'
        context.set('operation_history', context.get('operation_history') + [operation_infomation])
        deps.notification_logger.msg(operation_infomation)

    return ResultBase(
        total_assets = get_total_assets(data[-1].close, context.get('account_coin_amount'), context.get('account_usdt_amount'))
    )

def run(cmd_params: dict, notification: NotificationLogger):
    model = cmd_params.get('gpt_model')
    params = ParamsBase(
        money=cmd_params.get('money'), 
        data_frame='1d', 
        symbol = cmd_params.get('symbol')
    )
    with Context(params = params, deps=GptStrategyDependency(notification=notification, agent=BaiChuanAgent(model))) as context:
        gpt(context)