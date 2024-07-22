from datetime import datetime

from lib.model import CryptoOrder, CryptoFee
from lib.utils.string import random_id

def test_get_amount_cost_with_fee():
    order = CryptoOrder({}, 'binance', id=random_id(), timestamp=datetime(2020, 1, 1), pair = 'BTC/USDT', type='market', side='buy', price=20000, _amount = 0.01, _cost = 200, fees = [
        CryptoFee('BTC', 0.001, None),
        CryptoFee('USDT', 1, None)
    ])

    assert order.get_amount() == 0.01
    assert order.get_amount(True) == 0.01 - 0.001

    assert order.get_cost() == 200
    assert order.get_cost(True) == 200 + 1