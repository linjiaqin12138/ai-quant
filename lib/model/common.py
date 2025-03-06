import abc
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar

OrderType = Literal['market', 'limit']
OrderSide = Literal['buy', 'sell']

@dataclass(frozen=True)
class Ohlcv:

    def __dict__(self):
        # 使用dataclasses.asdict()获取字典表示
        data_dict = asdict(self)
        # 将timestamp字段从datetime对象转换为时间戳
        data_dict['timestamp'] = int(self.timestamp.timestamp() * 1000)
        return data_dict
    
    @classmethod
    def from_dict(cls, data_dict):
        """
        从包含时间戳（数字时间戳）的字典中初始化Ohlcv对象。
        
        :param data_dict: 包含时间戳的字典
        :return: Ohlcv对象
        """
        # 将数字时间戳转换回datetime对象
        timestamp_dt = datetime.fromtimestamp(data_dict['timestamp'] / 1000)
        # 创建Ohlcv对象
        return cls(
            timestamp=timestamp_dt,
            open=data_dict['open'],
            high=data_dict['high'],
            low=data_dict['low'],
            close=data_dict['close'],
            volume=data_dict['volume']
        )

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