import abc
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar

OrderType = Literal['market', 'limit']
OrderSide = Literal['buy', 'sell']

@dataclass(frozen=True)
class Ohlcv:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

F = TypeVar('f', bound=str)
@dataclass(frozen=True)
class OhlcvHistory(Generic[F]):
    symbol: str
    frame: F
    data: List[Ohlcv]

@dataclass
class TradeTicker:
    last: float # 最新价格

@dataclass(frozen=True)
class OrderFee:
    currency: str
    cost: float
    rate: Optional[float]

@dataclass(frozen=True)
class Order(abc.ABC):
    id: str
    timestamp: datetime
    symbol: str
    type: OrderType
    side: OrderSide
    price: float
    _amount: float
    _cost: float
    fees: List[OrderFee]

    @abc.abstractmethod
    def get_amount(self, excluding_fee: bool = False):
        pass

    @abc.abstractmethod
    def get_cost(self, including_fee: bool = False):
        pass