import json
from typing import Optional, Literal
from dataclasses import dataclass
from ccxt.base.types import Order as CcxtOrder
from lib.adapter.exchange.crypto_exchange import BinanceExchange
from lib.logger import logger
from .model import *

@dataclass
class LeverageResult:
    """设置杠杆返回结果"""
    symbol: str
    leverage: int

class BinanceFuturesOperator:
    """
    币安合约操作封装。只负责调用交易所接口，不管理任何本地状态。
    """

    def __init__(self, symbol: str):
        """
        symbol 例如: 'SUIUSDT'
        """
        self.symbol = symbol
        self._ex = BinanceExchange(future_mode=True)  # ccxt binance 实例封装在内部

    # -------------------- 基础信息 --------------------

    def get_latest_price(self) -> float:
        return self._ex.binance.fetch_ticker(self.symbol)['last']
    
    def set_leverage(self, leverage: int) -> LeverageResult:
        """
        设置杠杆倍数
        """
        result = self._ex.binance.fapiPrivatePostLeverage({
            "symbol": self.symbol,
            "leverage": leverage
        })
        return LeverageResult(
            symbol=result.get("symbol", self.symbol),
            leverage=int(result.get("leverage", leverage))
        )

    def get_position_status(self) -> PositionStatus:
        """
        获取当前仓位状态（BOTH）
        """
        rsp = self._ex.binance.fapiPrivateV2GetPositionRisk(params={"symbol": self.symbol})
        item = next((x for x in rsp if x.get("positionSide", "").upper() == "BOTH"), None)

        assert item != None, "仓位信息错误"

        amt = float(item.get("positionAmt", "0") or 0)
        side = "long" if amt > 0 else "short" if amt < 0 else "none"
        return PositionStatus(
            position_side=side,
            amount=abs(amt),
            entry_price=float(item.get("entryPrice", "0") or 0),
            mark_price=float(item.get("markPrice", "0") or 0),
            break_even_price=float(item.get("breakEvenPrice", "0") or 0),
            liquidation_price=float(item.get("liquidationPrice", "0") or 0),
            leverage=int(item.get("leverage", "0") or 0),
            notional=float(item.get("notional", "0") or 0),
            unrealized_pnl=float(item.get("unRealizedProfit", "0") or 0),
            raw=item
        )

    def get_order(self, order_id: str) -> FuturesOrder:
        raw_order = self._ex.binance.fetch_order(**{ 'symbol': self.symbol, 'id': order_id })
        logger.debug(f"获取订单信息: {json.dumps(raw_order, indent=2)}")
        return self._transform_order_result(raw_order)

    # -------------------- 下单操作 --------------------

    def _transform_order_result(self, raw_order: CcxtOrder) -> FuturesOrder:
        """
        将原始订单数据转换为 OrderResult 对象
        """
        return FuturesOrder.from_raw(raw_order["info"])

    def create_order(
        self,
        order_type: Literal["market", "limit"],
        side: Literal["buy", "sell"],
        amount: float,
        price: Optional[float] = None
    ) -> FuturesOrder:
        """
        创建订单
        """
        if order_type == "limit":
            assert price is not None, "限价单需要提供 price"

        order = self._ex.binance.create_order(
            symbol=self.symbol,
            type=order_type,
            side=side,
            amount=amount,
            price=price
        )

        return self._transform_order_result(order)

    def cancel_order(self, order_id) -> FuturesOrder:
        """
        取消订单
        """
        order = self._ex.binance.cancel_order(symbol=self.symbol, id=order_id)
        return self._transform_order_result(order)

    def set_position_stop_price(
        self,
        position_status: Optional[PositionStatus] = None,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None
    ) -> StopOrderResult:
        """
        设置止盈/止损（使用 closePosition=True 一键平仓方式）
        - 对多仓：止盈/止损使用 SELL
        - 对空仓：止盈/止损使用 BUY
        """
        pos = position_status or self.get_position_status()
        if not pos:
            return StopOrderResult(error="当前无持仓，无法设置止盈止损")

        close_side = "sell" if pos.position_side == "long" else "buy"
        result = StopOrderResult()

        # 止盈
        if take_profit is not None:
            raw_order = self._ex.binance.create_order(
                symbol=self.symbol,
                type="TAKE_PROFIT_MARKET",
                side=close_side,
                amount=pos.amount,
                params={
                    "closePosition": True,
                    "stopPrice": take_profit
                }
            )

            result.take_profit_order_result = self._transform_order_result(raw_order)

        # 止损
        if stop_loss is not None:
            sl_order = self._ex.binance.create_order(
                symbol=self.symbol,
                type="STOP_MARKET",
                side=close_side,
                amount=pos.amount,
                params={
                    "closePosition": True,
                    "stopPrice": stop_loss
                }
            )
            result.stop_loss_order_result = self._transform_order_result(sl_order)

        if result.take_profit_order_result is None and result.stop_loss_order_result is None:
            result.error = "止盈止损价格不能都为空"

        return result