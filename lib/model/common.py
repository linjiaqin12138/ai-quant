import abc
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Literal, Optional

OrderType = Literal['market', 'limit']
OrderSide = Literal['buy', 'sell']

@dataclass(frozen=True)
class Ohlcv:

    def to_dict(self):
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

@dataclass(frozen=True)
class OhlcvHistory:
    symbol: str
    frame: str
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
    # 交易涉及的总金额
    _cost: float
    fees: List[OrderFee]

    @property
    def amount(self) -> float:
        """获取订单的原始（毛）数量。"""
        return self._amount

    @property
    def cost(self) -> float:
        """获取订单的原始（毛）成本/价值 (price * amount)，不包含手续费。"""
        return self._cost

    @abc.abstractmethod
    def get_net_amount(self) -> float:
        """
        获取净交易数量。
        对于费用以基础资产支付的情况（如某些加密货币交易），
        此数量会扣除相应费用。
        """
        pass

    @abc.abstractmethod
    def get_net_cost(self) -> float:
        """
        获取净成本/价值，计入所有以计价货币支付的费用。
        对于买单，返回值通常 >= cost。
        对于卖单，返回值通常 <= cost。
        """
        pass

    def get_total_fee_in_currency(self, currency: str) -> float:
        """计算指定货币的总费用。"""
        return sum(fee.cost for fee in self.fees if fee.currency == currency)