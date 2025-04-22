
from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional

from .common import OhlcvHistory, Order

CryptoHistoryFrame = Literal['1d', '1h', '15m']

@dataclass(frozen=True)
class CryptoOhlcvHistory(OhlcvHistory):
    exchange: Optional[str]

@dataclass(frozen=True)
class CryptoOrder(Order):
    context: Dict[str, Any]
    exchange: str

    _base_currency: str = field(init=False)
    _quote_currency: str = field(init=False)
    def __post_init__(self):
        parts = self.symbol.split('/')
        if len(parts) == 2:
            # 使用 object.__setattr__ 因为 frozen=True
            object.__setattr__(self, '_base_currency', parts[0])
            object.__setattr__(self, '_quote_currency', parts[1])
        else:
            # 处理无效 symbol 或不同格式
            raise ValueError(f"Invalid symbol format: {self.symbol}")

    def get_base_currency(self) -> str:
        return self._base_currency

    def get_quote_currency(self) -> str:
        return self._quote_currency

    def get_total_fee_in_currency(self, currency: str) -> float:
        """计算指定货币的总费用。"""
        return sum(fee.cost for fee in self.fees if fee.currency == currency)
    
    def get_net_amount(self) -> float:
        """
        获取净交易数量，扣除以基础货币支付的费用。
        """
        base_currency = self.get_base_currency()
        base_fee = self.get_total_fee_in_currency(base_currency)
        # 假设费用总是正数，净数量是原始数量减去费用
        return self.amount - base_fee

    def get_net_cost(self) -> float:
        """
        获取净成本/价值，计入所有以计价货币支付的费用。
        """
        quote_currency = self.get_quote_currency()
        quote_fee = self.get_total_fee_in_currency(quote_currency)

        if self.side == 'buy':
            # 买入时，净成本 = 原始成本 + 计价货币费用
            return self.cost + quote_fee
        else: # sell
            # 卖出时，净收入 = 原始价值 - 计价货币费用
            return self.cost - quote_fee