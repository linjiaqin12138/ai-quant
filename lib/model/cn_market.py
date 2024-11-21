from typing import Literal
from dataclasses import dataclass
from .common import Order

CnStockHistoryFrame = Literal['1d', '1w', '1M']
@dataclass(frozen=True)
class AShareOrder(Order):
    def get_amount(self, excluding_fee: bool = False):
        return self._amount
    
    def get_cost(self, including_fee: bool = False):
        return self._cost