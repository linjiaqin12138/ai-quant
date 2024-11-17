
from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

from .common import OhlcvHistory, Order

CryptoHistoryFrame = Literal['1d', '1h', '15m']

@dataclass(frozen=True)
class CryptoOhlcvHistory(OhlcvHistory[CryptoHistoryFrame]):
    exchange: Optional[str]

@dataclass(frozen=True)
class CryptoOrder(Order):
    context: Dict[str, Any]
    exchange: str

    def get_amount(self, excluding_fee: bool = False):
        currency = self.symbol.split('/').pop(0)
        result = self._amount
        if excluding_fee:
            for fee in self.fees:
                if fee.currency == currency:
                    result -= fee.cost
        return result
    
    def get_cost(self, including_fee: bool = False):
        currency = self.symbol.split('/').pop()
        result = self._cost
        if including_fee:
            for fee in self.fees:
                if fee.currency == currency:
                    result += fee.cost
        return result