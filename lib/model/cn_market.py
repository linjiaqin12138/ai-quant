from typing import Literal
from dataclasses import dataclass
from .common import Order

CnStockHistoryFrame = Literal["1d"]


@dataclass(frozen=True)
class AShareOrder(Order):
    def get_net_amount(self) -> float:
        """
        获取净交易数量。
        A股交易费用通常不以股票数量支付，所以净数量等于原始数量。
        """
        return self.amount  # 使用基类提供的属性

    def get_net_cost(self) -> float:
        """
        获取净成本/价值，计入所有以人民币支付的费用。
        """
        total_cny_fee = self.get_total_fee_in_currency("CNY")
        if self.side == "buy":
            # 买入时，净成本 = 原始成本 + 费用
            return self.cost + total_cny_fee
        else:  # sell
            # 卖出时，净收入 = 原始价值 - 费用
            return self.cost - total_cny_fee
