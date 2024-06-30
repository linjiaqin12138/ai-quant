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
    amount: float
    # filled: Num
    # remaining: Num
    # stopPrice: Num
    # takeProfitPrice: Num
    # stopLossPrice: Num
    cost: float
    # trades: List[Trade]
    # reduceOnly: Bool
    # postOnly: Bool
    # fee: Fee

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