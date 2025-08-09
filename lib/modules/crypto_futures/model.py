from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, Literal, Any
from lib.model.common import OrderSide


@dataclass
class PositionStatus:
    """仓位状态"""
    position_side: Literal["long", "short"]
    amount: float  # 绝对数量
    entry_price: float
    mark_price: float
    break_even_price: float
    liquidation_price: float
    leverage: int
    notional: float
    unrealized_pnl: float
    raw: Optional[Dict[str, Any]] = None


@dataclass
class FuturesOrder:
    """下单结果"""
    id: str
    symbol: str
    limit_order_price: Optional[float] # 限价单价格
    avg_price: Optional[float] # 成交价格
    side: OrderSide
    amount: float # 已成交数量，如果未成交则为原始委托数量
    cost: Optional[float] # 总成交金额
    timestamp: datetime # 更新时间
    type: Literal["LIMIT", "MARKET", "TAKE_PROFIT_MARKET", "STOP_MARKET"]
    status: Literal["NEW", "FILLED", "CANCELED", "EXPIRED", ""] = ""
    
    raw: Optional[Dict[str, Any]] = None

    @classmethod
    def from_raw(cls, raw: Dict[str, Any]) -> "FuturesOrder":
        """
        {
            "orderId": "29276685412",              # 订单ID
            "symbol": "SUIUSDT",                   # 交易对
            "status": "NEW",                       # 订单状态
            "clientOrderId": "x-xcKtGhcuf5ca5812c869e01544a85d", # 客户端订单ID
            "price": "4.330000",                   # 限价单价格
            "avgPrice": "0.00",                    # 平均成交价
            "origQty": "15.0",                     # 原始委托数量
            "executedQty": "0.0",                  # 已成交数量
            "cumQty": "0.0",                       # 累计成交数量
            "cumQuote": "0.0000000",               # 累计成交金额
            "timeInForce": "GTC",                  # 有效方式（如GTC为一直有效）
            "type": "LIMIT",                       # 订单类型（限价单）
            "reduceOnly": false,                   # 仅减仓标志
            "closePosition": false,                # 是否全部平仓
            "side": "SELL",                        # 买卖方向
            "positionSide": "BOTH",                # 仓位方向（BOTH/SHORT/LONG）
            "stopPrice": "0.000000",               # 止损价格
            "workingType": "CONTRACT_PRICE",       # 触发类型
            "priceProtect": false,                 # 是否价格保护
            "origType": "LIMIT",                   # 原始订单类型
            "priceMatch": "NONE",                  # 价格匹配模式
            "selfTradePreventionMode": "EXPIRE_MAKER", # 自成交防止模式
            "goodTillDate": "0",                   # 有效截止日期
            "updateTime": "1753680586540"          # 更新时间（时间戳）
        }
        """
        return FuturesOrder(
            id=raw["orderId"],
            symbol=raw["symbol"],
            limit_order_price=float(raw["stopPrice"]) if raw['type'] in ["STOP_MARKET", "TAKE_PROFIT_MARKET"] else float(raw["price"]), # 限价单价格
            avg_price=float(raw["avgPrice"]) if float(raw["avgPrice"]) != 0.0 else None, # 实际成交价格
            side=raw["side"].lower(),
            amount=float(raw["executedQty"]) if float(raw["executedQty"]) != 0.0 else float(raw["origQty"]),
            cost=float(raw["cumQuote"]) if float(raw["cumQuote"]) != 0.0 else None,
            timestamp=datetime.fromtimestamp(int(raw["updateTime"]) / 1000),
            type=raw["type"],
            status=raw["status"],
            raw=raw
        )

@dataclass
class StopOrderResult:
    """止盈止损设置结果"""
    take_profit_order_result: Optional[FuturesOrder] = None
    stop_loss_order_result: Optional[FuturesOrder] = None
    error: Optional[str] = None