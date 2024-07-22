from typing import List, TypedDict
from datetime import datetime, timedelta

from lib.utils.number import get_total_assets

from ..model import Ohlcv
from ..utils.time import timeframe_to_second
from ..utils.ohlcv import macd_info, sar_info
from ..modules.notification_logger import NotificationLogger
from ..modules.strategy import Dependency, ParamsBase, ResultBase, ContextBase

ContextDict = TypedDict('Context', {
    'account_usdt_amount': float,
    'account_coin_amount': float,
    'buyable': bool,
    'sellable': bool
})


class Context(ContextBase):

    def __init__(self, params: ParamsBase, deps: Dependency):
        super().__init__(params, deps)

    def init_id(self, params: ParamsBase) -> str:
        return f'{super().init_id(params)}_MACD_SAR'
    
    def init_context(self, params: ParamsBase) -> ContextDict:
        return {
            'account_usdt_amount': params.money,
            'account_coin_amount': 0,
            'buyable': True,
            'sellable': False
        }

def macd_sar(context: Context, data: List[Ohlcv] = []) -> ResultBase:
    params = context._params
    deps = context._deps
    
    expected_data_length = 35
    if len(data) == 0:
        data = deps.crypto.get_ohlcv_history(params.symbol, params.data_frame, 
           datetime.now() - (expected_data_length) * timedelta(seconds = timeframe_to_second(params.data_frame)),
           datetime.now()           
        ).data
    assert len(data) >= expected_data_length
    # 为了防止单元测试中datetime.now()返回当前时间，所以实际通过这种方式来作为当前时间，效果差不多
    # curr_time = data[-1].timestamp + timedelta(seconds=timeframe_to_second(params.data_frame))s
    close_price = data[-1].close
    macd_result = macd_info(data)
    # print(macd_result)
    sar_result = sar_info(data)
    # print(sar_result)
    if context.get('buyable') and macd_result['is_gold_cross']:
        order = deps.crypto.create_order(params.symbol, 'market', 'buy', 'TURTLE_PLAN', spent = context.get('account_usdt_amount'))
        context.set('account_coin_amount', context.get('account_coin_amount') + order.get_amount(True))
        context.set('account_usdt_amount', context.get('account_usdt_amount') - order.get_cost(True))
        context.set('buyable', False)
        context.set('sellable', True)
        deps.notification_logger.msg(f'{order.timestamp} 花费 ', order.get_cost(True), ' USDT 买入 ', order.get_amount(True), '个', params.symbol, ', 剩余: ', context.get("account_usdt_amount"), ' USDT')
    
    elif context.get('sellable') and sar_result['is_turn_up']:
        order = deps.crypto.create_order(params.symbol, 'market', 'sell', 'TURTLE_PLAN', amount = context.get('account_coin_amount'))
        context.set('account_coin_amount', context.get('account_coin_amount') - order.get_amount(True))
        context.set('account_usdt_amount', context.get('account_usdt_amount') + order.get_cost(True))
        context.set('buyable', True)
        context.set('sellable', False)
        deps.notification_logger.msg(f'{order.timestamp} 卖出 ', order.get_amount(True), ' ', params.symbol, ', 总共', order.get_cost(True), ' USDT 剩余: ', context.get("account_usdt_amount"), 'USDT')
        

    return ResultBase(
        total_assets = get_total_assets(close_price, context.get('account_coin_amount') , context.get('account_usdt_amount'))
    )

def run(params: dict, notification: NotificationLogger):
    with Context(params = ParamsBase(**params), deps=Dependency(notification=notification)) as context:
        macd_sar(context)


        