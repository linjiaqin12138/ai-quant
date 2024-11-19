
from datetime import datetime
from typing import Literal, Optional, TypedDict
from lib.model.common import OhlcvHistory, Order, OrderFee
from lib.utils.string import random_id
from lib.model import CryptoHistoryFrame, CryptoOhlcvHistory, CryptoOrder, OrderSide, OrderType
from lib.modules.exchange_proxy import ExchangeOperationProxy

ActionSpied = TypedDict('ActionSpied', {
    'action': Literal['hold', 'buy', 'sell'],
    'amount': Optional[float],
    'cost': Optional[float],
})

class FakeExchange(ExchangeOperationProxy):
    curr_time: datetime
    curr_price: float
    curr_data: OhlcvHistory
    action_info: ActionSpied = {}

    def get_buy_cost(self) -> float:
        return self.action_info.get('cost')
    
    def get_sell_amount(self) -> float:
        return self.action_info.get('amount')

    @property
    def is_buy(self) -> bool:
        return self.action_info.get('action') == 'buy'
    @property
    def is_sell(self) -> bool:
        return self.action_info.get('action') == 'sell'

    def clear(self):
        self.action_info = {}
    
    def set_curr_data(self, data: OhlcvHistory):
        self.curr_data = data

    def set_curr_price(self, price: float):
        self.curr_price = price

    def set_curr_time(self, datetime: datetime):
        self.curr_time = datetime

    def create_order(self, symbol: str, type: OrderType, side: OrderSide, reason: str, amount: float = None, price: float = None, spent: float = None, comment: str = None) -> Order:
        if side == 'buy':
            self.action_info = {
                'action': 'buy',
                'cost': spent
            }
        elif side == 'sell':
            self.action_info = {
                'action': 'sell',
                'amount': amount
            }

        amount = amount if amount else spent / self.curr_price
        if symbol.endswith('USDT'):
            return CryptoOrder(
                context={},
                exchange='binance',
                id = random_id(10),
                timestamp = self.curr_time,
                symbol = symbol,
                type = type,
                side = side,
                _amount = amount,
                price = self.curr_price,
                _cost = self.curr_price * amount,
                fees = [OrderFee(symbol, 0.001 * amount, 0.001) if side == 'buy' else OrderFee(symbol, 0.01 * amount * self.curr_price, 0.001)]
            )
        
        raise NotImplementedError(f"{symbol} is not support")
    
    def get_ohlcv_history(self, symbol: str, frame: CryptoHistoryFrame, start: datetime, end: datetime) -> CryptoOhlcvHistory:
        return self.curr_data


fake_exchange = FakeExchange()