
from datetime import datetime
from lib.logger import logger
from lib.utils.string import random_id
from lib.model import CryptoHistoryFrame, CryptoOhlcvHistory, CryptoOrder, OrderSide, OrderType
from lib.modules.crypto import CryptoOperationAbstract


class FakeCryptoOperation(CryptoOperationAbstract):
    history = CryptoOhlcvHistory(symbol="BTC/USDT", frame='1d', exchange='binance', data=[])
    price = 100

    def set_price(self, price: float):
        self.price = price

    def set_history(self, history: CryptoOhlcvHistory):
        self.history = history
    
    def create_order(self, symbol: str, type: OrderType, side: OrderSide, reason: str, amount: float = None, price: float = None, spent: float = None, comment: str = None) -> CryptoOrder:
        logger.info(f"Create {type} order: {side} {amount or spent} {symbol} for {reason}:{comment}, price {price}")
        return CryptoOrder(
            context = {},
            exchange = 'binance',
            id =random_id(),
            timestamp = self.history.data[-1].timestamp,
            symbol = symbol,
            type = type,
            side = side,
            price = self.price,
            _amount = amount or spent / self.price,
            _cost = spent,
            fees =[]
        )

    def get_ohlcv_history(self, symbol: str, frame: CryptoHistoryFrame, start: datetime, end: datetime = datetime.now()) -> CryptoOhlcvHistory:
        return self.history


fake_crypto = FakeCryptoOperation()