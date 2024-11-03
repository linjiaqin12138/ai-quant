
from datetime import datetime
from lib.logger import logger
from lib.utils.string import random_id
from lib.model import CryptoHistoryFrame, CryptoOhlcvHistory, CryptoOrder, CryptoOrderSide, CryptoOrderType
from lib.modules.crypto import CryptoOperationAbstract


class FakeCryptoOperation(CryptoOperationAbstract):
    history = CryptoOhlcvHistory(pair="BTC/USDT", frame='1d', exchange='binance', data=[])
    price = 100

    def set_price(self, price: float):
        self.price = price

    def set_history(self, history: CryptoOhlcvHistory):
        self.history = history
    
    def create_order(self, pair: str, type: CryptoOrderType, side: CryptoOrderSide, reason: str, amount: float = None, price: float = None, spent: float = None, comment: str = None) -> CryptoOrder:
        logger.info(f"Create {type} order: {side} {amount or spent} {pair} for {reason}:{comment}, price {price}")
        return CryptoOrder(
            context = {},
            exchange = 'binance',
            id =random_id(),
            timestamp = datetime.now(),
            pair = pair,
            type = type,
            side = side,
            price = self.price,
            _amount = amount or spent / self.price,
            _cost = spent,
            fees =[]
        )

    def get_ohlcv_history(self, pair: str, frame: CryptoHistoryFrame, start: datetime, end: datetime = datetime.now()) -> CryptoOhlcvHistory:
        return self.history


fake_crypto = FakeCryptoOperation()