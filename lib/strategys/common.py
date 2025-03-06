
from datetime import datetime, timedelta
from typing import List

from ..utils.time import timeframe_to_second
from ..model import Ohlcv
from ..modules.exchange_proxy import ExchangeOperationProxy, crypto
from ..modules.strategy import BasicDependency

def get_recent_data_with_at_least_count(count: int, symbol: str, frame: str, exchange: ExchangeOperationProxy) -> List[Ohlcv]:
    history = exchange.get_ohlcv_history(
        symbol, 
        frame,
        datetime.now() - (count * timedelta(seconds = timeframe_to_second(frame))),
        datetime.now()
    )
    # assert len(history.data) >= count
    return history.data

class WithExchangeProxy(BasicDependency):
    def __init__(self, exchange: ExchangeOperationProxy):
        self.exchange = exchange or crypto