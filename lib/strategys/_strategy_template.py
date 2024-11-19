from dataclasses import dataclass
from typing import TypedDict

from ..adapter.database.session import SessionAbstract
from ..modules.exchange_proxy import ExchangeOperationProxy
from ..modules.notification_logger import NotificationLogger
from ..modules.strategy import BasicDependency, ParamsBase, BasicContext
from .common import get_recent_data_with_at_least_count

ContextDict = TypedDict('Context', {
    'account_money_amount': float,
    'account_symbol_amount': float
})

@dataclass
class Params(ParamsBase):
    pass

class Dependency(BasicDependency):
    def __init__(self, notification: NotificationLogger, exchange: ExchangeOperationProxy = None, session: SessionAbstract = None):
        super().__init__(notification = notification, exchange=exchange, session=session)

class Context(BasicContext[ContextDict]):
    def __init__(self, params: Params, deps: Dependency):
        super().__init__(f'{params.symbol}_{params.money}_{params.data_frame}_<Strategy-Name>', deps)
        self.params = params

    def _initial_context(self) -> ContextDict:
        return {
            'account_money_amount': self.params.money,
            'account_symbol_amount': 0
        }
    
    def buy(self, cost: float):
        order = self.deps.exchange.create_order(self.params.symbol, 'market', 'buy', '<Strategy Slogan>', spent=cost, comment='')
        self.increate('account_symbol_amount', order.get_amount(True))
        self.decreate('account_money_amount', order.get_cost(True))
        self.deps.notification_logger.msg(f'{order.timestamp} 花费', order.get_cost(True), '买入', order.get_amount(True), '份')
        return

    def sell(self, amount: float):
        order = self.deps.exchange.create_order(self.params.symbol, 'market', 'buy', '<Strategy Slogan>', amount=amount, comment='')
        self.increate('account_money_amount', order.get_cost(True))
        self.decreate('account_symbol_amount', order.get_amount(True))
        self.deps.notification_logger.msg(f'{order.timestamp} 卖出', order.get_amount(True), '份并获得', order.get_cost(True))


def strategy(context: Context):
    params: Params = context.params
    deps = context.deps

    data = get_recent_data_with_at_least_count(32, params.symbol, params.data_frame, deps.exchange)
   
    # 分析决策
    result = {  }

    # 判断是否买入卖出
    if result.get('xx'):
        context.buy(100)

    if result.get('xx'):
        context.sell(100)


def run(params: dict, notification: NotificationLogger):
    with Context(params = Params(**params), deps=Dependency(notification=notification)) as context:
        strategy(context)


        