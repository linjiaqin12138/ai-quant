from typing import TypedDict
from ..utils.ohlcv import macd_info, sar_info
from ..modules.notification_logger import NotificationLogger
from ..modules.strategy import ParamsBase, BasicContext
from ..strategys.common import get_recent_data_with_at_least_count, WithExchangeProxy

ContextDict = TypedDict('Context', {
    'account_usdt_amount': float,
    'account_coin_amount': float,
    'buyable': bool,
    'sellable': bool
})

class Context(BasicContext[ContextDict]):
    deps: WithExchangeProxy
    def __init__(self, params: ParamsBase, deps: WithExchangeProxy):
        super().__init__(f'{params.symbol}_{params.data_frame}_{params.money}_MACD_SAR', deps)
        self.params = params

    def _initial_context(self) -> ContextDict:
        return {
            'account_usdt_amount': self.params.money,
            'account_coin_amount': 0,
            'buyable': True,
            'sellable': False
        }

def macd_sar(context: Context):
    params = context.params
    deps = context.deps
    
    data = get_recent_data_with_at_least_count(35, params.symbol, params.data_frame, deps.exchange)
    # 为了防止单元测试中datetime.now()返回当前时间，所以实际通过这种方式来作为当前时间，效果差不多
    # curr_time = data[-1].timestamp + timedelta(seconds=timeframe_to_second(params.data_frame))s
    close_price = data[-1].close
    macd_result = macd_info(data)
    # print(macd_result)
    sar_result = sar_info(data)
    # print(sar_result)
    if context.get('buyable') and macd_result['is_gold_cross']:
        order = deps.exchange.create_order(params.symbol, 'market', 'buy', f'MACD_SAR_{params.symbol}', spent = context.get('account_usdt_amount'))
        context.set('account_coin_amount', context.get('account_coin_amount') + order.get_amount(True))
        context.set('account_usdt_amount', context.get('account_usdt_amount') - order.get_cost(True))
        context.set('buyable', False)
        context.set('sellable', True)
        deps.notification_logger.msg(f'{order.timestamp} 花费 ', order.get_cost(True), ' USDT 买入 ', order.get_amount(True), '个', params.symbol, ', 剩余: ', context.get("account_usdt_amount"), ' USDT')
    
    elif context.get('sellable') and sar_result['is_turn_up']:
        order = deps.exchange.create_order(params.symbol, 'market', 'sell', f'MACD_SAR_{params.symbol}', amount = context.get('account_coin_amount'))
        context.set('account_coin_amount', context.get('account_coin_amount') - order.get_amount(True))
        context.set('account_usdt_amount', context.get('account_usdt_amount') + order.get_cost(True))
        context.set('buyable', True)
        context.set('sellable', False)
        deps.notification_logger.msg(f'{order.timestamp} 卖出 ', order.get_amount(True), ' ', params.symbol, ', 总共', order.get_cost(True), ' USDT 剩余: ', context.get("account_usdt_amount"), 'USDT')

def run(params: dict, notification: NotificationLogger):
    with Context(params = ParamsBase(**params), deps=WithExchangeProxy(notification=notification)) as context:
        macd_sar(context)


        