from typing import List, Optional, Literal, Dict, Any
from dataclasses import dataclass
from datetime import datetime

CryptoHistoryFrame = Literal['1d', '1h', '15m']
CryptoOrderType = Literal['market', 'limit']
CryptoOrderSide = Literal['buy', 'sell']

@dataclass(frozen=True)
class Ohlcv:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
@dataclass(frozen=True)
class CryptoFee:
    currency: str
    cost: float
    rate: Optional[float]
@dataclass(frozen=True)
class OhlcvHistory:
    data: List[Ohlcv]

@dataclass(frozen=True)
class CryptoOhlcvHistory(OhlcvHistory):
    pair: str
    frame: CryptoHistoryFrame
    exchange: Optional[str]

@dataclass(frozen=True)
class CryptoOrder:
    context: Dict[str, Any]
    exchange: str
    # id: str
    id: str
    # datetime: Str
    timestamp: datetime
    # lastTradeTimestamp: Int
    # lastUpdateTimestamp: Int
    # status: Str
    pair: str
    type: CryptoOrderType
    # timeInForce: Str
    side: CryptoOrderSide
    price: float
    # average: Num
    _amount: float
    # filled: Num
    # remaining: Num
    # stopPrice: Num
    # takeProfitPrice: Num
    # stopLossPrice: Num
    _cost: float
    # trades: List[Trade]
    # reduceOnly: Bool
    # postOnly: Bool
    fees: Optional[List[CryptoFee]]

    def get_amount(self, excluding_fee: bool = False):
        currency = self.pair.split('/').pop(0)
        result = self._amount
        if excluding_fee:
            for fee in self.fees:
                if fee.currency == currency:
                    result -= fee.cost
        return result
    
    def get_cost(self, including_fee: bool = False):
        currency = self.pair.split('/').pop()
        result = self._cost
        if including_fee:
            for fee in self.fees:
                if fee.currency == currency:
                    result += fee.cost
        return result

class CryptoTradeInfo:
    pair: str
    timestamp: datetime
    action: Literal['buy', 'sell']
    reason: str
    amount: float
    price: float
    type: Literal['limit', 'market']
    context: dict
    order_id: str

@dataclass
class NewsInfo:
    news_id: str
    title: str
    description: Optional[str]
    timestamp: datetime
    url: str
    platform: str

    reason: Optional[str]
    mood: Optional[float]