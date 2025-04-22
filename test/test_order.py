from datetime import datetime

from lib.model import CryptoOrder, OrderFee
from lib.utils.string import random_id

def test_get_amount_cost_with_fee():
    order = CryptoOrder(
        context={}, 
        exchange='binance', 
        id=random_id(), 
        timestamp=datetime(2020, 1, 1), 
        symbol = 'BTC/USDT', 
        type='market', 
        side='buy', 
        price=20000, 
        _amount = 0.01, 
        _cost = 200, 
        fees = [
            OrderFee('BTC', 0.001, None),
            OrderFee('USDT', 1, None)
        ]
    )

    assert order.amount == 0.01
    assert order.get_net_amount() == 0.01 - 0.001

    assert order.cost == 200
    assert order.get_net_cost() == 200 + 1