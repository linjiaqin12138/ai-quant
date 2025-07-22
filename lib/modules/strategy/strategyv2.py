import abc
from datetime import datetime
import time
from typing import Literal, Optional, List

from lib.adapter.notification.api import NotificationAbstract
from lib.model.common import Ohlcv, Order
from lib.utils.time import time_ago_from, ts_to_dt
from lib.utils.string import random_id
from lib.adapter.notification import PushPlus
from lib.modules.notification_logger import NotificationLogger
from lib.modules.trade import TradeOperations, crypto, ashare
from .state import PersisitentState, StateApi


class FakeOrder(Order):
    def get_net_amount(self):
        return self._amount

    def get_net_cost(self):
        return self._cost


class StrategyBase(abc.ABC):
    # 基本默认值
    symbol: str = "BTC/USDT"
    investment: float = 100.0
    name: str = "Strategy"
    frame: str = "1d"
    # 这个参数在子类中修改
    _data_fetch_amount: int = 40
    # 用来判断是否运行在回测backtest还是实盘run，来选择性做一些事情
    _is_test_mode: bool = False

    # 实际运行时指定
    state: StateApi
    trade_ops: TradeOperations
    logger: NotificationLogger

    def buy(
        self, spent: float = None, amount: float = None, comment: str = None
    ) -> Order:
        if not spent and not amount:
            raise ValueError("Either 'spent' or 'amount' must be provided.")
        if spent and amount:
            raise ValueError(
                f"Invalid operation: spent={spent}, amount={amount}. Both should not be set simultaneously."
            )
        if spent > self.free_money:
            raise ValueError(
                f"Spent amount ({spent}) exceeds available free money ({self.free_money})."
            )

        self.logger.msg(f"Attempting to buy: spent={spent}, amount={amount}.")

        if not self._is_test_mode:
            order = self.trade_ops.create_order(
                self.symbol,
                "market",
                "buy",
                tags=self.name,
                amount=amount,
                spent=spent,
                comment=comment,
            )
            self.state.decrease("free_money", order.get_net_cost())
            self.state.increase("hold_amount", order.get_net_amount())
            return order
        else:
            self.state.set("bt_observed_action", "buy")
            increase_amount = spent / self.current_price if spent else amount
            decrease_money = spent if spent else amount * self.current_price
            self.state.decrease("free_money", decrease_money)
            self.state.increase("hold_amount", increase_amount)

            return FakeOrder(
                id=random_id(20),
                timestamp=self.current_time,
                symbol=self.symbol,
                type="market",
                side="buy",
                price=self.current_price,
                _amount=increase_amount,
                _cost=decrease_money,
                fees=[],
            )

    def sell(self, amount: float, comment: str = None) -> Order:
        self.logger.msg(f"Attempting to sell: amount={amount}.")
        if amount > self.hold_amount:
            raise ValueError(
                f"Attempted to sell {amount}, but only {self.hold_amount} is held."
            )

        if not self._is_test_mode:
            order = self.trade_ops.create_order(
                self.symbol,
                "market",
                "sell",
                tags=self.name,
                amount=amount,
                comment=comment,
            )
            self.state.increase("free_money", order.get_net_cost(True))
            self.state.decrease("hold_amount", order.get_net_amount(True))
            return order
        else:
            self.state.set("bt_observed_action", "sell")
            self.state.increase(
                "free_money", amount * self.state.get("bt_current_price")
            )
            self.state.decrease("hold_amount", amount)
            return FakeOrder(
                id=random_id(20),
                timestamp=self.current_time,
                symbol=self.symbol,
                type="market",
                side="sell",
                price=self.current_price,
                _amount=amount,
                _cost=amount * self.state.get("bt_current_price"),
                fees=[],
            )

    def _id(self) -> str:
        return '{{"name": {name}, "frame": {frame}, "symbol": {symbol}}}'.format(
            name=self.name, symbol=self.symbol, frame=self.frame
        )

    def _prepare(self):
        """
        Override this function to inject dependencys for run or back_test according to is_test_mode
        """
        return

    def _addtional_state_parameters(self):
        """
        Override this function if need to inject addtional initial state parameters
        """
        return {}

    @property
    def free_money(self) -> float:
        return self.state.get("free_money")

    @property
    def hold_amount(self) -> float:
        return self.state.get("hold_amount")

    @property
    def current_price(self) -> float:
        if self._is_test_mode:
            return self.state.get("bt_current_price")
        else:
            return self.trade_ops.get_current_price(self.symbol)

    @property
    def current_time(self) -> datetime:
        if self._is_test_mode:
            return ts_to_dt(self.state.get("bt_current_time"))
        else:
            return datetime.now()

    @abc.abstractmethod
    def _core(self, ohlcv_history: List[Ohlcv]):
        pass

    def _init_state(self):
        addtional_params = self._addtional_state_parameters()
        for key in addtional_params.keys():
            if key.startswith("bt_"):
                raise ValueError(
                    f"Invalid key '{key}' in additional_params: keys cannot start with 'bt_'."
                )
        init_state = addtional_params
        init_state.update(
            {
                "free_money": self.investment,
                "hold_amount": 0,
            }
        )
        return init_state

    def run(
        self,
        name: str = None,
        symbol: str = None,
        investment: float = None,
        frame: str = None,
        notification: NotificationAbstract = PushPlus(),
        **addtional_params,
    ):
        self._is_test_mode = False
        self.symbol = symbol or self.symbol
        self.investment = investment or self.investment
        self.name = name or self.name
        self.frame = frame or self.frame
        for param, val in addtional_params:
            setattr(self, param, val)

        self.trade_ops = crypto if self.symbol.endswith("USDT") else ashare
        self.logger = NotificationLogger(self.name, notification)
        try:
            if not self.trade_ops.is_business_day(self.current_time):
                return
            self.state = PersisitentState(self._id(), default=self._init_state())
            ohlcv_list = self.get_ohlcv_history(limit=self._data_fetch_amount)
            self._prepare()
            self._core(ohlcv_list)

            self.state.save()
        except Exception as e:
            import traceback

            self.logger.msg(traceback.format_exc())
        finally:
            self.logger.send()

    def _trace_back_business_day_from(
        self, count: int, from_time: datetime
    ) -> datetime:
        while count > 0:
            days_ahead = time_ago_from(1, self.frame, from_time)
            if self.trade_ops.is_business_day(days_ahead):
                count -= 1
            from_time = days_ahead
        return from_time

    def get_ohlcv_history(
        self,
        limit: int = None,
        start_time: datetime = None,
        end_time: datetime = datetime.now(),
    ) -> List[Ohlcv]:
        return self.trade_ops.get_ohlcv_history(
            self.symbol, self.frame, limit=limit, start=start_time, end=end_time
        ).data

    def back_test(
        self,
        start_time: datetime,
        end_time: datetime,
        symbol: str = None,
        investment: float = None,
        name: str = None,
        frame: str = None,
        recovery_file: Optional[str] = None,
        show_indicators: List[Literal["macd", "boll"]] = [],
        result_folder: Optional[str] = None,
        **addtional_params,
    ):
        from lib.modules.strategy.back_test import BackTest

        self.symbol = symbol or self.symbol
        self.investment = investment if investment is not None else self.investment
        self.frame = frame or self.frame
        back_test = BackTest(
            strategy=self,
            start_time=start_time,
            end_time=end_time,
            name=name,
            recovery_file=recovery_file,
            show_indicators=show_indicators,
            result_folder=result_folder,
            addtional_params=addtional_params,
        )
        back_test.run()


if __name__ == "__main__":

    class SimpleStategy(StrategyBase):
        _data_fetch_amount = 50

        def _core(self, ohlcv_history: List[Ohlcv]):
            if ohlcv_history[-1].close < ohlcv_history[0].close and self.free_money > 0:
                self.buy(spent=self.free_money)
            elif (
                ohlcv_history[-1].close > ohlcv_history[1].close
                and self.hold_amount > 0
            ):
                self.sell(self.hold_amount)
            time.sleep(0.1)

    s = SimpleStategy()
    s.back_test(
        name="策略测试",
        symbol="DOGE/USDT",
        start_time=datetime(2025, 2, 1, 8),
        end_time=datetime(2025, 2, 27, 8),
        investment=50000,
        show_indicators=["macd", "boll"],
    )
