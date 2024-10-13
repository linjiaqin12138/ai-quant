from dataclasses import dataclass
from typing import List, Optional, TypedDict
from datetime import datetime, timedelta

from lib.utils.number import change_rate, get_total_assets

from ..model import Ohlcv
from ..utils.time import timeframe_to_second
from ..utils.ohlcv import boll_info
from ..modules.notification_logger import NotificationLogger
from ..modules.strategy import CryptoDependency, ParamsBase, ResultBase, ContextBase

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

class Context(ContextBase[CryptoDependency]):

    def __init__(self, params: Params, deps: CryptoDependency):
        super().__init__(params, deps)

    def init_id(self, params: Params) -> str:
        return f'{super().init_id(params)}_BOLL'

    def init_context(self, params: Params) -> ContextDict:
        return {
            'account_usdt_amount': params.money,
            'account_coin_amount': 0,
            'buyable': True,
            'sellable': False
        }

def boll(context: Context, data: List[Ohlcv] = []) -> ResultBase:
    params: Params = context._params
    deps = context._deps
    
    expected_data_length = 21
    if len(data) == 0:
        data = deps.crypto.get_ohlcv_history(params.symbol, params.data_frame, 
           datetime.now() - (expected_data_length) * timedelta(seconds = timeframe_to_second(params.data_frame)),
           datetime.now()           
        ).data
    assert len(data) >= expected_data_length
    
    close_price = data[-1].close
    boll_result = boll_info(data)

    
    if context.get('sellable') and context.get('max_price') < close_price:
        context.set('max_price', close_price)

    if context.get('buyable') and boll_result['is_turn_good']:
        order = deps.crypto.create_order(params.symbol, 'market', 'buy', 'BOLL_PLAN', spent = context.get('account_usdt_amount'))
        context.set('account_coin_amount', context.get('account_coin_amount') + order.get_amount(True))
        context.set('account_usdt_amount', context.get('account_usdt_amount') - order.get_cost(True))
        context.set('buyable', False)
        context.set('sellable', True)
        context.set('max_price', close_price)
        deps.notification_logger.msg(f'{order.timestamp} 花费 ', order.get_cost(True), ' USDT 买入 ', order.get_amount(True), '个', params.symbol, ', 剩余: ', context.get("account_usdt_amount"), ' USDT')
    
    elif context.get('sellable') and ((context.get('max_price') and params.max_retrieval and change_rate(context.get('max_price'), close_price) < -params.max_retrieval) or boll_result['is_increase_over']):
        order = deps.crypto.create_order(params.symbol, 'market', 'sell', 'BOLL_PLAN', amount = context.get('account_coin_amount'))
        context.set('account_coin_amount', context.get('account_coin_amount') - order.get_amount(True))
        context.set('account_usdt_amount', context.get('account_usdt_amount') + order.get_cost(True))
        context.set('buyable', True)
        context.set('sellable', False)
        context.delete('max_price')
        deps.notification_logger.msg(f'{order.timestamp} 卖出 ', order.get_amount(True), ' ', params.symbol, ', 总共', order.get_cost(True), ' USDT 剩余: ', context.get("account_usdt_amount"), 'USDT')
        

    return ResultBase(
        total_assets = get_total_assets(close_price, context.get('account_coin_amount') , context.get('account_usdt_amount'))
    )

def run(params: dict, notification: NotificationLogger):
    with Context(params = Params(**params), deps=CryptoDependency(notification=notification)) as context:
        boll(context)


        