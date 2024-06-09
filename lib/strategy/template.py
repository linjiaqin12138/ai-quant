from dataclasses import dataclass
import abc
from typing import Callable
from pandas import DataFrame

HistoryLoader = Callable[[], DataFrame]

class BuyStrategy(abc.ABC):
    def __init__(self):
        pass
    def is_buy() -> bool:
        pass
    def buy():
        pass

class SellStrategy(abc.ABC):
    def __init__(self):
        pass
    def is_sell() -> bool:
        pass
    def sell():
        pass

class Context(abc.ABC):
    history_loader: HistoryLoader
    buy_strategy: BuyStrategy
    sell_strategy: SellStrategy

    def load_history(self)-> None:
        self.history_loader()
    @abc.abstractclassmethod
    def post_operation(self) -> None:
        pass

    def set_history_loader(self, history_loader: HistoryLoader) -> None:
        self.history_loader = history_loader
        
    def set_buy_strategy(self, buy_strategy: BuyStrategy) -> None: 
        self.buy_strategy = buy_strategy
        
    def set_sell_strategy(self, sell_strategy: SellStrategy) -> None:
        self.sell_strategy = sell_strategy

def trade_flow(
    context: Context
):
    context.load_history()
    if context.buy_strategy.is_buy():
        context.buy_strategy.buy()
    if context.sell_strategy.is_sell():
        context.sell_strategy.sell()
    context.post_operation()