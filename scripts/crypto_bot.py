from datetime import datetime, timedelta
import json
from textwrap import dedent, indent
from typing import Annotated, Any, Dict, Literal, Optional
import typer

from lib.adapter.database.db_transaction import create_transaction
from lib.adapter.llm import get_llm, get_llm_direct_ask
from lib.adapter.exchange.crypto_exchange import BinanceExchange
from lib.adapter.notification.push_plus import PushPlus
from lib.logger import logger
from lib.modules.news_proxy import news_proxy
from lib.modules.agent import get_agent
from lib.modules.agents.common import format_indicators, format_ohlcv_list, format_ohlcv_pattern
from lib.modules.notification_logger import NotificationLogger
from lib.modules.trade.crypto import crypto
from lib.modules.strategy.state import PersisitentState
from lib.modules.trade.crypto import crypto
from lib.utils.news import render_news_in_markdown_group_by_platform
import threading

app = typer.Typer()

def cal_avg_price(price1: float, amount1: float, price2: float, amount2: float) -> float:
    """
    计算两个价格和数量的加权平均价格
    """
    return (price1 * amount1 + price2 * amount2) / (amount1 + amount2) if (amount1 + amount2) != 0 else 0
class CryptoAgent:

    def __init__(
            self,
            symbol: str,
            investment: float = 1000.0
        ):
        self.binance = BinanceExchange(future_mode=True)
        self.symbol = symbol
        self.message_express = NotificationLogger(f"{symbol} Crypto Bot", PushPlus(template="markdown"))
        self.ask_for_technical_analysis = get_llm_direct_ask(
            system_prompt=dedent(f"""
            你是一位经验丰富的技术分析专家，擅长深入的技术分析。
            
            分析原则：
            1. **综合分析**: 结合价格走势、技术指标和K线形态进行综合判断
            2. **风险评估**: 务必评估当前市场风险，给出明确的风险提示
            3. **多时间周期**: 分析短期(1小时)、中期(1天)的趋势一致性
            4. **量价关系**: 关注成交量与价格变化的配合度

            ## 输出要求
            1. 提供详细的技术分析报告，包含：
                - 趋势分析（短期=1小时，中期=1天，并分析趋势一致性）
                - 关键支撑和阻力位（标注具体价格区间）
                - 技术指标解读（SMA、MACD、RSI、BOLL、ATR等，重点关注背离信号）
                - K线形态分析（如检测到主要形态则列出，否则说明"无明显K线形态"）
                - 成交量分析（量价配合度）
                - 风险评估（具体风险点和概率评估）
            2. 给出明确的交易建议和可信度：
                - **强烈买入**: 多个指标强烈看涨，可信度90%以上
                - **买入**: 多个指标显示积极信号，可信度70-90%
                - **观望**: 信号不明确或处于关键位置，可信度50-70%
                - **卖出**: 多个指标显示负面信号，可信度70-90%
                - **强烈卖出**: 多个指标强烈看跌，可信度90%以上
            3. 在报告末尾添加一个Markdown表格，总结关键要点：
                | 时间周期 | 分析项目 | 状态 | 说明 | 可信度 |
                |----------|----------|------|------|--------|
                | 短期/中期 | 趋势方向 | 上升/下降/震荡 | 具体说明 | 高/中/低 |
                | 短期/中期 | 技术指标 | 积极/中性/消极 | 主要信号 | 高/中/低 |
                | 短期/中期 | K线形态 | 看涨/看跌/中性 | 形态说明 | 高/中/低 |
                | - | 风险等级 | 低/中/高 | 风险因素 | - |
                | - | 交易建议 | 强烈买入/买入/观望/卖出/强烈卖出 | 建议理由 | 可信度% |
            """),
            llm=get_llm("paoluz", "gemini-2.5-flash")
        )
        self.ask_for_news_analysis = get_llm_direct_ask(
            llm=get_llm("paoluz", "gemini-2.5-flash"),
            system_prompt=dedent(
            f"""
            你是一位专业的金融新闻分析师，擅长为特定投资标的分析金融市场新闻信息。

            **分析重点：**
            1. **影响程度分级**: 将新闻按对{self.symbol}的影响程度分为：重大影响、中等影响、轻微影响、无影响
            2. **时效性分析**: 区分短期影响(1-24小时)、中期影响(1-7天)、长期影响(1个月以上)
            3. **黑天鹅识别**: 特别关注可能引起剧烈波动的突发事件

            **报告要求：**
            - 使用中文撰写，结构清晰
            - 按影响程度排序新闻事件
            - 明确标注是否存在黑天鹅事件
            - 给出市场情绪评分(1-10，1为极度恐慌，10为极度乐观)
            - 提供具体的短期价格影响预测(涨跌幅度范围)

            **输出格式：**
            1. 新闻摘要(按影响程度分级)
            2. 黑天鹅事件预警(如有)
            3. 市场情绪评估
            4. 短期影响预测
            5. 投资建议

            请始终保持专业和客观的态度，基于事实进行分析。                 
            """
            )
        )
        self.operation_advice_ask = get_llm_direct_ask(
            llm=get_llm("paoluz", "gemini-2.5-flash"),
            system_prompt=dedent(
            f"""
            你是一位专业的加密货币交易顾问，根据技术分析和新闻分析提供精确的交易建议。

            ## 决策框架
            1. **信号权重**: 技术分析70%，新闻分析30%
            2. **风险控制**: 必须考虑止盈止损设置
            3. **仓位管理**: 根据信号强度决定仓位大小
            4. **时机选择**: 明确入场和出场时机

            ## 输出要求
            1. **明确方向建议**:
                - 强烈做多/做多/观望/做空/强烈做空
                - 信号强度评分(1-10分)
                - 建议仓位比例(如：满仓、7成仓、5成仓、轻仓)
            
            2. **仓位操作建议**:
                - 如已有仓位：加仓/减仓/平仓的具体比例
                - 如无仓位：建议开仓比例和分批策略
            
            3. **风险管理**:
                - 止盈位设置(具体价格区间)
                - 止损位设置(具体价格区间)
                - 最大可承受亏损比例
            
            4. **时间预测**:
                - 接下来1小时价格波动区间
                - 关键观察时间点
                - 信号失效的条件
            
            5. **操作优先级**:
                - 立即执行/等待确认/观望等待
                - 市价单/限价单建议
            
            ## 输出格式
            使用以下结构化格式：
            
            ### 交易信号
            - **方向**: [强烈做多/做多/观望/做空/强烈做空]
            - **信号强度**: [X/10分]
            - **建议仓位**: [具体比例]
            
            ### 具体操作
            - **当前仓位处理**: [具体操作]
            - **新仓建议**: [具体建议]
            - **执行方式**: [市价/限价，具体价格]
            
            ### 风险管理
            - **止盈**: [价格区间]
            - **止损**: [价格区间]
            - **最大风险**: [百分比]
            
            ### 时间预测
            - **1小时目标区间**: [价格范围]
            - **关键时点**: [具体时间]
            
            严格基于技术分析和新闻分析内容，避免主观臆断。
            """
            )
        )
        self.operation_proposal_ask = get_llm_direct_ask(
            llm=get_llm("paoluz", "gemini-2.5-flash"),
            system_prompt=dedent(
            f"""
            你是交易执行专家，根据操作建议和当前仓位制定具体可执行的操作方案。

            ## 分析步骤
            1. **现状分析**: 详细分析当前仓位、挂单、风险状况
            2. **目标确定**: 根据操作建议确定目标仓位状态
            3. **路径规划**: 制定从现状到目标的具体执行步骤
            4. **风险评估**: 评估每个操作的风险和可能结果

            ## 输出格式
            ### 1. 现状分析
            - 当前仓位状况总结
            - 未完成订单分析
            - 风险敞口评估

            ### 2. 操作目标
            - 目标仓位方向和大小
            - 目标杠杆倍数
            - 目标止盈止损设置

            ### 3. 执行计划（按顺序）
            **步骤1**: [具体操作]
            - 操作类型: [取消订单/调整杠杆/开仓/平仓/设置止损止盈]
            - 具体参数: [订单类型、价格、数量等]
            - 执行理由: [为什么这样操作]
            - 风险提示: [可能的风险]

            **步骤2**: [下一步操作]
            ...

            ### 4. 风险控制
            - 最大亏损预估
            - 紧急处理预案
            - 执行过程监控要点

            ### 5. 执行建议
            - 推荐执行时机
            - 订单类型选择理由
            - 需要人工确认的环节

            ## 重要约束
            1. 不能同时做多做空
            2. 操作顺序必须正确（先取消冲突订单，再执行新操作）
            3. 加仓数量不得超过“杠杆后余额最大可继续加仓开多/开空合约数量”
            4. 由于系统限制，加建仓限价单只能挂一个，不能分批挂多个在不同价位
            5. 止盈止损只能各设置一次
            6. 必须考虑限价单可能不成交的情况
            7. 每个操作都要有明确的风险评估

            请确保方案具体可执行，避免模糊指令。
            """
            )
        )
        self.operation_agent = get_agent(
            llm=get_llm("paoluz", "gemini-2.5-pro")
        )
        self.operation_agent.set_system_prompt(
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

        self.operation_agent.register_tool(self.cancel_order)
        self.operation_agent.register_tool(self.close_current_position)
        self.operation_agent.register_tool(self.set_position_stop_price)
        self.operation_agent.register_tool(self.set_leverage)
        self.operation_agent.register_tool(self.open_new_position)
        self.operation_agent.register_tool(self.increase_current_position)
        self.operation_agent.register_tool(self.decrease_current_position)
        
        plan_id = f"crypto_agent_{self.symbol}_{investment}"
        self.position_status = None
        self.state = PersisitentState(plan_id, {
            "free_balance": investment, # 可用余额
            "position_avg_price": 0, # 开仓均价
            "limit_order_suspended_balance": 0, # 限价单开仓/加仓的挂单冻结
            # "short_sell_temporary_profit": 0, # 做空卖出暂时获得的钱
            "leverage": 5, # 杠杆倍数
            "position_amount": 0, # 仓位数量
            "position_side": "none", # 当前仓位方向, LONG-多仓，SHORT-空仓
            "recent_open_position_limit_order": None, # 开仓限价单对象
            "recent_add_position_limit_order": None,
            "recent_decrease_position_limit_order": None,
            "recent_take_profit_limit_order": None, # 止盈限价单对象
            "recent_stop_loss_limit_order": None, # 止损限价单对象
            "error_state": False
        })
        logger.info("当前状态: %s", json.dumps(self.state._simple_state._context, indent=2, ensure_ascii=False))

    @property
    def free_balance(self):
        return self.state.get("free_balance")

    @property
    def position_avg_price(self):
        return self.state.get("position_avg_price")
    
    @property
    def position_side(self):
        return self.state.get("position_side")

    @property
    def leverage(self):
        return self.state.get("leverage")

    @property
    def position_amount(self):
        return self.state.get("position_amount")
    
    def _create_limit_order(self, price: float, amount: float, trade_side: str) -> Dict[str, str]:

        order = self.binance.binance.create_order(
            symbol=self.symbol,
            type="limit",
            side=trade_side,
            amount=amount,
            price=price
        )

        return order["info"]

    def _create_market_order(self, amount: float, trade_side: str) -> Dict[str, str]:
        order = self.binance.binance.create_order(
            symbol=self.symbol,
            type="market",
            side=trade_side,
            amount=amount
        )
        logger.debug(f"created market order: {order}")
        return order["info"]

    def close_current_position(
            self,
            # order_type: Annotated[
            #     Literal["market", "limit"], 
            #     "订单类型, 市价单(market), 限价单(limit)"
            # ],
        ) -> dict:
        """
        立即使用市价单平掉当前仓位。限价平仓应该使用仓位止盈止损。
        """
        
        trade_side = "sell" if self.position_side == "long" else "buy"
        order = self._create_market_order(self.position_amount, trade_side)
        self._handling_position_state_change_for_resolved_order(order, "close_position")

        if self.state.has("recent_open_position_limit_order"):
            self.message_express.msg("检测到有未完成的开仓限价单，不应该执行这个操作")
            self._mark_error_state_and_exit()

        # 仓位没了，所有这些状态有的话都要清除，无意义
        for key in [
            "recent_add_position_limit_order", 
            "recent_decrease_position_limit_order", 
            "recent_take_profit_limit_order", 
            "recent_stop_loss_limit_order"
        ]:
            if self.state.has(key):
                self.message_express.msg("[WARN] 检测到有未完成的限价单, 没有先取消它们就关仓")
                self.cancel_order(self.state.get([key, 'orderId']))

        return order

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
        if self.position_side != "none" and self.position_amount != 0:
            return { "error": "当前已有仓位，请先平掉当前仓位" }
            
        self.state.set("position_side", position_side)
        result = {}
        if order_type == "limit":
            result = self._create_limit_order(price, amount, trade_side)
            if result['status'] == 'close':
                self._handling_position_state_change_for_resolved_order(result, "open_position")
            else:
                self.state.set("recent_open_position_limit_order", result)
                self._handling_position_state_change_for_new_limit_order(result, "open_position")
        else:
            result = self._create_market_order(amount, trade_side)
            self._handling_position_state_change_for_resolved_order(result, "open_position")

        return result
    
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
        trade_side = "buy" if self.position_side == "long" else "sell"
        result = {}
        if order_type == "limit":
            if self.state.has("recent_add_position_limit_order"):
                return { "error": "由于系统限制，当前已有未完成的加仓限价单，不能再挂新加仓的限价单" }
            result = self._create_limit_order(price, amount, trade_side)
            if result['status'] == 'close':
                self._handling_position_state_change_for_resolved_order(result, "add_position")
            else:
                self.state.set("recent_add_position_limit_order", result)
                self._handling_position_state_change_for_new_limit_order(result, "add_position")
        else:
            result = self._create_market_order(amount, trade_side)
            self._handling_position_state_change_for_resolved_order(result, "add_position")
        return result
    
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
        trade_side = "sell" if self.position_side == "long" else "buy"
        result = {}
        if order_type == "limit":
            if self.state.has("recent_decrease_position_limit_order"):
                return { "error": "由于系统限制，当前已有未完成的减仓限价单，不能再挂新减仓的限价单" }

            result = self._create_limit_order(price, amount, trade_side)
            if result['status'] == 'close':
                self._handling_position_state_change_for_resolved_order(result, "decrease_position")
            else:
                self.state.set("recent_decrease_position_limit_order", result)
                self._handling_position_state_change_for_new_limit_order(result, "decrease_position")
        else:
            result = self._create_market_order(amount, trade_side)
            self._handling_position_state_change_for_resolved_order(result, "decrease_position")
        return result

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
        if take_profit and stop_loss:
            if self.position_side == "long" and take_profit <= stop_loss:
                return { "error": "当前做多，止盈价格不能小于止损价格" }
            if self.position_side == "short" and take_profit >= stop_loss:
                return { "error": "当前做空，止盈价格不能大于止损价格" }
        
        result = {}
        if take_profit:
            # 可能存在未完成的止盈单
            curr_take_profit = self.state.get(["recent_take_profit_limit_order", "stopPrice"])

            if curr_take_profit and float(curr_take_profit) != take_profit:
                self.message_express.msg("[WARN] 检测到有未完成的冲突止盈单, 先取消它")
                self.cancel_order(self.state.get(["recent_take_profit_limit_order", "orderId"]))
            
            if not curr_take_profit or float(curr_take_profit) != take_profit:
                order = self.binance.binance.create_order(
                    symbol=self.symbol,
                    type="TAKE_PROFIT_MARKET",
                    side="buy" if self.position_side == "short" else "sell",
                    amount=self.position_amount,
                    params = {
                        "closePosition": True,
                        "stopPrice": take_profit
                    }
                )
                result["take_profit"] = order["info"]
                self._handling_position_state_change_for_new_limit_order(order["info"], "take_profit")
                self.state.set("recent_take_profit_limit_order", order["info"])
            
            if curr_take_profit and float(curr_take_profit) == take_profit:
                self.message_express.msg(f"[INFO] 当前已有止盈单，价格为 {take_profit}，不需要重新设置")
                result["take_profit"] = { "error": "新设置的止盈价格和当前未完成的止盈单价格相同，请勿重复设置" }

        if stop_loss:
            curr_stop_loss = self.state.get(["recent_stop_loss_limit_order", "stopPrice"])
            if curr_stop_loss and float(curr_stop_loss) != stop_loss:
                # 可能存在未完成的止损单
                self.message_express.msg("[WARN] 检测到有未完成的冲突止损单, 先取消它")
                self.cancel_order(self.state.get(["recent_stop_loss_limit_order", "orderId"]))

            if not curr_stop_loss or float(curr_stop_loss) != stop_loss:
                order = self.binance.binance.create_order(
                    symbol=self.symbol,
                    type="STOP_MARKET",
                    side="buy" if self.position_side == "short" else "sell",
                    amount=self.position_amount,
                    params = {
                        "closePosition": True,
                        "stopPrice": stop_loss
                    }
                )
                result["stop_loss"] = order["info"]
                self._handling_position_state_change_for_new_limit_order(order["info"], "stop_loss")
                self.state.set("recent_stop_loss_limit_order", order["info"])

            if curr_stop_loss and float(curr_stop_loss) == stop_loss:
                self.message_express.msg(f"[INFO] 当前已有止损单，价格为 {stop_loss}，不需要重新设置")
                result["stop_loss"] = { "error": "新设置的止损价格和当前未完成的止损单价格相同，请勿重复设置" }

        return result

    def _mark_error_state_and_exit(self):
        self.state.set("error_state", True)
        exit(1)

    def _handling_position_state_change_for_new_limit_order(self, order: dict, order_source: str):
        """
        处理新限价单引发的仓位状态变化(剩余可用、锁定金额、仓位方向) ，不涉及recent_xxx_order
        限价单FILLED前不会影响仓位数量、仓位均价
        """

        order_side = order['side'].lower()
        assert order["status"] != "FILLED"

        if order_source == "open_position":
            if order_side == "buy":
                to_be_locked_balance = float(order['origQty']) * float(order['price']) / self.leverage
                self.state.decrease("free_balance", to_be_locked_balance)
                self.state.set("limit_order_suspended_balance", to_be_locked_balance)
                self.state.set("position_side", "long")
            elif order_side == "sell":
                to_be_locked_balance = float(order['origQty']) * float(order['price']) / self.leverage
                self.state.decrease("free_balance", to_be_locked_balance)
                self.state.set("limit_order_suspended_balance", to_be_locked_balance)
                self.state.set("position_side", "short")
            else:
                self.message_express.msg(f"[ERROR] Unknown order side {order_side} for open position order {order}")
                self._mark_error_state_and_exit()
        
        if order_source == "add_position":
            if order_side == "buy" and self.position_side == "long":
                to_be_locked_balance = float(order['origQty']) * float(order['price']) / self.leverage
                self.state.decrease("free_balance", to_be_locked_balance)
                self.state.increase("limit_order_suspended_balance", to_be_locked_balance)
            elif order_side == "sell" and self.position_side == "short":
                to_be_locked_balance = float(order['origQty']) * float(order['price']) / self.leverage
                self.state.decrease("free_balance", to_be_locked_balance)
                self.state.increase("limit_order_suspended_balance", to_be_locked_balance)
            else:
                self.message_express.msg(f"[ERROR] Unknown order side {order_side} for add position order {order}")
                self._mark_error_state_and_exit()

        if order_source == "decrease_position":
            # 减仓不改变可用，也不锁钱，包括止盈止损也是一样的
            pass


    def _handling_position_state_change_for_resolved_order(self, order: dict, order_source: str):
        """
        处理已完成订单引发的仓位状态变化(剩余可用、仓位总数、仓位均价、开仓加仓锁定金额、仓位方向等) ，不涉及recent_xxx_order
        """
        def _reset_state_for_close_position():
            self.state.set("position_amount", 0)
            self.state.set("position_avg_price", 0)
            self.state.set("position_side", "none")

        order_side = order['side'].lower()
        assert order["status"] == "FILLED"
        if order_source == "open_position":
            if order_side == "buy" and self.position_side == "long":
                if order['type'] == "LIMIT":
                    self.message_express.msg(f"限价开多成功: {order}")
                    self.state.set("limit_order_suspended_balance", 0)
                else:
                    self.message_express.msg(f"市价开多成功: {order}")
                    self.state.decrease("free_balance", float(order['cumQuote']) / self.leverage)
                self.state.set("position_amount", float(order['executedQty']))
                self.state.set("position_avg_price", float(order['avgPrice']))
                self.state.set("position_side", "long")
            elif order_side == "sell" and self.position_side == "short":
                if order['type'] == "LIMIT":
                    self.message_express.msg(f"限价开空成功: {order}")
                    self.state.set("limit_order_suspended_balance", 0)
                else:
                    self.message_express.msg(f"市价开空成功: {order}")
                    self.state.decrease("free_balance", float(order['cumQuote']) / self.leverage)
                self.state.set("position_avg_price", float(order['avgPrice']))
                self.state.set("position_amount", float(order['executedQty']))
                self.state.set("position_side", "short")
            else:
                self.message_express.msg(f"[ERROR] Unknown order side {order_side} for open position order {order}")
                self._mark_error_state_and_exit()
        
        if order_source == "add_position":
            if order_side == "buy" and self.position_side == "long":
                if order['type'] == "LIMIT":
                    self.message_express.msg(f"限价买入加多成功: {order}")
                    self.state.set("limit_order_suspended_balance", 0)
                else:
                    self.message_express.msg(f"市价买入加多成功: {order}")
                    self.state.decrease("free_balance", float(order['cumQuote']) / self.leverage)
                self.state.set(
                    "position_avg_price", 
                    cal_avg_price(
                        float(order['avgPrice']), float(order['executedQty']),
                        self.position_avg_price, self.position_amount
                    )
                )
                self.state.increase("position_amount", float(order['executedQty']))
            elif order_side == "sell" and self.position_side == "short":
                if order['type'] == "LIMIT":
                    self.message_express.msg(f"限价卖出加空成功: {order}")
                    self.state.set("limit_order_suspended_balance", 0)
                else:
                    self.message_express.msg(f"市价卖出加空成功: {order}")
                    self.state.decrease("free_balance", float(order['cumQuote']) / self.leverage)
                self.state.set(
                    "position_avg_price", 
                    cal_avg_price(
                        float(order['avgPrice']), float(order['executedQty']),
                        self.position_avg_price, self.position_amount
                    )
                )
                self.state.increase("position_amount", float(order['executedQty']))
            else:
                self.message_express.msg(f"[ERROR] Unknown order side {order_side} for add position order {order}")
                self._mark_error_state_and_exit()

        if order_source == "decrease_position":
            # 减仓不改变仓位均价
            if order_side == "sell" and self.position_side == "long":
                if order['type'] == "LIMIT":
                    self.message_express.msg(f"限价卖出减多成功: {order}")

                self.state.increase("free_balance", float(order['cumQuote']) / self.leverage)
                self.state.decrease("position_amount", float(order['executedQty']))

            elif order_side == "buy" and self.position_side == "short":
                if order['type'] == "LIMIT":
                    self.message_express.msg(f"限价买入减空成功: {order}")
                
                # 赎回的本金
                self.state.increase("free_balance", self.position_avg_price * float(order['executedQty']) / self.leverage)
                # 赚取利润
                self.state.increase("free_balance", (self.position_avg_price - float(order['avgPrice'])) * float(order['executedQty']))
                self.state.decrease("position_amount", float(order['executedQty']))
            else:
                self.message_express.msg(f"[ERROR] Unknown order side {order_side} for decrease position order {order}")
                self._mark_error_state_and_exit()

        if order_source == "take_profit" or order_source == "stop_loss" or order_source == "close_position":
            self.message_express.msg(f"仓位{'止盈' if order_source == 'take_profit' else '止损' if order_source == 'stop_loss' else '平仓'}订单已完成: {order}")

            if self.state.get("position_side") == "short" and order_side == "buy":
                # 收回的本金
                self.state.increase("free_balance", self.position_avg_price * float(order['executedQty']) / self.leverage)
                # 赚取利润
                profit = (self.position_avg_price - float(order['avgPrice'])) * float(order['executedQty'])
                self.state.increase("free_balance", profit)
                _reset_state_for_close_position()
                self.message_express.msg(f"仓位平空，获利：{profit}")

            elif self.state.get("position_side") == "long" and order_side == "sell":
                # 收回的本金
                self.state.increase("free_balance", float(order['cumQuote']) / self.leverage)
                _reset_state_for_close_position()
            else:
                self.message_express.msg(f"[ERROR] Unknown order side {order_side} for take profit/stop lossorder {order}")
                self._mark_error_state_and_exit()
                
    def _handle_state_change_for_pending_order(self, order_source: str):
        order_key = f"recent_{order_source}_limit_order"
        order_id = self.state.get([order_key, 'orderId'])
        if order_id:
            order = self.get_order(order_id)
            if order['status'] in ['FILLED', 'CANCELED', 'EXPIRED']:
                self.state.delete(order_key)

            if order['status'] == 'FILLED':
                self._handling_position_state_change_for_resolved_order(order, order_source)
                if order_source == "take_profit":
                    order_to_be_canceled = self.state.get(["recent_stop_loss_limit_order", "orderId"])
                    if order_to_be_canceled:
                        canceled_paired_stop_loss_order = self.cancel_order(order_to_be_canceled)
                        self.message_express.msg(f"止盈后取消止损订单: {canceled_paired_stop_loss_order}")
                elif order_source == "stop_loss":
                    order_to_be_canceled = self.state.get(["recent_take_profit_limit_order", "orderId"])
                    if order_to_be_canceled:
                        canceled_paired_take_profit_order = self.cancel_order(order_to_be_canceled)
                        self.message_express.msg(f"止损后取消止盈订单: {canceled_paired_take_profit_order}")
            
            if order['status'] in ['CANCELED', 'EXPIRED']:
                self.message_express.msg(f"限价单已取消或过期: {order}")
                if order_source == "open_position" or order_source == "add_position":
                    self.message_express.msg(f"锁定金额归零，恢复可用余额: {order}")
                    self.state.increase("free_balance", self.state.get("limit_order_suspended_balance"))
                    self.state.set("limit_order_suspended_balance", 0)

    def handle_state_change_for_pending_limit_orders(self):
        self._handle_state_change_for_pending_order("open_position")
        self._handle_state_change_for_pending_order("add_position")
        self._handle_state_change_for_pending_order("decrease_position")
        self._handle_state_change_for_pending_order("take_profit")
        self._handle_state_change_for_pending_order("stop_loss")

    def _get_cache(self, key: str) -> tuple[bool, str]:
        with create_transaction() as db:
            result = db.kv_store.get(key)
            if result:
                return True, result
            return False, None
        
    def _set_cache_and_return(self, key: str, value: str) -> str:
        with create_transaction() as db:
            db.kv_store.set(key, value)
            db.commit()
            return value

    def get_operation_proposal(self) -> str:
        cache_key = f"crypto_operation_proposal_{self.symbol}_{datetime.now().strftime('%Y-%m-%d_%H:00')}"
        cache_exist, value = self._get_cache(cache_key)
        if cache_exist:
            return value
        
        current_position_info_str = self.get_position_info()
        self.message_express.msg(current_position_info_str)
        operation_advice = self.get_operation_advice()
        self.message_express.msg(operation_advice)
        
        prompt = "请根据以下信息给出操作方案：\n"
        prompt += f"当前仓位信息：\n {indent(current_position_info_str, ' ' * 2)}\n"
        prompt += f"当前操作建议：\n {indent(operation_advice, ' ' * 2)}\n"
        return self._set_cache_and_return(
            cache_key,
            self.operation_proposal_ask(prompt)
        )

    def get_operation_advice(self) -> str:
        """
        多agent对未来1小时涨跌进行辩论，最后给出建议。
        """
        cache_key = f"crypto_operation_advice_{self.symbol}_{datetime.now().strftime('%Y-%m-%d_%H:00')}"
        cache_exist, cache_value = self._get_cache(cache_key)
        if cache_exist:
            return cache_value
        
        news_report = None
        technical_report = None

        def fetch_news():
            nonlocal news_report
            news_report = self.get_news_analysis_report(from_time=(datetime.now() - timedelta(minutes=30)).replace(minute=0, second=0, microsecond=0))

        def fetch_technical():
            nonlocal technical_report
            technical_report = self.get_technical_analysis_report()

        t1 = threading.Thread(target=fetch_news)
        t2 = threading.Thread(target=fetch_technical)
        t1.start()
        t1.join()
        t2.start()
        t2.join()
        
        assert news_report is not None, "新闻分析报告不能为空"
        assert technical_report is not None, "技术分析报告不能为空"

        self.message_express.msg(news_report)
        self.message_express.msg(technical_report)

        curr_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        curr_price = self.binance.fetch_ticker(self.symbol).last

        prompt = f"新闻分析:\n{news_report}\n\n技术分析:\n{technical_report}\n"
        prompt += f"当前时间: {curr_time}\n"
        prompt += f"当前价格: {curr_price}\n\n"
        prompt += "请根据以上信息，预测未来一小时涨跌并给出操作建议"

        return self._set_cache_and_return(cache_key, self.operation_advice_ask(prompt))
    
    # @use_cache(3600, use_db_cache=True, key_generator=lambda args, _: f"{args['symbol']}_{str(args["from_time"])}")
    def get_news_analysis_report(self, from_time: datetime) -> str:
        """
        获取新闻分析报告。
        参数：
            from_time: 分析的起始时间
        返回：新闻分析报告字符串
        """
        cache_key = f"crypto_news_analysis_{self.symbol}_{from_time.strftime('%Y-%m-%d_%H:00')}"
        cache_exist, cache_value = self._get_cache(cache_key)
        if cache_exist:
            return cache_value

        coin_time = news_proxy.get_news_from("cointime", start=from_time)
        if len(coin_time) == 0:
            return "过去一小时无需要关注的新闻"
        news_in_str = render_news_in_markdown_group_by_platform({
            "cointime": coin_time
        })
        prompt = f"请分析以下从{from_time}开始的新闻，会不会对投资标的{self.symbol}产生影响？\n{news_in_str}"
        logger.debug(prompt)
        return self._set_cache_and_return(cache_key, self.ask_for_news_analysis(prompt))

    def get_technical_analysis_report(self) -> str:
        # 为了使用上缓存，使用现货的symbol代替合约的symbol
        # assert interval in ['1d', '1h', '15m'], "不支持的时间周期"
        symbol = self.symbol.rstrip("USDT").rstrip("/") + '/USDT'
        curr_time = datetime.now().strftime('%Y-%m-%d_%H:00')
        cache_key = f"crypto_news_analysis_{self.symbol}_1h_48_{curr_time}"
        cache_exist, cache_value = self._get_cache(cache_key)
        if cache_exist:
            return cache_value
            
        data = crypto.get_ohlcv_history(
            symbol=symbol,
            frame="1h",
            limit=48
        ).data

        user_prompt = f"请分析以下{self.symbol}的小时级别OHLCV数据\n"
        user_prompt += f"过去{len(data)}小时级别OHLCV数据如下:\n\n"
        user_prompt += format_ohlcv_list(data)
        ohlcv_patterns = format_ohlcv_pattern(data)
        if ohlcv_patterns:
            user_prompt += "\n\n检测到的K线形态：\n" + ohlcv_patterns
        user_prompt += "\n\n技术指标：\n" + format_indicators(data, ["sma", "macd", "rsi", "boll", "atr"], 20, "1h")

        user_prompt += "\n\n以下是过去4小时15min级别的OHLCV数据， 用于更精确的短期趋势分析。"
        data = crypto.get_ohlcv_history(
            symbol=symbol,
            frame="15m",
            limit=16
        ).data
        user_prompt += format_ohlcv_list(data)

        # user_prompt += "\n\n以下是过去1小时5min级别的OHLCV数据， 用于更精确的短期趋势分析。"
        # data = crypto.get_ohlcv_history(
        #     symbol=symbol,
        #     frame="5m",
        #     limit=12
        # ).data
        # user_prompt += format_ohlcv_list(data)

        user_prompt += f"\n\n请分析以上数据，对未来1小时的行情预测。"

        logger.debug(user_prompt)

        return self._set_cache_and_return(cache_key, self.ask_for_technical_analysis(user_prompt))

    def get_order(self, order_id: str) -> Dict[str, str]:
        raw_order = self.binance.binance.fetch_order(**{ 'symbol': self.symbol, 'id': order_id })['info']
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
        logger.debug(f"获取订单信息: {json.dumps(raw_order, indent=2)}")
        return {
            'orderId': raw_order['orderId'],
            'status': raw_order['status'],
            "price": raw_order["price"],
            "type": raw_order['type'],
            "side": raw_order['side'],
            "positionSide": raw_order['positionSide'],
            "origQty": float(raw_order['origQty']),
            'avgPrice': float(raw_order['avgPrice']),
            "cumQty": float(raw_order.get('cumQty', 0)) if raw_order.get('cumQty', 0) else None, # 订单resolve后没有
            'executedQty': float(raw_order['executedQty']),
            'cumQuote': float(raw_order['cumQuote']),
            'reduceOnly': bool(raw_order['reduceOnly']),
            'closePosition': bool(raw_order['closePosition']),
            'stopPrice': float(raw_order['stopPrice']),
            'updateTime': int(raw_order['updateTime'])
        }

    def set_leverage(self, leverage: Annotated[int, "杠杆倍率"]) -> Dict[str, str]:
        """
        设置杠杆倍率
        """
        result = self.binance.binance.fapiPrivatePostLeverage({ 'symbol': self.symbol, 'leverage': leverage })
        self.state.set("leverage", leverage)
        return result

    def cancel_order(self, order_id: Annotated[str, "订单ID"]) -> Dict[str, str]:
        """
        取消订单。
        参数：
            order_id: 订单ID
        返回：取消结果信息。
        """

        result = self.binance.binance.cancel_order(symbol=self.symbol, id=order_id)
        for order_id_key in [
            "recent_add_position_limit_order",
            "recent_decrease_position_limit_order",
            "recent_open_position_limit_order", 
            "recent_take_profit_limit_order", 
            "recent_stop_loss_limit_order"
        ]:
            if order_id == self.state.get([order_id_key, 'orderId']):
                self.state.delete(order_id_key)
                if order_id_key in ["recent_add_position_limit_order", "recent_open_position_limit_order"]:
                    self.state.increase("free_balance", self.state.get("limit_order_suspended_balance"))
                    self.state.set("limit_order_suspended_balance", 0)
        return result['info']

    def get_position_info(self) -> str:
        """
        获取当前仓位信息，包括杠杆倍率、仓位水平等。
        返回：仓位信息结构体或字典。
        """
        rsp = self.binance.binance.fapiPrivateV2GetPositionRisk(params={ 'symbol': self.symbol })
        """
        [
            {
                "symbol": "SUIUSDT",                # 交易对名称
                "positionAmt": "-16.0",             # 持仓数量（正为多，负为空）
                "entryPrice": "4.2101",             # 开仓均价
                "breakEvenPrice": "4.20799495",     # 盈亏平衡价格
                "markPrice": "4.20890000",          # 当前标记价格
                "unRealizedProfit": "0.01920000",   # 未实现盈亏
                "liquidationPrice": "7.26039104",   # 强平价格
                "leverage": "5",                    # 杠杆倍数
                "maxNotionalValue": "20000000",     # 最大名义价值
                "marginType": "cross",              # 保证金模式（全仓/逐仓）
                "isolatedMargin": "0.00000000",     # 逐仓保证金数量
                "isAutoAddMargin": "false",         # 是否自动追加保证金
                "positionSide": "BOTH",             # 仓位方向（BOTH/SHORT/LONG）
                "notional": "-67.34240000",         # 持仓名义价值
                "isolatedWallet": "0",              # 逐仓钱包余额
                "updateTime": "1753602954123",      # 更新时间（时间戳）
                "isolated": false,                  # 是否逐仓
                "adlQuantile": "3"                  # ADL分位数
            }
        ]
        """
        # 只支持双向持仓模式
        info = next((item for item in rsp if item.get('positionSide', '').upper() == 'BOTH'), None)
        logger.debug(f"获取仓位信息: {json.dumps(info, indent=2)}")
        if not info:
            self.message_express.msg("[ERROR] 当前没有仓位信息，可能是未开仓或已平仓。")
            self._mark_error_state_and_exit()
        else:
            leverage = int(info.get('leverage', 5))
            position_amount = float(info.get('positionAmt', 0))

            self.state.set("position_amount", abs(position_amount))
            self.state.set("position_side", "long" if position_amount > 0 else "short" if position_amount < 0 else "none")
            self.state.set("position_avg_price", float(info.get('entryPrice', 0)))
            self.state.set("leverage", leverage)

        free_balance = self.state.get('free_balance')

        curr_price = float(info['markPrice'])

        position_info_str = ""
        recent_open_position_limit_order = self.state.get("recent_open_position_limit_order")
        recent_add_position_limit_order = self.state.get("recent_add_position_limit_order")
        recent_decrease_position_limit_order = self.state.get("recent_decrease_position_limit_order")
        recent_take_profit_limit_order = self.state.get("recent_take_profit_limit_order")
        recent_stop_loss_limit_order = self.state.get("recent_stop_loss_limit_order")

        if self.position_side == "none":
            position_info_str = (
                f"当前没有持仓。\n"
                f"当前杠杆倍数: {leverage}\n"
                f"可用: {free_balance}USDT\n"
                f"杠杆后余额: {free_balance * leverage:2f}USDT\n"
                f"当前标记价格: {curr_price}\n"
                f"杠杆后余额最大可开多/开空合约数量: {free_balance * leverage / curr_price:2f}\n"
            )
            if recent_open_position_limit_order:
                position_info_str += (
                    f"当前有未完成开仓限价单: {recent_open_position_limit_order['orderId']}\n"
                    f"限价单价格: {recent_open_position_limit_order['price']}\n"
                    f"限价单委托数量: {recent_open_position_limit_order['origQty']}\n"
                    f"限价单状态: {recent_open_position_limit_order['status']}\n"
                    f"限价单方向: {'做空' if recent_open_position_limit_order['side'] == 'SELL' else '做多'}\n"
                )
            return position_info_str
        

        position_info_str = (
            f"持仓数量: {self.position_amount}\n"
            f"仓位方向：{'做多' if self.position_side == 'long' else '做空' if self.position_side == 'short' else '无'}\n"
            f"仓位水平: {self.position_amount * self.position_avg_price / (self.position_amount * self.position_avg_price + self.free_balance * self.leverage):.2%}\n"
            f"开仓均价: {self.position_avg_price}\n"
            f"盈亏平衡价格: {info.get('breakEvenPrice', '')}\n"
            f"当前标记价格: {curr_price}\n"
            f"未实现盈亏: {info.get('unRealizedProfit', '')}\n"
            f"强平价格: {info.get('liquidationPrice', '')}\n"
            f"当前杠杆倍数: {leverage}\n"
            f"持仓名义价值: {info.get('notional', '')}\n"
            f"当前可用: {self.free_balance:2f}USDT\n"
            f"杠杆后余额: {self.free_balance * leverage:2f}USDT\n"
            f"杠杆后余额最大可继续加仓{'开多' if position_amount > 0 else '开空'}合约数量: {self.free_balance * leverage / curr_price:2f}\n"
            f"最大可反向{'开多' if position_amount < 0 else '开空'}合约数量: {self.free_balance * leverage / curr_price + self.position_amount:2f}\n"
        )
        if recent_add_position_limit_order:
            position_info_str += (
                f"当前有未完成加仓限价单: {recent_add_position_limit_order['orderId']}\n"
                f"限价单价格: {recent_add_position_limit_order['price']}\n"
                f"限价单委托数量: {recent_add_position_limit_order['origQty']}\n"
                f"限价单状态: {recent_add_position_limit_order['status']}\n"
                f"限价单方向: {'做多' if recent_add_position_limit_order['side'] == 'BUY' else '做空'}\n"
            )
        if recent_add_position_limit_order:
            position_info_str += (
                f"当前有未完成加仓限价单: {recent_add_position_limit_order['orderId']}\n"
                f"限价单价格: {recent_add_position_limit_order['price']}\n"
            )
        if recent_decrease_position_limit_order:
            position_info_str += (
                f"当前有未完成减仓限价单: {recent_decrease_position_limit_order['orderId']}\n"
                f"限价单价格: {recent_decrease_position_limit_order['price']}\n"
            )
        if recent_take_profit_limit_order:
            position_info_str += (
                f"当前有未完成止盈平仓限价单({recent_take_profit_limit_order['side']}): {recent_take_profit_limit_order['orderId']}\n"
                f"当前止盈价格: {recent_take_profit_limit_order['stopPrice']}\n"
            )
        else:
            position_info_str += (
                "当前没有设置止盈。\n"
            )
        if recent_stop_loss_limit_order:
            position_info_str += (
                f"当前有未完成止损平仓限价单({recent_stop_loss_limit_order['side']}): {recent_stop_loss_limit_order['orderId']}\n"
                f"当前止损限价格: {recent_stop_loss_limit_order['stopPrice']}\n"
            )
        else:
            position_info_str += (
                "当前没有设置止损。\n"
            )
        position_info_str += f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        return position_info_str

    def run(self):
        try:
            self.handle_state_change_for_pending_limit_orders()
            proposal = self.get_operation_proposal()
            self.message_express.msg(proposal)
            operation_result = self.operation_agent.ask(proposal, tool_use=True)
            self.message_express.msg(operation_result)
            self.state.save()
        except Exception as e:
            self.message_express.msg(f"运行过程中发生错误: {str(e)}")
        finally:
            self.message_express.send()


@app.command()
def main():
    """
    运行加密货币智能仓位管理Agent。
    """
    try:
        agent = CryptoAgent(
            symbol="SUIUSDT",
            investment=50,  # 初始投资金额
        )
        # agent.message_express.msg(agent.get_position_info())
        # agent.message_express.msg(agent.get_news_analysis_report(datetime.now() - timedelta(minutes=55)))
        # agent.message_express.msg(agent.get_technical_analysis_report())
        # agent.message_express.msg(agent.get_operation_advice())
        # agent.message_express.msg(agent.get_operation_proposal())
        # agent.message_express.send()
        # print(agent.create_order(
        #     order_type="LIMIT",
        #     order_side="SELL",
        #     amount=15,
        #     # postion_side="BOTH",
        #     price=4.2509
        #     # stop_price=4.5,
        #     # reduce_only=True,
        #     # close_position=True
        # ))
        # print(agent.get_position_info())
        
        agent.run()
    except KeyboardInterrupt:
        print('Ctrl-C pressed – the request is still running in the daemon thread')
        exit(1)
    
    # print(agent.create_order(
    #     order_type="STOP_MARKET",
    #     order_side="BUY",
    #     # amount=15,
    #     # postion_side="BOTH",
    #     # price=4.2300,
    #     stop_price=4.5,
    #     # reduce_only=True,
    #     close_position=True
    # ))
    # print(agent.get_position_info())
    # print(
    #     json.dumps(
    #         agent.binance.binance.fapiPrivateGetOpenOrders({ "symbol": "SUIUSDT" }),
    #         indent=2
    #     )
    # )
    # [
    #     {
    #     "orderId": "29235756919",
    #     "symbol": "SUIUSDT",
    #     "status": "NEW",
    #     "clientOrderId": "android_KqG0DumNkfuNb3pce8pK",
    #     "price": "0",
    #     "avgPrice": "0",
    #     "origQty": "0",
    #     "executedQty": "0",
    #     "cumQuote": "0.0000000",
    #     "timeInForce": "GTE_GTC",
    #     "type": "TAKE_PROFIT_MARKET",
    #     "reduceOnly": true,
    #     "closePosition": true,
    #     "side": "SELL",
    #     "positionSide": "BOTH",
    #     "stopPrice": "4.339000",
    #     "workingType": "MARK_PRICE",
    #     "priceProtect": true,
    #     "origType": "TAKE_PROFIT_MARKET",
    #     "priceMatch": "NONE",
    #     "selfTradePreventionMode": "NONE",
    #     "goodTillDate": "0",
    #     "time": "1753634347888",
    #     "time": "1753634347888",
    #     "updateTime": "1753634347900"
    #     "updateTime": "1753634347900"
    #     },
    #     {
    #     "orderId": "29235756925",
    #     "orderId": "29235756925",
    #     "symbol": "SUIUSDT",
    #     "status": "NEW",
    #     "clientOrderId": "android_kGyqRg4vBDzKJgbtbUAN",
    #     "price": "0",
    #     "avgPrice": "0",
    #     "origQty": "0",
    #     "executedQty": "0",
    #     "cumQuote": "0.0000000",
    #     "timeInForce": "GTE_GTC",
    #     "type": "STOP_MARKET",
    #     "reduceOnly": true,
    #     "closePosition": true,
    #     "side": "SELL",
    #     "positionSide": "BOTH",
    #     "stopPrice": "4.210100",
    #     "workingType": "MARK_PRICE",
    #     "priceProtect": true,
    #     "origType": "STOP_MARKET",
    #     "priceMatch": "NONE",
    #     "selfTradePreventionMode": "NONE",
    #     "goodTillDate": "0",
    #     "time": "1753634347891",
    #     "updateTime": "1753634347902"
    #     }
    #     ]
    # acc = agent.binance.binance.fapiPrivateV2GetAccount()
    # print(acc)
    # print(acc['totalMaintMargin'])  # 0.64334970 维持保证金总额（所有持仓维持不被强平所需的最低保证金总和）
    # print(acc['totalWalletBalance'])  # 49.57185143 账户总余额（包括已实现盈亏，未实现盈亏未计入）
    # print(acc['totalUnrealizedProfit'])  # 0.05508000 所有持仓的未实现盈亏总和
    # print(acc['totalMarginBalance'])  # 49.62693143 保证金余额（= totalWalletBalance + totalUnrealizedProfit，实际可用来抵扣保证金的总额）
    # print(acc['totalPositionInitialMargin'])  # 12.86699400 所有持仓的初始保证金总额（开仓时冻结的保证金总和）
    # print(acc['totalOpenOrderInitialMargin'])  # 0.00000000 所有挂单的初始保证金总额（挂单冻结的保证金总和）
    # print(acc['totalCrossWalletBalance'])  # 49.57185143 全仓钱包余额（全仓模式下可用的总余额）
    # print(acc['totalCrossUnPnl'])  # 0.05508000 全仓未实现盈亏
    # print(acc['availableBalance'])  # 36.75993743 可用余额（可用于开新仓或提取的余额）
    # print(acc['maxWithdrawAmount'])  # 36.75993743 最大可提取金额（不影响当前持仓的情况下可提取的最大金额）
    
    # print(agent.create_order(
    #     order_type="LIMIT",
    #     order_side="BUY",
    #     amount=0.230,
    #     postion_side="LONG",
    #     price=39,
    #     stop_price=50

    # ))

if __name__ == "__main__":
    app()