import ccxt
from datetime import datetime 
from lib.config import get_binance_config
from lib.model import CryptoOhlcvHistory, CryptoHistoryFrame, Ohlcv, CryptoOrderType, CryptoOrderSide, CryptoOrder
from lib.utils.time import dt_to_ts, timeframe_to_second
from .base import retry_patch, CryptoExchangeAbstract

def binance_test_patch(exchange: ccxt.binance) -> ccxt.binance:
    def call_with_test(func):
        def wrapper(*args, **kwargs):
            if kwargs['params']:
                kwargs['params']['test'] = True
            else:
                kwargs['params'] = { 'test': True }
            func(*args, **kwargs)
        return wrapper
    
    for method in dir(exchange):
        func = getattr(exchange, method)
        if callable(func):
            setattr(exchange, method, call_with_test(func))

class BinanceExchange(CryptoExchangeAbstract):

    def __init__(self, test_mode: bool = False):
        binance = ccxt.binance(get_binance_config())
        self.binance = retry_patch(binance)
        self.test_mode = test_mode


    def create_order(self, pair: str, type: CryptoOrderType, side: CryptoOrderSide, amount: float, price: float = None) -> CryptoOrder: 
        res = self.binance.create_order(pair, type, side, amount, price)
        return CryptoOrder(
            context = res.info,
            exchange = 'binance',
            id = res.id,
            timestamp = datetime.fromtimestamp(res.timestamp / 1000),
            pair = res.symbol,
            type = res.type,
            side = res.side,
            price = res.price,
            amount= res.amount,
            cost = res.cost
        )
    
    def fetch_ohlcv(self, pair: str, frame: CryptoHistoryFrame, start: datetime, end: datetime = datetime.now()) -> CryptoOhlcvHistory:
        start_in_ts = dt_to_ts(start)
        end_in_ts = dt_to_ts(end)
        interval_in_ms = timeframe_to_second(frame) * 1000
        total = int((end_in_ts - start_in_ts) / interval_in_ms)

        data = []
        while total > 0:
            limit = 500 if total > 500 else total
            data.extend(self.binance.fetch_ohlcv(pair, frame, since=start_in_ts, limit=limit))
            total -= 500
            start_in_ts += (500 * timeframe_to_second(frame) * 1000)
        return CryptoOhlcvHistory(
            pair = pair,
            frame = frame,
            exchange = 'binance',
            data = list(
                map(
                    lambda item: Ohlcv(
                        timestamp = datetime.fromtimestamp(item[0] / 1000), 
                        open = item[1], 
                        high = item[2], 
                        low = item[3], 
                        close = item[4], 
                        volume = item[5]
                    ), 
                    data
                )
            )
        )
        