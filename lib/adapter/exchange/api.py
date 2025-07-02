from abc import ABC, abstractmethod
from datetime import datetime

from lib.model.common import OhlcvHistory, Order, OrderSide, OrderType, TradeTicker


class ExchangeAPI(ABC):
    """交易所API抽象基类"""

    @abstractmethod
    def fetch_ticker(self, symbol: str) -> TradeTicker:
        raise NotImplementedError

    @abstractmethod
    def fetch_ohlcv(
        self, symbol: str, frame: str, start: datetime, end: datetime = datetime.now()
    ) -> OhlcvHistory:
        raise NotImplementedError

    @abstractmethod
    def create_order(
        self,
        symbol: str,
        type: OrderType,
        side: OrderSide,
        amount: float,
        price: float = None,
    ) -> Order:
        raise NotImplementedError

    # @abstractmethod
    # def cancel_order(self, order_id: str) -> bool:
    #     """撤单"""
    #     pass

    # @abstractmethod
    # def get_order_status(self, order_id: str) -> OrderResponse:
    #     """查询订单状态"""
    #     pass

    # @abstractmethod
    # def get_account_balance(self) -> Dict[str, float]:
    #     """查询账户余额"""
    #     pass
