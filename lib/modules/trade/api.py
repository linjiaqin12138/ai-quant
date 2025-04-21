import abc
from datetime import datetime

from lib.model.common import OhlcvHistory, Order, OrderSide, OrderType

class TradeOperations(abc.ABC):
    """
    这里面的方法主要是一些交易所的操作，但和交易所的接口lib.adapter.exchange下有所不同，目的是
    1. 这里面的操作会比较复杂，涉及一些缓存逻辑等，函数参数也可以比较灵活一点
    2. 防止污染交易所的接口，合适的话可以考虑将一些方法放到交易所的接口中
    3. 可以放一些和交易所无关的操作，比如获取交易日历等
    """
    @abc.abstractmethod
    def is_business_day(self, day: datetime) -> bool:
        pass

    @abc.abstractmethod
    def get_current_price(self, symbol: str) -> float:
        pass

    @abc.abstractmethod
    def create_order(
        self, 
        symbol: str, 
        type: OrderType, 
        side: OrderSide,
        *,
        tags: str, 
        amount: float = None, 
        price: float = None, 
        spent: float = None, 
        comment: str = None
    ) -> Order:
        pass

    @abc.abstractmethod
    def get_ohlcv_history(
        self, 
        symbol: str, 
        frame: str,
        *,
        limit: int, 
        start: datetime, 
        end: datetime = datetime.now()
    ) -> OhlcvHistory:
        pass

__all__ = [
    'TradeOperations'
]
