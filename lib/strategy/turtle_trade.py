from dataclasses import dataclass
from typing import Literal, Union
from pandas import DataFrame

from lib.dao.data_query import get_ohclv
from .template import trade_flow, Context, BuyStrategy, SellStrategy, HistoryLoader

trade_actions = [
    
]

@dataclass(frozen=True)
class BuyEvent:
    amount: Union[float]
    type: Literal['market', 'limit']
    price: Union[float]
    spend: Union[float]

@dataclass(frozen=True)
class SellEvent:
    amount: Union[float]
    type: Literal['market', 'limit']

class TurtleContext(Context):
    curr_price: float
    hold_money: float
    hold_coin: float
    max_window: int
    min_window: int
    history: DataFrame
    def __init__(self, pair: str, frame: str, limit: int):
        super().__init__(self)
        # self.set_history_loader(lambda :get_ohclv(pair, frame, limit))

    def post_operation():
        pass
        
class BuyStrategyImpl(BuyStrategy):
    ctx: TurtleContext
    def __init__(self, ctx: TurtleContext): 
        self.ctx = ctx
    
    def is_buy(self) -> bool:
        max_in_window = self.ctx.history['close'].iloc[-self.ctx.max_window:].max()
        if self.ctx.curr_price > max_in_window and self.ctx.hold_money > 0:
            return True
        return False
    
    def buy(self):
        trade_actions.append(BuyEvent(spend=self.ctx.hold_money, type='market'))

class SellStrategyImpl(SellStrategy):
    ctx: TurtleContext
    def __init__(self, ctx: TurtleContext): 
        self.ctx = ctx

    def is_sell(self) -> bool:
        min_in_window = self.ctx.history['close'].iloc[-self.ctx.min_window:].min()
        if self.ctx.curr_price < min_in_window and self.ctx.hold_coin > 0:
            return True
        return False
    
    def sell(self):
        trade_actions.append(SellEvent(amount=self.ctx.hold_coin, type='market'))
