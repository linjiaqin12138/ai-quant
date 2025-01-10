import abc
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Literal, TypedDict, Optional
import re

from ...logger import logger
from ...model import  CryptoHistoryFrame, Ohlcv
from ...utils.decorators import with_retry
from ...utils.list import filter_by, map_by
from ...utils.string import extract_json_string
from ...utils.time import ts_to_dt
from ...utils.number import change_rate
from ...utils.news import render_news_in_markdown_group_by_platform
from ...utils.time import hours_ago, timeframe_to_second
from ...adapter.exchange.crypto_exchange.binance import BinanceExchange
from ...adapter.database.session import SessionAbstract
from ...adapter.news import NewsFetcherApi
from ...adapter.gpt import get_agent_by_model, GptAgentAbstract
from ...modules.news_proxy import news_proxy
from ...modules.exchange_proxy import CryptoProxy, ModuleDependency
from ...modules.notification_logger import NotificationLogger
from ...modules.strategy import BasicDependency, ParamsBase, BasicContext
from .common import TechnicalIndicators, calculate_technical_indicators, format_ohlcv_list, round_to_5, GptReplyNotValid

ContextDict = TypedDict('Context', {
    'account_money_amount': float,
    'account_symbol_amount': float,
})

PositionRisk = TypedDict('PositionInfo', {
    'entryPrice': float, # 开仓价格
    'breakEvenPrice': float, # 盈亏平衡价
    'markPrice': float, # 标记价格
    'positionAmt': float, # 杠杆后仓位数量，做空为负
    'unRealizedProfit': float, # 未实现收益
    'liquidationPrice': float, # 爆仓价格
    'leverage': int, # 杠杆倍率
    'positionSide': Literal['LONG', 'SHORT'],
    'notional': float, # 杠杆后仓位价值，做空为负数
    'isolated': bool, # 逐仓true
    'updateTime': int
})

OrderInfo = TypedDict('OrderInfo', {
    'orderId': str,
    'status': Literal['FILLED', 'NEW'],
    'avgPrice': float, #均价
    'executedQty': float, # 份额
    'cumQuote': float, # 成交数量
    'reduceOnly': bool, # 只减仓
    'closePosition': bool, # 已平仓,
    # 'side': 'SELL',
    'updateTime': int,
    # 'positionSide': 'LONG',
    'stopPrice': float, #触发条件
    'origType': Literal['TAKE_PROFIT_MARKET', 'STOP_MARKET'], #止盈
})

PositionInfo = TypedDict('PositionInfo', {
    'is_position_closed': bool,
    'is_stop_order_resolve': bool,
    'take_profit_order': OrderInfo,
    'stop_loss_order': OrderInfo,
    'position_risk': PositionRisk,
})

CryptoFutureTradeAction = TypedDict('CryptoFutureTradeAction', {
    'action': Literal["buy_long", "sell_long", "sell_short", "buy_short", "add_position", "hold"],
    'leverage': Optional[int],  # 2-5, only for opening positions
    'amount': Optional[float],  # for closing positions (partial or full)
    'cost': Optional[float],  # USDT amount for opening/adding positions
    'take_profit': Optional[float],
    'stop_loss': Optional[float],
    'reason': str,
    'summary': str
})
    
HISTORY_TIME_FORMAT = "%Y-%m-%dT%H:%M"
@dataclass
class Params(ParamsBase):
    # 杠杆倍率
    news_platforms: List[str]
    risk_prefer: str = "风险喜好型"

FutureData = TypedDict('FutureData', {
    'last_funding_rate': float,
    'global_long_short_account_ratio': float,
    'top_long_short_account_ratio': float,
    'top_long_short_ratio': float,
})

def format_history(history_obj) -> str:
    if history_obj['action'] == 'buy_long':
        return f"{history_obj['timestamp']} 开仓做多，杠杆倍率:{history_obj['leverage']}, 仓位:{history_obj['position_percentage']}%, 止盈{history_obj['take_profit']}, 止损{history_obj['stop_loss']}, 理由:{history_obj['reason']}"

    if history_obj['action'] == 'sell_short':
        return f"{history_obj['timestamp']} 开仓做空，杠杆倍率:{history_obj['leverage']}, 仓位:{history_obj['position_percentage']}%, 止盈{history_obj['take_profit']}, 止损{history_obj['stop_loss']}, 理由:{history_obj['reason']}"
    
    if history_obj["action"] == "hold":
        if history_obj["take_profit"] and history_obj["stop_loss"]:
            return f"{history_obj['timestamp']} 观望，调整止盈价为{history_obj['take_profit']}, 止损价为{history_obj['stop_loss']}, 理由:{history_obj['reason']}"
        if history_obj["take_profit"]:
            return f"{history_obj['timestamp']} 观望，调整止盈价为{history_obj['take_profit']}, 理由:{history_obj['reason']}"
        if history_obj["take_profit"]:
            return f"{history_obj['timestamp']} 观望，调整止损价为{history_obj['stop_loss']}, 理由:{history_obj['reason']}"
    
    if history_obj["action"] == "add_position_long":
        return f"{history_obj['timestamp']} 加仓做多，仓位：{history_obj['position_percentage']}%, 止盈{history_obj['take_profit']}, 止损{history_obj['stop_loss']}, 理由:{history_obj['reason']}"

    if history_obj["action"] == "add_position_short":
        return f"{history_obj['timestamp']} 加仓做空，仓位：{history_obj['position_percentage']}%, 止盈{history_obj['take_profit']}, 止损{history_obj['stop_loss']}, 理由:{history_obj['reason']}"
    
    if history_obj["action"] == "reduce_position_long":
        return f"{history_obj['timestamp']} 多仓减仓，仓位：{history_obj['position_percentage']}%, 止盈{history_obj['take_profit']}, 止损{history_obj['stop_loss']}, 理由:{history_obj['reason']}"
    
    if history_obj["action"] == "reduce_position_short":
        return f"{history_obj['timestamp']} 空仓减仓，仓位：{history_obj['position_percentage']}%, 止盈{history_obj['take_profit']}, 止损{history_obj['stop_loss']}, 理由:{history_obj['reason']}"

    if history_obj["action"] == "long_close":
        return f"{history_obj['timestamp']} 平多, 理由:{history_obj['reason']}"
    
    if history_obj["action"] == "short_close":
        return f"{history_obj['timestamp']} 平空, 理由:{history_obj['reason']}"

    if history_obj["action"] == "take_profit_success":
        return f"{history_obj['timestamp']} 止盈成功"

    if history_obj["action"] == "stop_loss_success":
        return f"{history_obj['timestamp']} 止损成功"

    if history_obj["action"] == "force_close":
        return f"{history_obj['timestamp']} 爆仓！"

    return "ERROR"

def get_position_percentage(a: float, b: float) -> int:
    return int((a / (a + b)) * 100)

class OtherOperationsApi(abc.ABC):

    @abc.abstractmethod
    def set_leverate(self, symbol: str, leverage: int):
        pass

    @abc.abstractmethod
    def create_future_order(self, symbol: str, order_type: str, order_side: str, amount: float, postion_side: str, price: float = None, stop_price: float = None) -> OrderInfo:
        pass
    
    @abc.abstractmethod
    def market_future_data(self, symbol: str) -> FutureData:
        pass 

    @abc.abstractmethod
    def get_position_info(self, symbol: str, side: Literal['long', 'short']) -> PositionRisk:
        pass 

    @abc.abstractmethod
    def get_ohlcv_history(self, symbol: str, time_frame: CryptoHistoryFrame, limit: int) -> List[Ohlcv]:
        pass

    @abc.abstractmethod
    def get_order(self, symbol: str, order_id: str) -> OrderInfo:
        pass 

    @abc.abstractmethod
    def cancel_order(self, symbol: str, order_id: str):
        pass 

    @abc.abstractmethod
    def get_latest_price(self, symbol: str) -> float:
        pass

class OtherOperations(OtherOperationsApi):
    def __init__(self):
        self.binance = BinanceExchange(future_mode=True)
        self.exchange_proxy = CryptoProxy(ModuleDependency(exchange=self.binance))
    
    def set_leverate(self, symbol: str, leverage: int):
        logger.debug(f"set_leverate {symbol} {leverage}")
        self.binance.binance.fapiPrivatePostLeverage({ 'symbol': symbol, 'leverage': leverage })

    def get_latest_price(self, symbol: str) -> float:
        logger.debug(f"get_latest_price {symbol}")
        return self.binance.binance.fetch_ticker(symbol=symbol)['last']

    def cancel_order(self, symbol: str, order_id: str):
        logger.debug(f"cancel_order {symbol} {order_id}")
        self.binance.binance.cancel_order(order_id, symbol)

    def _transform_order(self, raw_order) -> OrderInfo:
        return {
            'orderId': raw_order['orderId'],
            'status': raw_order['status'],
            'avgPrice': float(raw_order['avgPrice']),
            'executedQty': float(raw_order['executedQty']),
            'cumQuote': float(raw_order['cumQuote']),
            'reduceOnly': bool(raw_order['reduceOnly']),
            'closePosition': bool(raw_order['closePosition']),
            'stopPrice': float(raw_order['stopPrice']),
            'updateTime': int(raw_order['updateTime'])
        }
    def get_order(self, symbol: str, order_id: str) -> OrderInfo:
        logger.debug(f"get_order {symbol} {order_id}")
        raw_order = self.binance.binance.fetch_order(order_id, symbol)['info']
        logger.debug(raw_order)
        return self._transform_order(raw_order)

    def get_ohlcv_history(self, symbol: str, time_frame: CryptoHistoryFrame, limit: int) -> List[Ohlcv]:
        # 复用一下现货的接口，可以存缓存，这里假设现货价格和合约价格差别不大, 存进去缓存没问题。
        logger.debug(f"get_ohlcv_history {symbol} {time_frame} {limit}")
        return self.exchange_proxy.get_ohlcv_history(
            symbol, 
            time_frame, 
            datetime.now() - timedelta(seconds = limit *  timeframe_to_second(time_frame)), 
            datetime.now()
        ).data

    def get_position_info(self, symbol: str, side) -> Optional[PositionRisk]:
        logger.debug(f"get_position_info {symbol} {side}")
        rsp = self.binance.binance.fapiPrivateV2GetPositionRisk(params={ 'symbol': symbol.replace('/', '') })
        assert isinstance(rsp, list)
        position_info: dict = next((item for item in rsp if item['positionSide'] == side.upper()), None)
        if position_info is None:
            return None
        for key in position_info.keys():
            if key == 'positionSide':
                continue
            if key == 'isolated':
                position_info[key] = bool(position_info[key])
                continue
            if key in ['updateTime', 'leverage']:
                position_info[key] = int(position_info[key])
            if re.fullmatch(r"^[-+]?\d*\.?\d+$", position_info[key]):
                position_info[key] = float(position_info[key])
        return position_info

    # https://developers.binance.com/docs/zh-CN/derivatives/usds-margined-futures/trade/rest-api
    def create_future_order(self, symbol: str, order_type: str, order_side: str, amount: float, postion_side: str, price: float = None, stop_price: float = None) -> OrderInfo:
        logger.debug(f"create_future_order {symbol} {order_type} {order_side} {amount} {postion_side} {price} {stop_price}")
        created_order = self.binance.binance.create_order(
            symbol=symbol,
            type=order_type,
            side=order_side,
            amount=amount,
            price=price,
            params = {
                'positionSide': postion_side.upper(),
                'stopPrice': stop_price
            }
        )['info']
        logger.debug(created_order)
        return self._transform_order(created_order)

    def market_future_data(self, symbol: str) -> FutureData:
        logger.debug(f"market_future_data {symbol}")
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
        self._voter_idx = 0

    def get_a_voter_agent(self):
        voter = self.result_voter_agents[self._voter_idx]
        self._voter_idx = (self._voter_idx + 1) % len(self.result_voter_agents)
        return voter

class Context(BasicContext[ContextDict]):
    deps: Dependency
    def __init__(self, params: Params, deps: Dependency):
        super().__init__(f'{params.symbol}_{params.money}_{params.data_frame}_future_GPT', deps)
        self.params = params

    def _initial_context(self) -> ContextDict:
        return {
            'account_money_amount': self.params.money,
            'account_symbol_amount': 0,
            'position_status': 'init',
            'history': []
        }

    def _stop_position_if_need(self, amount: int, curr_price: float, take_profit: float, stop_loss: float, postion_side: str, legacy_stop_orders: List[OrderInfo]):
        unresolved_take_profit_order = filter_by(legacy_stop_orders, lambda o: o['status'] != 'FILLED' and o['origType'] == 'TAKE_PROFIT_MARKET')
        unresolved_stop_loss_order = filter_by(legacy_stop_orders, lambda o: o['status'] != 'FILLED' and o['origType'] == 'STOP_MARKET')
        result = {
            'stop_loss_order': None,
            'take_profit_order': None
        }
        if take_profit and postion_side == 'long' and take_profit > curr_price:
            map_by(unresolved_take_profit_order, lambda o: self.deps.other_operations.cancel_order(self.params.symbol, o['orderId']))
            result['take_profit_order'] = self._stop_position(curr_price, amount, take_profit, True, False, True)
        if stop_loss and postion_side == 'long' and stop_loss < curr_price:
            map_by(unresolved_stop_loss_order, lambda o: self.deps.other_operations.cancel_order(self.params.symbol, o['orderId']))
            result['stop_loss_order'] = self._stop_position(curr_price,amount, stop_loss, True, False, False)
        if take_profit and postion_side == 'short' and take_profit < curr_price:
            map_by(unresolved_take_profit_order, lambda o: self.deps.other_operations.cancel_order(self.params.symbol, o['orderId']))
            result['take_profit_order'] = self._stop_position(curr_price,amount, take_profit, False, True, True)
        if stop_loss and postion_side == 'short' and stop_loss > curr_price:
            map_by(unresolved_stop_loss_order, lambda o: self.deps.other_operations.cancel_order(self.params.symbol, o['orderId']))
            result['stop_loss_order'] = self._stop_position(curr_price, amount, stop_loss, False, True, False)
        return result

    def _stop_position(self, curr_price: float, amount: int, stop_price: float, is_long: bool, is_buy: bool, is_take_profit: bool) -> OrderInfo:
        stop_position_order = self.deps.other_operations.create_future_order(
            self.params.symbol, 
            'TAKE_PROFIT_MARKET' if is_take_profit else 'STOP_MARKET', 
            'buy' if is_buy else 'sell',
            amount,
            'long' if is_long else 'short',
            stop_price=stop_price
        )
        self.set('take_profit_order_id' if is_take_profit else 'stop_loss_order_id', stop_position_order['orderId'])
        self.deps.notification_logger.msg(
            '做多' if is_long else '做空', 
            '止盈' if is_take_profit else '止损', 
            f'{round_to_5(change_rate(curr_price, stop_price) * 100)} %'
        )
        return stop_position_order

    def hold_position(self, take_profit: float, stop_loss: float, legacy_stop_orders: List[OrderInfo], reason: str):
        result = self._stop_position_if_need(
            self.get('account_symbol_amount'), 
            self.deps.other_operations.get_latest_price(self.params.symbol), 
            take_profit, 
            stop_loss,
            self.get('position_status'),
            legacy_stop_orders,
        )
        if result['stop_loss_order'] or result['take_profit_order']:
            order: OrderInfo = result['stop_loss_order'] or result['take_profit_order']
            self.append('history', {
                "timestamp": ts_to_dt(order['updateTime']).strftime(HISTORY_TIME_FORMAT),
                "action": 'hold',
                'take_profit': take_profit if result['take_profit_order'] else None,
                'stop_loss': stop_loss if result['stop_loss_order'] else None,
                "reason": reason
            })
        return 

    def reduce_position(self, amount: float, take_profit: float, stop_loss: float, legacy_stop_orders: List[OrderInfo], reason: str):
        position_side = self.get('position_status')
        reduce_position_order = self.deps.other_operations.create_future_order(
            self.params.symbol, 
            'market', 
            'sell' if position_side == 'long' else 'buy',
            amount,
            position_side
        )
        current_price = reduce_position_order['avgPrice']
        self.decreate('account_symbol_amount', reduce_position_order['executedQty'])
        self.increate('account_money_amount', reduce_position_order['cumQuote'] / self.get('position_leverage'))
        self.deps.notification_logger.msg('平仓', '卖出' if position_side == 'long' else '买入', reduce_position_order['executedQty'],'份')
        
        if self.get('account_symbol_amount') == 0 or reduce_position_order['closePosition']:
            self.delete('take_profit_order_id')
            self.delete('stop_loss_order_id')
            self.delete('position_leverage')
            self.set('position_status', 'close')
            self.append('history', {
                'timestamp': ts_to_dt(reduce_position_order['updateTime']).strftime(HISTORY_TIME_FORMAT),
                'action': position_side + '_close',
                'reason': reason
            })
            # 应该不需要取消止盈止损单
            return
        position_percentage = get_position_percentage(self.get('account_symbol_amount') * current_price, self.get('account_money_amount'))
        self.append('history', {
            'timestamp': ts_to_dt(reduce_position_order['updateTime']).strftime(HISTORY_TIME_FORMAT),
            'action': 'reduce_position_' + position_side,
            'take_profit': take_profit,
            'stop_loss': stop_loss,
            'position_percentage': position_percentage,
            'reason': reason
        })
        self._stop_position_if_need(self.get('account_symbol_amount'), reduce_position_order['avgPrice'], take_profit, stop_loss, position_side, legacy_stop_orders)
        return
        
    def add_position(self, cost: float, position_side: Literal['long', 'short'], take_profit: float, stop_loss: float, legacy_stop_orders: List[OrderInfo], reason: str):
        position_leverage = self.get('position_leverage')
        current_price = self.deps.other_operations.get_latest_price(self.params.symbol)
        increase_symbol_amount_around = round_to_5(cost * position_leverage / current_price)
        add_position_order = self.deps.other_operations.create_future_order(
            self.params.symbol, 
            'market', 
            'buy' if position_side == 'long' else 'sell',
            increase_symbol_amount_around,
            position_side,
        )
        self.increate('account_symbol_amount', add_position_order['executedQty'])
        if add_position_order['cumQuote'] / position_leverage >= self.get('account_money_amount'):
            self.set('account_money_amount', 0)
        else:
            self.decreate('account_money_amount', add_position_order['cumQuote'] / position_leverage)
        if self.get('position_status') == 'close':
            self.set('position_status', position_side)
            position_percentage = get_position_percentage(add_position_order['cumQuote'] / position_leverage, self.get('account_money_amount'))
            self.append('history', {
                'timestamp': ts_to_dt(add_position_order['updateTime']).strftime(HISTORY_TIME_FORMAT),
                'action': 'buy_long' if position_side == 'long' else 'sell_short',
                'leverage': self.get('position_leverage'),
                'cost': add_position_order['cumQuote'] / position_leverage,
                'amount': add_position_order['executedQty'],
                'take_profit': take_profit,
                'stop_loss': stop_loss,
                'position_percentage': position_percentage,
                'reason': reason
            })
        else:
            position_percentage = get_position_percentage(add_position_order['cumQuote'] / position_leverage + self.get('account_symbol_amount') * current_price, self.get('account_money_amount'))
            self.append('history', {
                'timestamp': ts_to_dt(add_position_order['updateTime']).strftime(HISTORY_TIME_FORMAT),
                'action': 'add_position_' + position_side,
                'cost': add_position_order['cumQuote'] / position_leverage,
                'amount': add_position_order['executedQty'],
                'take_profit': take_profit,
                'stop_loss': stop_loss,
                'position_percentage': position_percentage,
                'reason': reason
            })
        self._stop_position_if_need(add_position_order['executedQty'], add_position_order['avgPrice'], take_profit, stop_loss, position_side, legacy_stop_orders)
        return

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

def construct_system_prompt(coinname: str, risk_prefer: str) -> str:
    return f"""你是一位经验丰富的加密货币交易专家，擅长分析市场数据、技术指标和新闻信息。现在是一个新的交易时段，请按照以下流程对 **{coinname}** 进行 **1小时级别** 短线技术分析，并在必要时灵活使用杠杠来放大收益。

1. **价格与K线形态分析**  
   - 分析过去若干小时到数天的OHLCV数据（1小时K线），结合检测到的短期K线形态以及过去7天的OHLCV数据（日K线），判断近期趋势走向以及是否存在明显的短期波动机会。

2. **短周期技术指标分析**  
   - 结合常用指标（如SMA、RSI、MACD、布林带、KDJ、ATR 等），着重关注这些指标在短周期下的快速变化、趋势强度以及潜在反转信号。
   - 由于我们将使用杠杆，请仔细评估当前波动率和风险水平，判断是否需要加快或者放缓交易动作。

3. **新闻与市场情绪分析**  
   - 综合过去一个小时最新的外部信息，如市场热点事件、监管动态、行业新闻等，评估其在短期内对价格可能造成的快速影响。

4. **回顾交易历史与仓位、风险分析**  
   - 参考已有的交易历史、当前仓位和风险偏好（{risk_prefer}），在确定的买多（开多）、卖多（平多）、卖空（开空）、买入平空（平空）等策略中，给出最合理的决策。
   - 请注意：我倾向于短期交易以捕捉波段机会，但仍需考虑整体风险控制，严格设定杠杆倍数与止盈止损范围。

你的回复必须是一个JSON结构体，定义如下：  
- **action(required)**: 建议操作类型，可选值：  
  - `"buy_long"`：买入开仓
  - `"sell_long"`：卖出平仓
  - `"sell_short"`：卖出开仓
  - `"buy_short"`：买入平仓
  - `"add_position"`: 加仓
  - `"hold"`：保持观望  
- **leverage(optional)**: 使用杠杆倍数（2至5，开仓时使用，后续加仓不可用）。  
- **amount(optional)**: 平单时平掉的合约数量。  
- **cost(optional)**: 开仓或加仓所需USDT金额（开仓/加仓时提供）。  
- **take_profit(optional)**: 止盈价格。观望时可以不给出。
- **stop_loss(optional)**: 止损价格，防止爆仓。观望时可以不给出。
- **reason(required)**: 详细分析报告，必须包括：
  1. **OHLCV分析**：1小时短周期价格走势与K线形态。  
  2. **技术指标分析**：评估 SMA、RSI、BOLL、MACD、KDJ、ATR 等。  
  3. **新闻/市场情绪分析**：评估市场热点或外部影响。  
  4. **仓位与风险偏好分析**：杠杆选择及风险收益评估。  
  5. **止盈止损设置分析**：说明设置逻辑及保护作用。  
- **summary(required)**: 30字左右总结交易理由，用于复盘。  

请注意：  
1. **不要超过**我当前可用的 USDT 余额或{coinname}合约持仓量。  
2. 开仓时所需 **USDT** 不能低于 5 USDT，总价值过小会导致无法执行交易；同理，平仓的仓位总价值也需至少5 USDT。  
3. 请谨慎使用杠杆，不要盲目放大头，最大可使用5倍杠杆，我的风险偏好是{risk_prefer}。
4. 遇不确定时，可保持观望（`"hold"`），只有原先的止盈或止损价格已经不太合理了才重新设置止盈或止损价格，并且要说明新止盈止损价的理由。
5. take_profit和stop_loss可以在开仓/加仓/平仓/观望时使用，如果原有的止盈止损价格已经足够合理可以不给出，在提供止盈止损价格时，原先的仓位止盈止损价格将作废，并对整个仓位的止盈止损进行重新设置。做空的止盈价格应该比当前价格低，止损价格比当前价格高，做多的止盈价格应该比当前价格高，止损价格比当前价格低。设置止损价格时，不要超过给出的爆仓价格。
6. 不要因为仓位投入的金额太小而每次开仓都all in，要在趋势和消息足够利好时开仓

响应格式示例
```json
Example A(开多,花费100USDT做保证金，使用2倍杠杆， 当前价格为0.065, 买入2 * 100 / 0.065 = 3076份，止盈0.078, 止损0.052， 0.0325爆仓):
{{
    "action": "buy_long",
    "leverage": 2,
    "take_profit": 0.078,
    "stop_loss": 0.052,
    "cost": 100.0,
    "summary": "短期回调充分，配合利好新闻加杠杆布局",
    "reason": "1. OHLCV分析：1小时K线显示近6小时内价格在支撑位筑底，成交量温和放大；\\n2. 技术指标分析：SMA5(0.065)上穿SMA20(0.062)，RSI(35)接近超卖区即将反弹，布林带收口但价格临近下轨，MACD金叉初现，KDJ与ATR显示短线波动加剧适合小幅杠杆进场；\\n3.新闻分析：主流媒体报道某龙头交易所上线DOGE衍生品，刺激市场关注度；\\n4.仓位与风险分析：当前空仓较多，风险承受度充足，使用2倍杠杆开多但需密切监控波动。"
}}
Example B(开空，花费50USDT做保证金，使用3倍杠杆，当前价格为0.073, 卖出2 * 50 / 0.073 = 1369.8份，止盈0.06, 止损0.08,， 0.097爆仓):
{{
    "action": "sell_short",
    "leverage": 3.0,
    "cost": 50.0,
    "take_profit": 0.06,
    "stop_loss": 0.08,
    "summary": "短线高位承压，选择3倍杠杆进场做空",
    "reason": "1. OHLCV分析：1小时K线持续上行后出现顶部十字星形态，成交量放大但价格未能继续冲高；\\n2.技术指标分析：SMA5(0.075)下穿SMA20(0.078)，RSI(72)超买区域，布林带上轨被多次触及，MACD死叉形成，KDJ快速下行，ATR显示波动率上升；\\n3.新闻分析：最新宏观数据利空，市场担忧情绪上升；\\n4.仓位与风险分析：当前已有一部分多单获利平仓，风险较可控，可用少量资金在3倍杠杆上尝试短线做空，及时设置止损。"
}}
Example C(平多，卖出一部分的合约，假设多仓持有400份，这里卖出200份，平掉一半仓位锁定利润/及时止损，并重新设置止盈止损，0.3爆仓):
{{
    "action": "sell_long",
    "amount": 200.0,
    "take_profit": 0.8,
    "stop_loss": 0.5,
    "summary": "短期见顶信号明显，先行止盈",
    "reason": "..."
}}
Example D(平多，卖出所有的合约，假设仓位总共400份，平掉整个仓位锁定利润/及时止损，不设置止盈止损，因为没有意义):
{{
    "action": "sell_long",
    "amount": 400.0,
    "summary": "...",
    "reason": "..."
}}
Example E(加仓，假设现在是做多，并设置新的止盈止损):
{{
    "action": "add_position",
    "cost": 100.0,
    "take_profit": 0.078,
    "stop_loss": 0.052,
    "summary": "...",
    "reason": "..."
}}
Example F(加仓，假设现在是做空，并设置新的止盈止损):
{{
    "action": "add_position",
    "cost": 100.0,
    "take_profit": 0.052,
    "stop_loss": 0.078,
    "summary": "...",
    "reason": "..."
}}
Example G(加仓，不设置新的止盈止损，使用原有的止盈止损):
{{
    "action": "add_position",
    "cost": 100.0,
    "summary": "...",
    "reason": "..."
}}
Example H(观望，不设置新的止盈止损，使用原有的止盈止损):
{{
    "action": "hold",
    "reason": "...",
    "summary": "..."
}}
Example I(观望，设置新的止盈止损，废弃原有的止盈止损):
{{
    "action": "hold",
    "reason": "...",
    "take_profit": 0.052,
    "stop_loss": 0.078,
    "reason": "...",
    "summary": "..."
}}
Example J(观望，设置新的止盈，废弃原有的止盈):
{{
    "action": "hold",
    "reason": "...",
    "take_profit": 0.052,
    "reason": "...",
    "summary": "..."
}}
```
"""

def format_position_info(context: Context, position_info: PositionInfo) -> str:
    position_status: str = context.get('position_status')
    if position_status == 'close':
        return f'- 空仓中'
    result = []
    percentage = get_position_percentage(abs(position_info["position_risk"]["notional"]) / context.get("position_leverage"), context.get("account_money_amount"))
    if position_status == 'long':
        result.append(f'- 仓位方向：做多')
        result.append(f'- 仓位水平 {percentage}%')
        result.append(f'- 持有数量 {position_info["position_risk"]["positionAmt"]}')
        result.append(f'- 杠杆倍率 {position_info["position_risk"]["leverage"]}')
        result.append(f'- 爆仓价格 {position_info["position_risk"]["liquidationPrice"]}')
        result.append(f'- 止损价格 {position_info["stop_loss_order"]["stopPrice"]}')
        result.append(f'- 止盈价格 {position_info["take_profit_order"]["stopPrice"]}')
    if position_status == 'short':
        result.append(f'- 仓位方向：做空')
        result.append(f'- 仓位水平 {percentage}%')
        result.append(f'- 持有数量 {abs(position_info["position_risk"]["positionAmt"])}')
        result.append(f'- 杠杆倍率 {position_info["position_risk"]["leverage"]}')
        result.append(f'- 爆仓价格 {position_info["position_risk"]["liquidationPrice"]}')
        result.append(f'- 止损价格 {position_info["stop_loss_order"]["stopPrice"]}')
        result.append(f'- 止盈价格 {position_info["take_profit_order"]["stopPrice"]}')
    return '\n'.join(result)

def construct_user_prompt(context: Context, coin_name: str, data_1h: List[Ohlcv], data_1d:List[Ohlcv], indicators_1h: TechnicalIndicators, news_1h_text: str, future_data: FutureData, position_info: PositionInfo, history: List[str]) -> str:
    ohlcv_1d_text = format_ohlcv_list(data_1d, 7)
    ohlcv_1h_text = format_ohlcv_list(data_1h, 30)
    history_text = '\n'.join(map_by(history, format_history))
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

4. 新闻:
- 过去一小时内的最新相关新闻如下
```
{news_1h_text}
```

5. 币安交易所{coin_name}此刻的U本位合约数据：
- 多空持仓人数比：{future_data['global_long_short_account_ratio']}
- 大户账户数多空比: {future_data['top_long_short_account_ratio']}
- 大户持仓量多空比: {future_data['top_long_short_ratio']}
- 资金费率：{'{:.20f}'.format(future_data['last_funding_rate']).rstrip('0').rstrip('.')}

6. 当前仓位信息:
- 可用于加仓的USDT余额：{round_to_5(context.get('account_money_amount'))}
{format_position_info(context, position_info)}

7. 最近10次以内交易历史
{history_text}

请根据这些信息分析市场趋势，并给出具体的交易建议。
"""

def get_position_info(context: Context) -> Optional[PositionInfo]:
    if context.get('position_status') in ['long', 'short']:
        take_profit_id = context.get('take_profit_order_id')
        stop_loss_id = context.get('stop_loss_order_id')
        take_profit_order: OrderInfo = context.deps.other_operations.get_order(context.params.symbol, take_profit_id)
        stop_loss_order: OrderInfo = context.deps.other_operations.get_order(context.params.symbol, stop_loss_id)
        position_risk = context.deps.other_operations.get_position_info(context.params.symbol, context.get('status'))
        return {
            'is_position_closed': position_risk is None,
            'is_stop_order_resolve': take_profit_order['status'] == 'FILLED' or stop_loss_order['status'] == 'FILLED',
            'take_profit_order': take_profit_order,
            'stop_loss_order': stop_loss_order,
            'position_risk': position_risk
        }
    return None

def update_context_info(context: Context, position_info: Optional[PositionInfo]) -> None:
    logger.info(f"仓位信息：{position_info}")
    if position_info is not None and context.get('position_status') != 'close':
        if position_info['is_stop_order_resolve']:
            context.set('position_status', 'close')
            leverage = position_info['position_risk']['leverage']
            if position_info['take_profit_order']['status'] == 'FILLED':
                take_profit_order: OrderInfo = position_info['take_profit_order']
                close_time = ts_to_dt(take_profit_order["updateTime"]).strftime(HISTORY_TIME_FORMAT)
                context.append('history', {
                    'timestamp': close_time,
                    'action': 'take_profit_success'
                })
                context.deps.notification_logger.msg("仓位已经被止盈平仓")
                context.increate('account_money_amount', round_to_5(take_profit_order['cumQuote'] / leverage))
                context.set('account_symbol_amount', 0)
            else:
                stop_loss_order: OrderInfo = position_info['stop_loss_order']
                close_time = ts_to_dt(stop_loss_order["updateTime"]).strftime(HISTORY_TIME_FORMAT)
                context.append('history', {
                    'timestamp': close_time,
                    'action': 'stop_loss_success'
                })
                context.deps.notification_logger.msg("仓位已经被止损平仓")
                context.increate('account_money_amount', round_to_5(stop_loss_order['cumQuote'] / leverage))
                context.set('account_symbol_amount', 0)
        else:
            position_risk: PositionRisk = position_info['position_risk']
            close_time = ts_to_dt(position_risk['updateTime']).strftime(HISTORY_TIME_FORMAT)
            context.set('position_status', 'force_close')
            context.set('account_symbol_amount', 0)
            context.append('history', {
                'timestamp': close_time,
                'action': 'force_close'
            })
            context.deps.notification_logger.msg("仓位已经爆仓")

def validate_gpt_reply(gpt_reply_text, context: Context, position_info: PositionInfo, curr_price: float) -> dict:
    try:
        logger.info(gpt_reply_text)
        advice_json = extract_json_string(gpt_reply_text)
        assert isinstance(advice_json, dict), "GPT回复必须是一个字典格式"
        assert 'action' in advice_json, "GPT回复缺少'action'字段"
        assert advice_json['action'] in ['buy_long', 'sell_long', 'sell_short', 'buy_short', 'add_position', 'hold'], f"无效的action值: {advice_json['action']}"
        assert 'reason' in advice_json, "GPT回复缺少'reason'字段"
        assert isinstance(advice_json['reason'], str), "'reason'字段必须是字符串类型"

        if advice_json['action'] in ['buy_long', 'sell_short']:
            assert 'leverage' in advice_json,  "开仓时GPT回复缺少'leverage'字段"
            assert isinstance(advice_json['leverage'], (int, float)), "'leverage'字段必须是数字类型"
            assert 2 <= advice_json['leverage'] <= 5, "'leverage'字段必须在2到5之间"
            assert 'cost' in advice_json, "开仓时GPT回复缺少'cost'字段"
            assert isinstance(advice_json['cost'], (int, float)), "'cost'字段必须是数字类型"
            assert advice_json['cost'] >= 5, "'cost'字段必须大于等于5"

        if advice_json['action'] in ['sell_long', 'buy_short']:
            assert 'amount' in advice_json, "平仓时GPT回复缺少'amount'字段"
            assert isinstance(advice_json['amount'], (int, float)), "'amount'字段必须是数字类型"
            assert advice_json['amount'] > 0, "'amount'字段必须大于0"

        if advice_json['action'] == 'add_position':
            assert 'cost' in advice_json, "加仓时GPT回复缺少'cost'字段"
            assert isinstance(advice_json['cost'], (int, float)), "'cost'字段必须是数字类型"
            assert advice_json['cost'] >= 5, "'cost'字段必须大于等于5"

        if 'cost' in advice_json:
            assert advice_json['cost'] <= context.get('account_money_amount'), "加仓超过剩余余额"
        
        if 'amount' in advice_json:
            assert advice_json['amount'] <= context.get('account_symbol_amount'), "减仓超过仓位"

        if 'take_profit' in advice_json:
            assert isinstance(advice_json['take_profit'], (int, float)), "'take_profit'字段必须是数字类型"
            if context.get('position_status') == 'long' or advice_json['action'] == 'buy_long':
                assert advice_json['take_profit'] > curr_price, f"'take_profit'<={curr_price}"
            elif context.get('position_status') == 'short' or advice_json['action'] == 'sell_short':
                assert advice_json['take_profit'] < curr_price, f"'take_profit'>={curr_price}"

        if 'stop_loss' in advice_json:
            assert isinstance(advice_json['stop_loss'], (int, float)), "'stop_loss'字段必须是数字类型"
            if context.get('position_status') == 'long' or advice_json['action'] == 'buy_long':
                assert advice_json['take_profit'] < curr_price, f"'take_profit'>={curr_price}"
            elif context.get('position_status') == 'short' or advice_json['action'] == 'sell_short':
                assert advice_json['take_profit'] > curr_price, f"'take_profit'<={curr_price}"

        if advice_json['action'] == 'hold':
            if 'take_profit' in advice_json and advice_json['take_profit'] == position_info['take_profit_order']['stopPrice']:
                logger.warning("GPT response with a unchanged take profit value")
                del advice_json['take_profit']
            if 'stop_loss' in advice_json and advice_json['stop_loss'] == position_info['stop_loss_order']['stopPrice']:
                logger.warning("GPT response with a unchanged stop loss value")
                del advice_json['stop_loss']
        # TODO: 校验止盈止损价格合理

        return advice_json
    except Exception as err:
        raise GptReplyNotValid(err)

def gpt_analysis(context: Context, data_1h: List[Ohlcv], data_1d: List[Ohlcv], indicators_1h: TechnicalIndicators, news_1h_text: str, future_data: FutureData, position_info: PositionInfo) -> CryptoFutureTradeAction:
    coin_name = context.params.symbol.rstrip('USDT').rstrip('/')
    news_summary = summary_news(news_1h_text, context.deps.news_summary_agent, coin_name)
    sys_prompt = construct_system_prompt(coin_name, context.params.risk_prefer)
    user_prompt = construct_user_prompt(context, coin_name, data_1h, data_1d, indicators_1h, news_summary, future_data, position_info, context.get('history'))
    logger.debug(sys_prompt)
    logger.debug(user_prompt)
    @with_retry((GptReplyNotValid), 5)
    def retryable_part():
        agent = context.deps.get_a_voter_agent()
        agent.set_system_prompt(sys_prompt)
        return validate_gpt_reply(agent.ask(user_prompt), context, position_info, data_1h[-1].close)

    return retryable_part()


def strategy(context: Context):
    params: Params = context.params
    logger.debug(f"Context: {context._context}")
    position_info = get_position_info(context)
    update_context_info(context, position_info)
    data_1h = context.deps.other_operations.get_ohlcv_history(params.symbol, '1h', 48)
    data_1d = context.deps.other_operations.get_ohlcv_history(params.symbol, '1d', 7)
    indicators_1h = calculate_technical_indicators(data_1h)
    news_by_platform = {}
    for platform in params.news_platforms:
        news_by_platform[platform] = context.deps.news_api.get_news_during(platform, data_1h[-1].timestamp, data_1h[-1].timestamp + timedelta(hours=1))
    news_1h_text = render_news_in_markdown_group_by_platform(news_by_platform)
    logger.debug(news_1h_text)
    future_data = context.deps.other_operations.market_future_data(params.symbol)

    result = gpt_analysis(context, data_1h, data_1d, indicators_1h, news_1h_text, future_data, position_info)
    if result['action'] in ['buy_long', 'sell_short']:
        context.set('position_leverage', result['leverage'])
        context.deps.other_operations.set_leverate(params.symbol, result['leverage'])

    legacy_stop_orders = []
    if position_info:
        legacy_stop_orders.append(position_info['stop_loss_order'])
        legacy_stop_orders.append(position_info['take_profit_order'])

    if result['action'] == 'buy_long':
        context.add_position(result['cost'], 'long', result['take_profit'], result['stop_loss'], legacy_stop_orders, result['summary'])
    elif result['action'] == 'sell_short':
        context.add_position(result['cost'], 'short', result['take_profit'], result['stop_loss'], legacy_stop_orders, result['summary'])
    elif result['action'] == 'add_position':
        context.add_position(result['cost'], context.get('position_status'), result['take_profit'], result['stop_loss'], legacy_stop_orders, result['summary'])
    elif result['action'] == 'sell_long':
        context.reduce_position(result['amount'], result['take_profit'], result['stop_loss'], legacy_stop_orders, result['summary'])
    elif result['action'] == 'buy_short':
        context.reduce_position(result['amount'], result['take_profit'], result['stop_loss'], legacy_stop_orders, result['summary'])
    else:
        context.hold_position(
            result.get('take_profit'),
            result.get('stop_loss'),
            legacy_stop_orders,
            result.get('summary')
        )


def run(cmd_params: dict, notification: NotificationLogger):
    params = Params(
        money=cmd_params.get('money'), 
        data_frame='1h',
        symbol = cmd_params.get('symbol'),
        risk_prefer=cmd_params.get('risk_prefer'),
        news_platforms=cmd_params.get('news_platforms', ['jin10', 'cointime'])
    )
    deps = Dependency(
        notification=notification,
        news_summary_agent=get_agent_by_model(cmd_params.get('news_summary_agent')),
        result_voter_agents=map_by(cmd_params.get('voter_agents'), lambda m: get_agent_by_model(m, { "temperature": 0.2 }))
    )
    with Context(params = params, deps=deps) as context:
        strategy(context)