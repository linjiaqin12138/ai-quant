from datetime import datetime
import time
from textwrap import dedent
import threading
from typing import Annotated, Any, Dict, Literal, Optional
from lib.adapter.llm import LlmAbstract

from lib.logger import logger
from lib.modules.crypto_futures.binance_futures_operations import BinanceFuturesOperator
from lib.modules.crypto_futures.future_position_manager import FuturesPositionStateManager
from lib.modules.agent import Agent
from lib.modules.crypto_futures.model import FuturesOrder
class FuturesOperationAgent:

    def __init__(
            self, 
            futures_operator: BinanceFuturesOperator, 
            futures_position_manager: FuturesPositionStateManager,
            llm: LlmAbstract
        ):
        self.futures_operator = futures_operator
        self.futures_position_manager = futures_position_manager
        self.agent = Agent(llm=llm)
        self.listening_orders: set[str] = set()  # 用于存储正在监听的订单ID

        self.agent.set_system_prompt(
            dedent(
                f"""
                    你是专业的交易执行专家，负责根据操作方案调用工具执行具体的交易操作。

                    ## 核心原则
                    1. **安全第一**: 每个操作都要考虑风险，避免造成不必要的损失，遇到错误立马放弃
                    2. **顺序严格**: 工具调用必须按照正确顺序执行，顺序错误可能导致严重后果
                    3. **市价优先**: 优先使用市价单，避免限价单不成交错过行情
                    4. **状态同步**: 每次操作前确认当前状态，避免重复或冲突操作

                    ## 操作流程约束
                    ### 开新仓流程
                    1. 如需调整杠杆 → 调用set_leverage
                    2. 如有冲突的挂单 → 调用cancel_order取消
                    3. 如有现有仓位 → 调用close_current_position平仓
                    4. 调用open_new_position开仓
                    5. 设置止盈止损 → 调用set_position_stop_price

                    ### 调整现有仓位流程
                    1. 加仓：直接调用increase_current_position
                    2. 减仓：直接调用decrease_current_position
                    3. 平仓：先取消止盈止损单 → 调用close_current_position
                    4. 调整止盈止损：直接调用set_position_stop_price（会自动取消旧的）

                    ### 反向开仓流程（做多转做空或做空转做多）
                    1. 取消所有止盈止损单 → cancel_order
                    2. 平掉现有仓位 → close_current_position
                    3. 开新的反向仓位 → open_new_position
                    4. 设置新的止盈止损 → set_position_stop_price

                    ## 工具使用规范
                    ### cancel_order
                    - 用于取消未完成的限价单
                    - 必须在冲突操作前调用
                    - 取消止盈止损单时要同时取消配对的单子

                    ### close_current_position  
                    - 使用市价单立即平仓
                    - 平仓前建议先取消止盈止损单
                    - 不要在有未完成开仓限价单时调用

                    ### open_new_position
                    - 只能在无仓位时调用
                    - 优先使用市价单（order_type="market"）
                    - 限价单需要合理的价格设置

                    ### increase_current_position/decrease_current_position
                    - 只能在有仓位时调用
                    - 方向必须与当前仓位一致
                    - 优先使用市价单

                    ### set_position_stop_price
                    - 可以只设置止盈或止损，也可同时设置
                    - 会自动取消之前的止盈止损单
                    - 价格设置要合理（做多：止盈>当前价>止损，做空相反）

                    ### set_leverage
                    - 在开仓前调用
                    - 杠杆设置要考虑风险承受能力

                    ### listen_for_order_resolve
                    - 用于监听订单状态完成或取消，在挂出限价单后根据返回限价单的id进行监听

                    ## 风险控制要求
                    1. **价格合理性**: 限价单价格不能偏离市价太远
                    2. **仓位大小**: 不能超过可用余额允许的最大仓位
                    3. **止损必设**: 开仓后必须设置止损，防止巨额亏损
                    4. **操作确认**: 重大操作前要基于当前仓位状态进行判断

                    ## 执行指导
                    1. **分步执行**: 复杂操作要分步骤执行，不要一次调用多个工具
                    2. **状态检查**: 每步操作后检查结果，确保成功后再进行下一步
                    3. **错误处理**: 如果操作失败，要分析原因并调整策略
                    4. **日志记录**: 重要操作要有清晰的说明和理由

                    ## 特别注意
                    - 限价单可能不成交，需要监控状态或改用市价单
                    - 不能同时持有多空仓位
                    - 止盈止损只能各设置一次，重复设置会取消之前的
                    - 取消订单时要考虑对资金状态的影响
                    - 由于系统限制，加建仓限价单只能各设置一个，不能分批挂多个在不同价位

                    请严格按照以上规范执行操作，确保每个步骤都安全可靠。
                """
            )
        )
        self.agent.register_tool(self.cancel_order)
        self.agent.register_tool(self.close_current_position)
        self.agent.register_tool(self.set_position_stop_price)
        self.agent.register_tool(self.set_leverage)
        self.agent.register_tool(self.open_new_position)
        self.agent.register_tool(self.increase_current_position)
        self.agent.register_tool(self.decrease_current_position)
        # self.agent.register_tool(self.listen_for_order_resolve)

    @property
    def is_listening_orders(self) -> bool:
        return len(self.listening_orders) > 0

    def set_leverage(self, leverage: Annotated[int, "杠杆倍率"]) -> str:
        """
        设置杠杆倍率
        """
        self.futures_operator.set_leverage(leverage)
        self.futures_position_manager.update_leverage(leverage)
        return "success"

    def cancel_order(self, order_id: Annotated[str, "订单ID"]) -> Dict[str, str]:
        """
        取消订单。
        参数：
            order_id: 订单ID
        返回：取消结果信息。
        """
        order = self.futures_operator.cancel_order(order_id)
        self.futures_position_manager.handle_order_event("order_canceled", order)
        return order.raw
    
    def close_current_position(
        self
    ) -> dict:
        """
        立即使用市价单平掉当前仓位。限价平仓应该使用仓位止盈止损。
        """
        trade_side = "sell" if self.futures_position_manager.position_side == "long" else "buy"
        if self.futures_position_manager.pending_open_position_order:
            logger.warning("检测到有开仓限价单, 没有先取消它们就关仓")
            self.cancel_order(self.futures_position_manager.pending_open_position_order.id)
        if self.futures_position_manager.pending_add_position_orders:
            logger.warning("检测到有加仓限价单, 没有先取消它们就关仓")
            for order in self.futures_position_manager.pending_add_position_orders:
                self.cancel_order(order.id)
        if self.futures_position_manager.pending_decrease_position_orders:
            logger.warning("检测到有减仓限价单, 没有先取消它们就关仓")
            for order in self.futures_position_manager.pending_decrease_position_orders:
                self.cancel_order(order.id)
        if self.futures_position_manager.pending_take_profit_order:
            logger.warning("检测到有止盈限价单, 没有先取消它们就关仓")
            self.cancel_order(self.futures_position_manager.pending_take_profit_order.id)
        if self.futures_position_manager.pending_stop_loss_order:
            logger.warning("检测到有止损限价单, 没有先取消它们就关仓")
            self.cancel_order(self.futures_position_manager.pending_stop_loss_order.id)

        if self.futures_position_manager.position_side == "none":
            return { "error": "当前没有仓位，无法平仓" }

        order = self.futures_operator.create_order(
            'market',
            side=trade_side,
            amount=self.futures_position_manager.position_amount
        )
        self.futures_position_manager.handle_order_event("close_position", order)

        return order.raw
    
    def open_new_position(
            self, 
            position_side: Annotated[
                Literal["long", "short"], 
                "仓位方向"
            ],
            order_type: Annotated[
                Literal["market", "limit"], 
                "订单类型, 市价单(market), 限价单(limit)"
            ],
            amount: Annotated[
                float,
                "开仓合约数量"
            ],
            price: Annotated[
                Optional[float],
                "限价单价格，限价单必填"
            ] = None
        ) -> dict:
        """
        开仓操作，支持市价单和限价单。
        """
        trade_side = "buy" if position_side == "long" else "sell"
        if self.futures_position_manager.position_side != "none":
            return { "error": "当前已有仓位，请先平掉当前仓位" }
            
        order = self.futures_operator.create_order(
            order_type=order_type,
            side=trade_side,
            amount=amount,
            price=price
        )
        self.futures_position_manager.handle_order_event("open_position", order)
        return order.raw

    def increase_current_position(
            self,
            order_type: Annotated[
                Literal["market", "limit"], 
                "订单类型, 市价单(market), 限价单(limit)"
            ],
            amount: Annotated[
                float,
                "增加仓位合约数量"
            ],
            price: Annotated[
                Optional[float],
                "限价单价格，限价单必填"
            ] = None
        ) -> dict:
        """
        增加当前仓位的合约数量，使用限价单或市价单。
        """
        trade_side = "buy" if self.futures_position_manager.position_side == "long" else "sell"
        order = self.futures_operator.create_order(
            order_type=order_type,
            side=trade_side,
            amount=amount,
            price=price
        )
        self.futures_position_manager.handle_order_event("add_position", order)
        return order.raw
    
    def decrease_current_position(
            self,
            order_type: Annotated[
                Literal["market", "limit"], 
                "订单类型, 市价单(market), 限价单(limit)"
            ],
            amount: Annotated[
                float,
                "减少仓位合约数量"
            ],
            price: Annotated[
                Optional[float],
                "限价单价格，限价单必填"
            ] = None
        ) -> dict:
        """
        减少当前仓位的合约数量，使用限价单或市价单。
        """
        trade_side = "sell" if self.futures_position_manager.position_side == "long" else "buy"
        order = self.futures_operator.create_order(
            order_type=order_type,
            side=trade_side,
            amount=amount,
            price=price
        )
        self.futures_position_manager.handle_order_event("decrease_position", order)
        return order.raw

    def set_position_stop_price(
            self, 
            take_profit: Annotated[
                Optional[float],
                "止盈价格"
            ] = None,
            stop_loss: Annotated[
                Optional[float],
                "止损价格"
            ] = None
        ) -> Dict[str, Any]:
        """
        设置当前仓位的止盈和止损价格，到达止盈止损价格时自动平掉整个仓位，无法设置分级平仓。可以只设置止盈或止损，也可同时设置，不能都不设置
        """
        if not take_profit and not stop_loss:
            return { "error": "止盈止损价格不能都为空" }
        result = {}
        if self.futures_position_manager.pending_take_profit_order:
            if self.futures_position_manager.pending_take_profit_order.limit_order_price != take_profit:
                logger.warning("检测到有未完成的止盈单, 先取消它")
                self.cancel_order(self.futures_position_manager.pending_take_profit_order.id)
            else:
                result["take_profit"] = { "error": "新设置的止盈价格和当前未完成的止盈单价格相同，请勿重复设置" }
                take_profit = None  # 不再设置止盈
        if self.futures_position_manager.pending_stop_loss_order:
            if self.futures_position_manager.pending_stop_loss_order.limit_order_price != stop_loss:
                logger.warning("检测到有未完成的止损单, 先取消它")
                self.cancel_order(self.futures_position_manager.pending_stop_loss_order.id)
            else:
                result["stop_loss"] = { "error": "新设置的止损价格和当前未完成的止损单价格相同，请勿重复设置" }
                stop_loss = None  # 不再设置止损

        if stop_loss is None and take_profit is None:
            return result
    
        stop_price_result = self.futures_operator.set_position_stop_price(
            take_profit=take_profit,
            stop_loss=stop_loss
        )
        if take_profit:
            self.futures_position_manager.handle_order_event(
                "take_profit",
                stop_price_result.take_profit_order_result
            )
            result["take_profit"] = stop_price_result.take_profit_order_result.raw
        if stop_loss:
            self.futures_position_manager.handle_order_event(
                "stop_loss",
                stop_price_result.stop_loss_order_result
            )
            result["stop_loss"] = stop_price_result.stop_loss_order_result.raw
        return result
    
    def listen_for_order_resolve(self, order_id: str) -> str:
        """
        监听订单状态变化，直到订单被取消或完成。
        """
        logger.info(f"开始监听订单状态变化: {order_id}")
        self.listening_orders.add(order_id)
        
    def wait_for_orders_resolve(self, until: datetime):
        """
        等待订单状态变化，直到订单被取消或完成。
        """
        if not self.is_listening_orders:
            logger.warning(f"没有正在监听的订单")
            return None
        
        def callback(order: FuturesOrder):
            if order.id in self.listening_orders:
                logger.info(f"订单 {order.id} 状态变化: {order.status}")
                if order.status == "FILLED":
                    self.listening_orders.remove(order.id)
                    self.agent.ask(f"订单 {order.id} 已完成")

        stopper = self.futures_position_manager.listen_for_limit_order_change(callback)
        logger.info(f"等待订单状态变化，直到 {until} 之前")
        while self.is_listening_orders and datetime.now() < until:
            time.sleep(1)

        stopper()

    def ask(self, question: str) -> str:
        """
        使用 LLM 回答问题
        """
        self.agent.clear_context()
        return self.agent.ask(question, tool_use=True)