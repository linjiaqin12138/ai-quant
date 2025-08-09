from textwrap import indent
import threading
import time
from typing import Callable, List

import json
from lib.logger import logger
from .binance_futures_operations import BinanceFuturesOperator
from lib.modules.strategy.state import  PersisitentState
from .model import *

# State Keys
FREE_BALANCE_KEY = "free_balance"
POSITION_AVG_PRICE_KEY = "position_avg_price"
LIMIT_ORDER_SUSPENDED_BALANCE_KEY = "limit_order_suspended_balance"
LEVERAGE_KEY = "leverage"
POSITION_AMOUNT_KEY = "position_amount"
POSITION_SIDE_KEY = "position_side"
OPERATION_HISTORYS = "operation_historys"  # 历史操作记录

ERROR_KEY = "error"

# Recent Order Keys - 记录最近的订单信息
RECENT_OPEN_POSITION_LIMIT_ORDER_KEY = "recent_open_position_limit_order"
RECENT_ADD_POSITION_LIMIT_ORDER_KEY = "recent_add_position_limit_order"
RECENT_DECREASE_POSITION_LIMIT_ORDER_KEY = "recent_decrease_position_limit_order"
RECENT_TAKE_PROFIT_LIMIT_ORDER_KEY = "recent_take_profit_limit_order"
RECENT_STOP_LOSS_LIMIT_ORDER_KEY = "recent_stop_loss_limit_order"

# Enums
POSITION_SIDE_LONG = "long"
POSITION_SIDE_SHORT = "short"
POSITION_SIDE_NONE = "none"
ORDER_SIDE_BUY = "buy"
ORDER_SIDE_SELL = "sell"
ORDER_STATUS_FILLED = "FILLED"
ORDER_STATUS_NEW = "NEW"
ORDER_STATUS_CANCELED = "CANCELED"
ORDER_STATUS_EXPIRED = "EXPIRED"

# Event Names
OPEN_POSITION = "open_position"
ADD_POSITION = "add_position"
DECREASE_POSITION = "decrease_position"
CLOSE_POSITION = "close_position"
TAKE_PROFIT = "take_profit"
STOP_LOSS = "stop_loss"
LIMIT_ORDER_CANCELED = "order_canceled"
LIMIT_ORDER_FILLED = "order_filled"

ALL_EVENTS = [
    OPEN_POSITION,
    ADD_POSITION,
    DECREASE_POSITION,
    CLOSE_POSITION,
    TAKE_PROFIT,
    STOP_LOSS,
    LIMIT_ORDER_CANCELED,
    LIMIT_ORDER_FILLED,
]

def cal_avg_price(price1: float, amount1: float, price2: float, amount2: float) -> float:
    """
    计算两个价格和数量的加权平均价格
    """
    return (price1 * amount1 + price2 * amount2) / (amount1 + amount2) if (amount1 + amount2) != 0 else 0

class FuturesPositionStateManager:
    def __init__(
            self,
            position_id: str,
            futures_opeator: BinanceFuturesOperator,
            initial_balance: float = 100,
        ):
        self.position_id = position_id
        self.initial_balance = initial_balance
        self.futures_operator = futures_opeator
        # self.order_event_queue = order_event_queue
        # self.state_update_lock = threading.Lock()
        self.state = PersisitentState(
            self.position_id, 
            default={
                FREE_BALANCE_KEY: self.initial_balance, # 可用余额
                POSITION_AVG_PRICE_KEY: 0, # 开仓均价
                LIMIT_ORDER_SUSPENDED_BALANCE_KEY: 0, # 限价单开仓/加仓的挂单冻结
                LEVERAGE_KEY: 5, # 杠杆倍数
                POSITION_AMOUNT_KEY: 0, # 仓位数量
                POSITION_SIDE_KEY: POSITION_SIDE_NONE, # 当前仓位方向
                ERROR_KEY: False,
                # Recent orders
                RECENT_OPEN_POSITION_LIMIT_ORDER_KEY: None,
                RECENT_ADD_POSITION_LIMIT_ORDER_KEY: {},
                RECENT_DECREASE_POSITION_LIMIT_ORDER_KEY: {},
                RECENT_TAKE_PROFIT_LIMIT_ORDER_KEY: None,
                RECENT_STOP_LOSS_LIMIT_ORDER_KEY: None,
                OPERATION_HISTORYS: []
            }
        )
        logger.debug("当前状态 : %s", json.dumps(self.state._simple_state._context, indent=2))
        self._handle_state_change_for_pending_orders()
        self._refresh_position(self.futures_operator.get_position_status())

        self._order_listening_thread: threading.Thread = None
        self._order_listening_callbacks: List[Callable[[FuturesOrder], None]] = []
        self._order_listening_thread_callback_write_lock: threading.Lock = threading.Lock()
        self._order_listening_thread_stop_event: threading.Event = threading.Event()

    @property
    def unrealized_pnl(self) -> float:
        return self._latest_position_status.unrealized_pnl
    
    @property
    def liquidation_price(self) -> float:
        return self._latest_position_status.liquidation_price
    
    @property
    def break_even_price(self) -> float:
        return self._latest_position_status.break_even_price

    @property
    def mark_price(self) -> float:
        return self._latest_position_status.mark_price

    @property
    def position_value(self) -> float:
        return self.position_amount * self.position_avg_price

    @property
    def position_level(self) -> float:
        return self.position_value / (self.position_value + self.free_balance * self.leverage)

    @property
    def leverage(self) -> float:
        return self.state.get(LEVERAGE_KEY)
    
    @property
    def free_balance(self) -> float:
        return self.state.get(FREE_BALANCE_KEY)
    
    @property
    def position_amount(self) -> float:
        return self.state.get(POSITION_AMOUNT_KEY)
    
    @property
    def position_side(self) -> str:
        return self.state.get(POSITION_SIDE_KEY)
    
    @property
    def position_avg_price(self) -> float:
        return self.state.get(POSITION_AVG_PRICE_KEY)
    
    @property
    def limit_order_suspended_balance(self) -> float:
        return self.state.get(LIMIT_ORDER_SUSPENDED_BALANCE_KEY)

    @property
    def pending_open_position_order(self) -> Optional[FuturesOrder]:
        if self.state.has(RECENT_OPEN_POSITION_LIMIT_ORDER_KEY):
            return FuturesOrder.from_raw(self.state.get(RECENT_OPEN_POSITION_LIMIT_ORDER_KEY))
        return None
    
    @property
    def pending_add_position_orders(self) -> List[FuturesOrder]:
        return [FuturesOrder.from_raw(order) for order in self._get_sorted_orders(RECENT_ADD_POSITION_LIMIT_ORDER_KEY)]

    @property
    def pending_decrease_position_orders(self) -> List[FuturesOrder]:
        return [FuturesOrder.from_raw(order) for order in self._get_sorted_orders(RECENT_DECREASE_POSITION_LIMIT_ORDER_KEY)]

    @property
    def pending_take_profit_order(self) -> Optional[FuturesOrder]:
        if self.state.has(RECENT_TAKE_PROFIT_LIMIT_ORDER_KEY):
            return FuturesOrder.from_raw(self.state.get(RECENT_TAKE_PROFIT_LIMIT_ORDER_KEY))
        return None

    @property
    def pending_stop_loss_order(self) -> Optional[FuturesOrder]:
        if self.state.has(RECENT_STOP_LOSS_LIMIT_ORDER_KEY):
            return FuturesOrder.from_raw(self.state.get(RECENT_STOP_LOSS_LIMIT_ORDER_KEY))
        return None

    @property
    def position_history(self) -> List[dict]:
        return self.state.get(OPERATION_HISTORYS)

    @property
    def all_pending_orders(self) -> List[FuturesOrder]:
        result = []
        if self.pending_open_position_order:
            result.append(self.pending_open_position_order)
        result.extend(self.pending_add_position_orders)
        result.extend(self.pending_decrease_position_orders)
        if self.pending_take_profit_order:
            result.append(self.pending_take_profit_order)
        if self.pending_stop_loss_order:
            result.append(self.pending_stop_loss_order)
        return result

    @property
    def is_error(self) -> bool:
        return self.state.get(ERROR_KEY)

    def _add_operation_history(self,time: datetime, text: str):
        self.state.append(
            OPERATION_HISTORYS, 
            { 
                "time": str(time),
                # "event": event,
                "description": text,
                # "snapshot": {
                #     FREE_BALANCE_KEY: self.free_balance,
                #     POSITION_AVG_PRICE_KEY: self.position_avg_price,
                #     LIMIT_ORDER_SUSPENDED_BALANCE_KEY: self.limit_order_suspended_balance,
                #     LEVERAGE_KEY: self.leverage,
                #     POSITION_AMOUNT_KEY: self.position_amount,
                #     POSITION_SIDE_KEY: self.position_side
                # }
            }
        )
        
    def _get_sorted_orders(self, key: str) -> List[dict]:
        """
        获取按更新时间排序的订单列表
        """
        orders = []
        
        for order_id in self.state.get(key):
            order = self.state.get([key, order_id])
            if order:
                orders.append(order)

        return sorted(orders, key=lambda o: float(o.get("updateTime", 0)))

    def _handle_state_change_for_pending_orders(self) -> List[FuturesOrder]:
        finished_orders = []
        
        for order in self.all_pending_orders:
            # 处理止盈止损的时候会导致另一个事件被取消并从pending_orders中删除，需要重新确认
            if order not in self.all_pending_orders:
                continue
            updated_order = self.futures_operator.get_order(order.id)
            if updated_order.status == ORDER_STATUS_FILLED:
                logger.info(f"订单 {order.id} 已完成")
                self._handle_order_filled(updated_order)
                finished_orders.append(updated_order)
            if updated_order.status == ORDER_STATUS_CANCELED:
                logger.info(f"订单 {order.id} 已取消")
                self._handle_order_canceled(updated_order)
                finished_orders.append(updated_order)
        return finished_orders

    def _refresh_position(self, position_status: PositionStatus) -> None:
        self._latest_position_status = position_status
        self.state.set(POSITION_AMOUNT_KEY, position_status.amount)
        self.state.set(POSITION_AVG_PRICE_KEY, position_status.entry_price)
        self.state.set(POSITION_SIDE_KEY, position_status.position_side)
        self.state.set(LEVERAGE_KEY, position_status.leverage)


    def _handle_open_position_canceled(self, order: FuturesOrder) -> None:
        """处理开仓限价单被取消的事件"""
        assert order.status == "CANCELED"
        assert order.type == "LIMIT", "限价单挂单才可以取消"

        # 释放冻结余额
        self.state.increase(FREE_BALANCE_KEY, self.limit_order_suspended_balance)
        self.state.set(LIMIT_ORDER_SUSPENDED_BALANCE_KEY, 0)
        self.state.delete(RECENT_OPEN_POSITION_LIMIT_ORDER_KEY)
        self._add_operation_history(order.timestamp, "取消开仓限价单")

    def _handle_open_position_pending(self, order: FuturesOrder) -> None:
        assert order.status == "NEW"
        assert order.type == "LIMIT", "限价单挂单才会有冻结余额"

        # 限价单挂单冻结余额
        suspended_balance = (order.limit_order_price * order.amount) / self.leverage
        self.state.set(RECENT_OPEN_POSITION_LIMIT_ORDER_KEY, order.raw)
        self.state.set(LIMIT_ORDER_SUSPENDED_BALANCE_KEY, suspended_balance)
        self.state.decrease(FREE_BALANCE_KEY, suspended_balance)
        self.state.set(POSITION_SIDE_KEY, POSITION_SIDE_LONG if order.side == ORDER_SIDE_BUY else POSITION_SIDE_SHORT)
        self._add_operation_history(order.timestamp, f"挂出开仓限价单, 限价单价格: {order.limit_order_price}, 数量: {order.amount}, 冻结余额: {suspended_balance}")

    def _handle_open_position_success(self, order: FuturesOrder) -> None:
        assert order.status == "FILLED"
        
        if order.type == "LIMIT":
            self.state.set(LIMIT_ORDER_SUSPENDED_BALANCE_KEY, 0)
            self.state.delete(RECENT_OPEN_POSITION_LIMIT_ORDER_KEY)
        else:
            self.state.decrease(FREE_BALANCE_KEY, order.cost / self.leverage)

        if order.side == "buy" :
            # 买入开仓，做多
            self.state.set(POSITION_AMOUNT_KEY, order.amount)
            self.state.set(POSITION_AVG_PRICE_KEY, order.avg_price)
            self.state.set(POSITION_SIDE_KEY, POSITION_SIDE_LONG)
        elif order.side == "sell":
            # 卖出开仓，做空
            self.state.set(POSITION_AVG_PRICE_KEY, order.avg_price)
            self.state.set(POSITION_AMOUNT_KEY, order.amount)
            self.state.set(POSITION_SIDE_KEY, POSITION_SIDE_SHORT)
        else:
            self.state.set(ERROR_KEY, True)

        self._add_operation_history(order.timestamp, f"开{'空' if order.side == 'sell' else '多'}仓成功, 成交均价: {order.avg_price}, 数量: {order.amount}, 仓位水平 {self.position_level:.2%}")

    def _handle_add_position_canceled(self, order: FuturesOrder) -> None:
        """处理开仓限价单被取消的事件"""
        assert order.status == "CANCELED"
        assert order.type == "LIMIT", "限价单挂单才可以取消"

        # 释放冻结余额
        suspended_balance = (order.amount * order.limit_order_price) / self.leverage
        self.state.increase(FREE_BALANCE_KEY, suspended_balance)
        self.state.decrease(LIMIT_ORDER_SUSPENDED_BALANCE_KEY, suspended_balance)
        self.state.delete([RECENT_ADD_POSITION_LIMIT_ORDER_KEY, order.id])

        self._add_operation_history(order.timestamp, f"取消加仓限价单")

    def _handle_add_position_pending(self, order: FuturesOrder) -> None:
        """处理加仓挂单事件"""
        assert order.status == "NEW", "加仓挂单状态应为 NEW"
        assert order.type == "LIMIT", "限价单挂单才会有冻结余额"
        assert order.side == ("buy" if self.position_side == POSITION_SIDE_LONG else "sell"), "加仓订单方向应与当前仓位方向一致"

        # 限价单挂单冻结余额
        suspended_balance = (order.amount * order.limit_order_price) / self.leverage
        self.state.set([RECENT_ADD_POSITION_LIMIT_ORDER_KEY, order.id], order.raw)
        self.state.decrease(FREE_BALANCE_KEY, suspended_balance)
        self.state.increase(LIMIT_ORDER_SUSPENDED_BALANCE_KEY, suspended_balance)
        self._add_operation_history(order.timestamp, f"挂出加仓限价单, 价格: {order.limit_order_price}, 数量: {order.amount}, 冻结余额: {suspended_balance}")

    def _handle_add_position_success(self, order: FuturesOrder) -> None:
        """处理加仓成功事件"""
        assert order.status == "FILLED"
        assert order.side == ("buy" if self.position_side == POSITION_SIDE_LONG else "sell"), "加仓订单方向应与当前仓位方向一致"

        if order.type == "LIMIT":
            # 释放冻结余额, 这里可能有点不对，实际成交的时候并不是冻结的那个金额，可能会退一部分回来吧，先忽略
            suspended_balance = (order.amount * order.limit_order_price) / self.leverage
            self.state.decrease(LIMIT_ORDER_SUSPENDED_BALANCE_KEY, suspended_balance)
            self.state.delete([RECENT_ADD_POSITION_LIMIT_ORDER_KEY, order.id])
        else:
            self.state.decrease(FREE_BALANCE_KEY, order.cost / self.leverage)

        self.state.set(
            POSITION_AVG_PRICE_KEY,
            cal_avg_price(
                order.avg_price, order.amount,
                self.position_avg_price, self.position_amount
            )
        )
        self.state.increase(POSITION_AMOUNT_KEY, order.amount)

        self._add_operation_history(order.timestamp, f"加{'空' if order.side == 'sell' else '多'}仓成功, 成交均价: {order.avg_price}, 数量: {order.amount}, 仓位水平 {self.position_level:.2%}")

    def _handle_decrease_position_pending(self, order: FuturesOrder) -> None:
        """处理减仓挂单事件"""
        assert order.status == "NEW"
        assert order.type == "LIMIT", "限价单挂单才会有冻结余额"
        assert order.side == ("sell" if self.position_side == POSITION_SIDE_LONG else "buy"), "减仓订单方向应与当前仓位方向一致"
        
        self.state.set([RECENT_DECREASE_POSITION_LIMIT_ORDER_KEY, order.id], order.raw)
        self._add_operation_history(order.timestamp, f"挂出减仓限价单, 价格: {order.limit_order_price}, 数量: {order.amount}")

    def _handle_decrease_position_success(self, order: FuturesOrder) -> None:
        """处理减仓成功事件"""
        assert order.status == "FILLED"
        assert order.side == ("sell" if self.position_side == POSITION_SIDE_LONG else "buy"), "减仓订单方向应与当前仓位方向一致"

        if order.type == "LIMIT":
            self.state.delete([RECENT_DECREASE_POSITION_LIMIT_ORDER_KEY, order.id])

        # 减少仓位数量
        self.state.decrease(POSITION_AMOUNT_KEY, order.amount)
        # 增加可用余额（减仓释放的资金）
        if self.position_side == POSITION_SIDE_LONG:
            # 做多减仓，增加可用余额
            self.state.increase(FREE_BALANCE_KEY, order.cost / self.leverage)
        else:
            # 做空减仓，增加可用余额
            # 赎回本金
            self.state.increase(FREE_BALANCE_KEY, self.position_avg_price * order.amount / self.leverage)
            # 获利
            self.state.increase(FREE_BALANCE_KEY, (self.position_avg_price - order.avg_price) * order.amount)

        self._add_operation_history(order.timestamp, f"减{'空' if order.side == 'sell' else '多'}仓成功, 成交均价: {order.avg_price}, 数量: {order.amount}, 仓位水平 {self.position_level:.2%}")
    
    def _handle_decrease_position_canceled(self, order: FuturesOrder) -> None:
        """处理减仓挂单被取消的事件"""
        assert order.status == "CANCELED"
        assert order.type == "LIMIT", "限价单挂单才可以取消"

        # 释放冻结余额
        self.state.delete([RECENT_DECREASE_POSITION_LIMIT_ORDER_KEY, order.id])
        self._add_operation_history(order.timestamp, f"取消减仓限价单")

    def _handle_close_position_state_change(self, order: FuturesOrder) -> None:
        assert order.status == "FILLED"
        
        if self.position_side == POSITION_SIDE_LONG:
            # 做多平仓
            self.state.increase(FREE_BALANCE_KEY, order.cost / self.leverage)
        else:
            # 做空平仓
            # 赎回本金
            self.state.increase(FREE_BALANCE_KEY, self.position_avg_price * order.amount / self.leverage)
            # 获利
            self.state.increase(FREE_BALANCE_KEY, (self.position_avg_price - order.avg_price) * order.amount)

        # 重置仓位状态
        self._reset_position_state_for_close_position()

    def _handle_close_position_success(self, order: FuturesOrder) -> None:
        """处理平仓成功事件"""
        self._handle_close_position_state_change(order)
        self._add_operation_history(order.timestamp, f"平仓")

    def _handle_take_profit_pending(self, order: FuturesOrder) -> None:
        """处理止盈挂单事件"""
        assert order.status == "NEW"
        assert order.type == "TAKE_PROFIT_MARKET", "止盈订单类型错误"
        
        self.state.set(RECENT_TAKE_PROFIT_LIMIT_ORDER_KEY, order.raw)
        self._add_operation_history(order.timestamp, f"止盈挂单, 价格: {order.limit_order_price}")

    def _handle_take_profit_success(self, order: FuturesOrder) -> None:
        """处理止盈成功事件"""
        if self.pending_stop_loss_order:
            self.futures_operator.cancel_order(self.pending_stop_loss_order.id)
            self.state.delete(RECENT_STOP_LOSS_LIMIT_ORDER_KEY)
        self._handle_close_position_state_change(order)
        self._add_operation_history(order.timestamp, f"止盈平仓触发")

    def _handle_take_profit_canceled(self, order: FuturesOrder) -> None:
        """处理止盈取消事件"""
        assert order.status == "CANCELED"
        self.state.delete(RECENT_TAKE_PROFIT_LIMIT_ORDER_KEY)
        self._add_operation_history(order.timestamp, f"取消止盈挂单")

    def _handle_stop_loss_pending(self, order: FuturesOrder) -> None:
        """处理止损挂单事件"""
        assert order.status == "NEW"
        assert order.type in ["STOP_MARKET"], "止损订单类型错误"

        self.state.set(RECENT_STOP_LOSS_LIMIT_ORDER_KEY, order.raw)
        self._add_operation_history(order.timestamp, f"止损挂单, 价格: {order.limit_order_price}")

    def _handle_stop_loss_success(self, order: FuturesOrder) -> None:
        """处理止损成功事件"""
        if self.pending_take_profit_order:
            self.futures_operator.cancel_order(self.pending_take_profit_order.id)
            self.state.delete(RECENT_TAKE_PROFIT_LIMIT_ORDER_KEY)

        self._handle_close_position_state_change(order)
        self._add_operation_history(order.timestamp, f"止损平仓触发")

    def _handle_stop_loss_canceled(self, order: FuturesOrder) -> None:
        """处理止损取消事件"""
        assert order.status == "CANCELED"
        self.state.delete(RECENT_STOP_LOSS_LIMIT_ORDER_KEY)
        self._add_operation_history(order.timestamp, f"取消止损挂单")

    def _reset_position_state_for_close_position(self) -> None:
        """重置仓位相关状态"""
        self.state.set(POSITION_AMOUNT_KEY, 0)
        self.state.set(POSITION_AVG_PRICE_KEY, 0)
        self.state.set(POSITION_SIDE_KEY, POSITION_SIDE_NONE)
        self.state.delete(RECENT_TAKE_PROFIT_LIMIT_ORDER_KEY)
        self.state.delete(RECENT_STOP_LOSS_LIMIT_ORDER_KEY)
        self.state.delete(RECENT_OPEN_POSITION_LIMIT_ORDER_KEY)
        self.state.set(RECENT_ADD_POSITION_LIMIT_ORDER_KEY, {})
        self.state.set(RECENT_DECREASE_POSITION_LIMIT_ORDER_KEY, {})

    def _handle_order_filled(self, order: FuturesOrder) -> None:
        assert order.status == "FILLED", "订单状态应为 FILLED"

        order_id = order.id
        if self.pending_open_position_order and order_id == self.pending_open_position_order.id:
            self._handle_open_position_success(order)
        elif order_id in self.state.get(RECENT_ADD_POSITION_LIMIT_ORDER_KEY):
            self._handle_add_position_success(order)
        elif order_id in self.state.get(RECENT_DECREASE_POSITION_LIMIT_ORDER_KEY):
            self._handle_decrease_position_success(order)
        elif self.pending_take_profit_order and order_id == self.pending_take_profit_order.id:
            self._handle_take_profit_success(order)
        elif self.pending_stop_loss_order and order_id == self.pending_stop_loss_order.id:
            self._handle_stop_loss_success(order)
        else:
            # Not my order
            pass

    def _handle_order_canceled(self, order: FuturesOrder) -> None:
        assert order.status == "CANCELED", "订单状态应为 CANCELED"
        logger.debug(f"订单 {order.id} 被取消 {order}")
        order_id = order.id
        if self.pending_open_position_order and order_id == self.pending_open_position_order.id:
            self._handle_open_position_canceled(order)
        elif order_id in self.state.get(RECENT_ADD_POSITION_LIMIT_ORDER_KEY):
            self._handle_add_position_canceled(order)
        elif order_id in self.state.get(RECENT_DECREASE_POSITION_LIMIT_ORDER_KEY):
            self._handle_decrease_position_canceled(order)
        elif self.pending_take_profit_order and order_id == self.pending_take_profit_order.id:
            self._handle_take_profit_canceled(order)
        elif self.pending_stop_loss_order and order_id == self.pending_stop_loss_order.id:
            self._handle_stop_loss_canceled(order)
        else:
            # Not my order
            pass

    def _order_listening_loop(self):
        while not self._order_listening_thread_stop_event.is_set():
            if self.all_pending_orders:
                if datetime.now().minute % 5 == 0:
                    # 每5分钟检查一次
                    finished_orders = self._handle_state_change_for_pending_orders()
                    if finished_orders and self._order_listening_callbacks:
                        for order in finished_orders:
                            for callback in self._order_listening_callbacks:
                                callback(order)
            time.sleep(1)

    def save(self):
        """
        保存当前状态到持久化存储
        """
        self.state.save()

    def update_leverage(self, leverage: int):
        """
        更新杠杆倍数
        """
        self.state.set(LEVERAGE_KEY, leverage)

    def listen_for_limit_order_change(self, callback: Optional[Callable]) -> Callable:
        logger.info(f"开始监听订单状态变化")
        if self._order_listening_thread and self._order_listening_thread.is_alive():
            if callback:
                with self._order_listening_thread_callback_write_lock:
                    self._order_listening_callbacks.append(callback)
        else:
            logger.info("启动订单状态变化监听线程")
            self._order_listening_thread_stop_event.clear()
            self._order_listening_thread = threading.Thread(target=self._order_listening_loop)
            self._order_listening_thread.start()
            if callback:
                with self._order_listening_thread_callback_write_lock:
                    self._order_listening_callbacks.append(callback)

        def stop():
            logger.info("停止监听订单状态变化")
            with self._order_listening_thread_callback_write_lock:
                self._order_listening_callbacks.remove(callback)
                if not self._order_listening_callbacks:
                    self._order_listening_thread_stop_event.set()
                    self._order_listening_thread.join()

        return stop

    def handle_order_event(
            self, 
            event: str, 
            order: FuturesOrder
        ):
        """
        处理订单事件，更新仓位状态。
        
        """
        assert event in ALL_EVENTS, f"未知事件类型: {event}"
        logger.debug("处理订单事件: %s, 订单: %s", event, order)
        # 开仓事件
        if event == OPEN_POSITION and order.status == ORDER_STATUS_FILLED:
            self._handle_open_position_success(order)
        elif event == OPEN_POSITION and order.status == ORDER_STATUS_NEW:
            self._handle_open_position_pending(order)
        elif event == OPEN_POSITION and order.status == ORDER_STATUS_CANCELED:
            self._handle_open_position_canceled(order)

        # 加仓事件
        elif event == ADD_POSITION and order.status == ORDER_STATUS_FILLED:
            self._handle_add_position_success(order)
        elif event == ADD_POSITION and order.status == ORDER_STATUS_NEW:
            self._handle_add_position_pending(order)
        elif event == ADD_POSITION and order.status == ORDER_STATUS_CANCELED:
            self._handle_add_position_canceled(order)
            
        # 减仓事件
        elif event == DECREASE_POSITION and order.status == ORDER_STATUS_FILLED:
            self._handle_decrease_position_success(order)
        elif event == DECREASE_POSITION and order.status == ORDER_STATUS_NEW:
            self._handle_decrease_position_pending(order)
        elif event == DECREASE_POSITION and order.status == ORDER_STATUS_CANCELED:
            self._handle_decrease_position_canceled(order)
            
        # 平仓事件
        elif event == CLOSE_POSITION and order.status == ORDER_STATUS_FILLED:
            self._handle_close_position_success(order)

        # 止盈事件
        elif event == TAKE_PROFIT and order.status == ORDER_STATUS_FILLED:
            self._handle_take_profit_success(order)
        elif event == TAKE_PROFIT and order.status == ORDER_STATUS_NEW:
            self._handle_take_profit_pending(order)
        elif event == TAKE_PROFIT and order.status in [ORDER_STATUS_CANCELED, ORDER_STATUS_EXPIRED]:
            self._handle_take_profit_canceled(order)

        # 止损事件
        elif event == STOP_LOSS and order.status == ORDER_STATUS_FILLED:
            self._handle_stop_loss_success(order)
        elif event == STOP_LOSS and order.status == ORDER_STATUS_NEW:
            self._handle_stop_loss_pending(order)
        elif event == STOP_LOSS and order.status in [ORDER_STATUS_CANCELED, ORDER_STATUS_EXPIRED]:
           self._handle_stop_loss_canceled(order)
        elif event == LIMIT_ORDER_CANCELED:
            self._handle_order_canceled(order)
        elif event == LIMIT_ORDER_FILLED:
            self._handle_order_filled(order)
        else:
            self.state.set(ERROR_KEY, True)
            
        
    def get_position_info_text(self) -> str:
        """
        获取当前仓位信息，包括杠杆倍率、仓位水平等。
        返回：仓位信息结构体或字典。
        """
        if self.position_side == "none":
            position_info_str = (
                f"当前没有持仓。\n"
                f"当前杠杆倍数: {self.leverage}\n"
                f"可用: {self.free_balance}USDT\n"
                f"杠杆后余额: {self.free_balance * self.leverage:2f}USDT\n"
                f"当前标记价格: {self.mark_price}\n"
                f"杠杆后余额最大可开多/开空合约数量: {self.free_balance * self.leverage / self.mark_price:2f}\n"
            )
            if self.pending_open_position_order:
                position_info_str += (
                    f"当前有未完成开仓限价单: {self.pending_open_position_order.id}\n"
                    f"限价单价格: {self.pending_open_position_order.limit_order_price}\n"
                    f"限价单创建时间: {str(self.pending_open_position_order.timestamp)}\n"
                    f"限价单委托数量: {self.pending_open_position_order.amount}\n"
                    f"限价单状态: {self.pending_open_position_order.status}\n"
                    f"限价单方向: {'做空' if self.pending_open_position_order.side == 'sell' else '做多'}\n"
                )
            return position_info_str

        position_info_str = (
            f"持仓数量: {self.position_amount}\n"
            f"仓位方向：{'做多' if self.position_side == 'long' else '做空'}\n"
            f"仓位水平: {self.position_level:.2%}\n"
            f"开仓均价: {self.position_avg_price}\n"
            f"盈亏平衡价格: {self.break_even_price}\n"
            f"当前标记价格: {self.mark_price}\n"
            f"未实现盈亏: {self.unrealized_pnl}\n"
            f"强平价格: {self.liquidation_price}\n"
            f"当前杠杆倍数: {self.leverage}\n"
            f"持仓名义价值: {self.position_value}\n"
            f"当前可用: {self.free_balance:2f}USDT\n"
            f"杠杆后余额: {self.free_balance * self.leverage:2f}USDT\n"
            f"杠杆后余额最大可继续加仓{'开多' if self.position_amount > 0 else '开空'}合约数量: {self.free_balance * self.leverage / self.mark_price:2f}\n"
            f"最大可反向{'开多' if self.position_amount < 0 else '开空'}合约数量: {self.free_balance * self.leverage / self.mark_price + self.position_amount:2f}\n"
        )
        if self.pending_add_position_orders:
            for recent_add_position_limit_order in self.pending_add_position_orders:
                position_info_str += (
                    f"当前有未完成加仓限价单: {recent_add_position_limit_order.id}\n"
                    f"  创建时间: {str(recent_add_position_limit_order.timestamp)}\n"
                    f"  限价单价格: {recent_add_position_limit_order.limit_order_price}\n"
                    f"  限价单委托数量: {recent_add_position_limit_order.amount}\n"
                )
        if self.pending_decrease_position_orders:
            for recent_decrease_position_limit_order in self.pending_decrease_position_orders:
                position_info_str += (
                    f"当前有未完成减仓限价单: {recent_decrease_position_limit_order.id}\n"
                    f"  创建时间: {str(recent_decrease_position_limit_order.timestamp)}\n"
                    f"  限价单价格: {recent_decrease_position_limit_order.limit_order_price}\n"
                    f"  限价单委托数量: {recent_decrease_position_limit_order.amount}\n"
                )
        recent_take_profit_limit_order = self.pending_take_profit_order
        recent_stop_loss_limit_order = self.pending_stop_loss_order
        if recent_take_profit_limit_order:
            position_info_str += (
                f"当前有未完成止盈平仓限价单({recent_take_profit_limit_order.side}): {recent_take_profit_limit_order.id}\n"
                f"当前止盈价格: {recent_take_profit_limit_order.limit_order_price}\n"
            )
        else:
            position_info_str += (
                "当前没有设置止盈。\n"
            )
        if recent_stop_loss_limit_order:
            position_info_str += (
                f"当前有未完成止损平仓限价单({recent_stop_loss_limit_order.side}): {recent_stop_loss_limit_order.id}\n"
                f"当前止损限价格: {recent_stop_loss_limit_order.limit_order_price}\n"
            )
        else:
            position_info_str += (
                "当前没有设置止损。\n"
            )

        position_history = self.position_history
        if position_history:
            position_info_str += "24H历史操作记录:\n"
            history_in_24h = [
                record for record in position_history if (datetime.now() - datetime.fromisoformat(record['time'])).total_seconds() < 86400
            ]
            for record in history_in_24h:
                position_info_str += f"  - [{record['time']}] {record['description']}\n"

        position_info_str += f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        return position_info_str