from dataclasses import dataclass
from typing import Optional, TypedDict

from lib.utils.number import change_rate

from ..utils.ohlcv import boll_info
from ..modules.notification_logger import NotificationLogger
from ..modules.strategy import BasicDependency, ParamsBase, BasicContext
from .common import get_recent_data_with_at_least_count

ContextDict = TypedDict('Context', {
    'account_usdt_amount': float,
    'account_coin_amount': float,
    'buyable': bool,
    'sellable': bool,
    'max_price': float
})

@dataclass
class Params(ParamsBase):
    max_retrieval: Optional[float] = None

class Context(BasicContext[ContextDict]):
    def __init__(self, params: Params, deps: BasicDependency):
        super().__init__(f'{params.symbol}_{params.data_frame}_{params.money}_BOLL', deps)
        self.params = params
    
    def _initial_context(self) -> ContextDict:
        return {
            'account_usdt_amount': self.params.money,
            'account_coin_amount': 0,
            'buyable': True,
            'sellable': False
        }

def boll(context: Context):
    params: Params = context.params
    deps = context.deps
    
    data = get_recent_data_with_at_least_count(21, params.symbol, params.data_frame, deps.exchange)

    close_price = data[-1].close
    boll_result = boll_info(data)

    if context.get('sellable') and context.get('max_price') < close_price:
        context.set('max_price', close_price)

    if context.get('buyable') and boll_result['is_turn_good']:
        order = deps.exchange.create_order(params.symbol, 'market', 'buy', f'BOLL_PLAN_{params.symbol}', spent = context.get('account_usdt_amount'))
        context.set('account_coin_amount', context.get('account_coin_amount') + order.get_amount(True))
        context.set('account_usdt_amount', context.get('account_usdt_amount') - order.get_cost(True))
        context.set('buyable', False)
        context.set('sellable', True)
        context.set('max_price', close_price)
        deps.notification_logger.msg(f'{order.timestamp} 花费 ', order.get_cost(True), ' USDT 买入 ', order.get_amount(True), '个', params.symbol, ', 剩余: ', context.get("account_usdt_amount"), ' USDT')
    
    elif context.get('sellable') and ((context.get('max_price') and params.max_retrieval and change_rate(context.get('max_price'), close_price) < -params.max_retrieval) or boll_result['is_increase_over']):
        order = deps.exchange.create_order(params.symbol, 'market', 'sell', f'BOLL_PLAN_{params.symbol}', amount = context.get('account_coin_amount'))
        context.set('account_coin_amount', context.get('account_coin_amount') - order.get_amount(True))
        context.set('account_usdt_amount', context.get('account_usdt_amount') + order.get_cost(True))
        context.set('buyable', True)
        context.set('sellable', False)
        context.delete('max_price')
        deps.notification_logger.msg(f'{order.timestamp} 卖出 ', order.get_amount(True), ' ', params.symbol, ', 总共', order.get_cost(True), ' USDT 剩余: ', context.get("account_usdt_amount"), 'USDT')

def run(params: dict, notification: NotificationLogger):
    with Context(params = Params(**params), deps=BasicDependency(notification=notification)) as context:
        boll(context)


        