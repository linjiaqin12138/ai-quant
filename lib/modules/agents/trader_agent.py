#!/usr/bin/env python3
"""
TraderAgent - 交易代理
基于BullBearResearcher报告进行交易决策的智能代理
"""

import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from textwrap import dedent


from lib.model.error import LlmReplyInvalid
from lib.adapter.database import create_transaction
from lib.adapter.llm import LlmAbstract, get_llm
from lib.logger import logger
from lib.modules.agent import get_agent
from lib.modules.trade.api import TradeOperations
from lib.modules.trade.ashare import AshareTrade
from lib.tools.investment_reflector import InvestmentReflector, ReflectionData
from lib.utils.string import extract_json_string


@dataclass
class TradeRecord:
    """交易记录"""
    date: datetime
    action: str  # BUY/SELL/HOLD
    price: float
    quantity: int  # 交易数量（手数）
    amount: float  # 交易金额
    available_funds: float  # 可用资金
    holding_quantity: int  # 持有数量
    reason: str  # 交易决策理由
    bull_bear_report: str  # 当时的牛熊研究报告
    
    @property
    def previous_available_funds(self) -> float:
        """获取交易前的可用资金"""
        if self.action == "BUY":
            return self.available_funds + self.amount
        if self.action == "SELL":
            return self.available_funds - self.amount
        return self.available_funds
        
    @property
    def previous_holding_quantity(self) -> int:
        """获取交易前的持有数量"""
        if self.action == "BUY":
            return self.holding_quantity - self.quantity
        if self.action == "SELL":
            return self.holding_quantity + self.quantity
        return self.holding_quantity

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TradeRecord':
        """从字典创建TradeRecord实例"""
        return cls(
            date=datetime.fromisoformat(data["date"]) if isinstance(data["date"], str) else data["date"],
            action=data["action"],
            price=data["price"],
            quantity=data["quantity"],
            amount=data["amount"],
            available_funds=data["available_funds"],
            holding_quantity=data["holding_quantity"],
            reason=data["reason"],
            bull_bear_report=data.get("bull_bear_report", "")
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "date": self.date.isoformat(),
            "action": self.action,
            "price": self.price,
            "quantity": self.quantity,
            "amount": self.amount,
            "available_funds": self.available_funds,
            "holding_quantity": self.holding_quantity,
            "reason": self.reason,
            "bull_bear_report": self.bull_bear_report
        }


@dataclass
class PortfolioStatus:
    """投资组合状态"""
    symbol: str
    available_funds: float  # 可用资金
    holding_quantity: int  # 持有数量（手数）
    current_price: float  # 当前价格
    
    @property
    def holding_val(self) -> float:
        """持有价值"""
        return self.holding_quantity * self.current_price * 100

    @property
    def total_value(self) -> float:
        """总价值"""
        return self.available_funds + self.holding_val
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PortfolioStatus':
        """从字典创建PortfolioStatus实例"""
        return cls(
            symbol=data["symbol"],
            available_funds=data["available_funds"],
            holding_quantity=data["holding_quantity"],
            current_price=data["current_price"]
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "symbol": self.symbol,
            "available_funds": self.available_funds,
            "holding_quantity": self.holding_quantity,
            "current_price": self.current_price
        }


class TraderAgent:
    """交易代理"""
    
    def __init__(
        self,
        symbol: str,
        initial_funds: float = 100000.0,
        llm: Optional[LlmAbstract] = None,
        reflector: Optional[InvestmentReflector] = None,
        reflect_top_k: int = 3
    ):
        """
        初始化交易代理
        
        Args:
            symbol: 交易标的
            initial_funds: 初始资金
            llm: LLM实例
            trade_operations: 交易操作接口
            reflector: 反思工具
            reflect_top_k: 反思时搜索的相似记录数量
        """
        self.symbol = symbol
        self.initial_funds = initial_funds
        self.llm = llm or get_llm('paoluz', 'deepseek-v3')
        self.reflect_top_k = reflect_top_k
        
        # 初始化交易操作接口
        self.trade_operations = AshareTrade()
        
        # 初始化反思工具
        self.reflector = reflector or InvestmentReflector(
            llm=self.llm,
            index_name=f"trader-reflections"
        )
        
        # 创建决策Agent
        self.decision_agent = get_agent(llm=self.llm)
        self._setup_decision_agent()
        
        # 数据库键名
        self.portfolio_key = f"trader_portfolio_{symbol}"
        self.history_key = f"trader_history_{symbol}"
        
        # 牛熊研究报告存储
        self.bull_bear_research_report = ""
        
        # 初始化投资组合状态
        self._initialize_portfolio()
        
        logger.info(f"TraderAgent已初始化，标的: {symbol}, 初始资金: {initial_funds}")
    
    def _setup_decision_agent(self):
        """设置决策Agent的系统提示词"""
        system_prompt = dedent("""
            你是一名专业的交易代理，负责根据分析师团队的报告做出投资决策。
            
            你的任务是：
            1. 仔细分析提供的投资计划和市场分析
            2. 结合过往交易历史和经验教训
            3. 考虑当前可用资金和持仓情况
            4. 做出明确的交易决策（买入/卖出/持有）
            
            决策原则：
            - 基于数据和分析，而非情绪
            - 考虑风险管理，控制单笔交易规模
            - 从过往失败中学习，避免重复错误
            - 保持投资组合的均衡性
            
            输出格式：
            请在回答的最后部分包含以下XML标签来表明你的决策：
            
            <ACTION>BUY</ACTION>
            <QUANTITY>10</QUANTITY>
            
            或者：
            
            <ACTION>SELL</ACTION>
            <QUANTITY>5</QUANTITY>
            
            或者：
            
            <ACTION>HOLD</ACTION>
            <QUANTITY>0</QUANTITY>
            
            说明：
            - ACTION标签：必须是BUY、SELL或HOLD之一
            - QUANTITY标签：仅在BUY/SELL时需要大于0，HOLD时为0，单位为手
            - 除了这两个标签外，其余所有文本都将作为决策理由(reasoning)
            
            请先给出详细的分析过程和决策理由，然后在最后用XML标签明确表明你的决策。
        """)
        
        self.decision_agent.set_system_prompt(system_prompt)
    
    def _initialize_portfolio(self):
        """初始化投资组合状态"""
        portfolio_json = None
        with create_transaction() as db:
            portfolio_json = db.kv_store.get(self.portfolio_key)
            db.rollback()
        if portfolio_json is None:
            logger.info(f"初始化投资组合：{self.symbol}, 资金: {self.initial_funds}")
            current_price = self.trade_operations.get_current_price(self.symbol)
            with create_transaction() as db:
                db.kv_store.set(
                    self.portfolio_key,
                    PortfolioStatus(
                        symbol=self.symbol,
                        available_funds=self.initial_funds,
                        holding_quantity=0,
                        current_price=current_price
                    ).to_dict()
                )
                db.commit()
        else:
            logger.info(f"加载现有投资组合：{self.symbol}")

    def _get_portfolio_status(self) -> PortfolioStatus:
        """获取投资组合状态"""

        # 获取当前价格
        portfolio_data: PortfolioStatus = None
        current_price = self.trade_operations.get_current_price(self.symbol)
        with create_transaction() as db:
            portfolio_record = db.kv_store.get(self.portfolio_key)
            if portfolio_record is None:
                portfolio_data = PortfolioStatus(
                    symbol= self.symbol,
                    available_funds=self.initial_funds,
                    holding_quantity=0,
                    current_price=current_price
                )
            else:
                portfolio_data = PortfolioStatus.from_dict(portfolio_record)
                portfolio_data.current_price = self.trade_operations.get_current_price(self.symbol)

        return portfolio_data

    
    def _get_trade_history(self, days: int = 60) -> List[TradeRecord]:
        """获取交易历史"""
        with create_transaction() as db:
            history_data = db.kv_store.get(self.history_key)
            
            if history_data is None:
                return []
            
            records = []
            cutoff_date = datetime.now() - timedelta(days=days)
            
            for record_data in history_data:
                record_date = datetime.fromisoformat(record_data["date"])
                if record_date >= cutoff_date:
                    records.append(TradeRecord(
                        date=record_date,
                        action=record_data["action"],
                        price=record_data["price"],
                        quantity=record_data["quantity"],
                        amount=record_data["amount"],
                        available_funds=record_data["available_funds"],
                        holding_quantity=record_data["holding_quantity"],
                        reason=record_data["reason"],
                        bull_bear_report=record_data.get("bull_bear_report", "")  # 新增字段
                    ))
            
            # 按日期排序
            records.sort(key=lambda x: x.date, reverse=True)
            return records
    
    def get_trade_detail_of_date(self, date: datetime) -> TradeRecord:
        """获取某日的交易详情"""
        # 计算从指定日期到今天的天数
        today = datetime.now()
        days_diff = (today - date).days + 1  # +1确保包含指定日期
        
        # 如果日期在未来，直接返回None
        if days_diff <= 0:
            return None
        
        history = self._get_trade_history(days=days_diff)
        
        for record in history:
            if record.date.date() == date.date():
                return record
        
        return None
    
    def add_bull_bear_research_report(self, report_content: str):
        """添加牛熊研究报告"""
        self.bull_bear_research_report = report_content
        logger.info("已添加牛熊研究报告")
    
    def make_trading_decision(self) -> Dict[str, Any]:
        """做出交易决策"""
        try:
            logger.info(f"开始为{self.symbol}做出交易决策...")
            
            # 1. 获取当前投资组合状态
            portfolio = self._get_portfolio_status()
            
            # 2. 获取交易历史
            history = self._get_trade_history(days=60)
            
            # 3. 获取过往经验教训
            past_memory = self._get_past_memory(portfolio)
            
            # 4. 检查是否有牛熊研究报告
            if not self.bull_bear_research_report:
                raise ValueError("请先添加牛熊研究报告")
            
            # 5. 构建决策提示词
            decision_prompt = self._build_decision_prompt(
                bull_bear_report=self.bull_bear_research_report,
                portfolio=portfolio,
                history=history,
                past_memory=past_memory
            )
            
            # 6. 让决策Agent做出决策
            logger.info("生成交易决策...")
            decision_response = self.decision_agent.ask(decision_prompt, json_response=True)
            
            # 7. 解析决策结果
            parsed_decision = self._validate_decision(decision_response, portfolio)
            
            # 8. 执行交易
            trade_result = None
            if parsed_decision["action"] != "HOLD":
                trade_result = self._execute_trade(parsed_decision, portfolio)
            
            return {
                "success": True,
                "decision": parsed_decision,
                "trade_result": trade_result or {"action": "HOLD", "message": "保持现有仓位"},
                "portfolio_status": self._get_portfolio_status()
            }
                
        except Exception as e:
            logger.error(f"交易决策失败: {e}")
            logger.debug(traceback.format_exc())
            return {
                "success": False,
                "error": str(e),
                "portfolio_status": self._get_portfolio_status()
            }
    
    def _get_past_memory(self, portfolio: PortfolioStatus) -> str:
        """获取过往经验教训"""
        # 构建当前情况描述
        situation = dedent(f"""
        标的：{self.symbol}
        当前价格：{portfolio.current_price:.2f}元
        持仓：{portfolio.holding_quantity}手
        可用资金：{portfolio.available_funds:.2f}元
        牛熊研究报告：{self.bull_bear_research_report}
        """)
        
        # 搜索相似的反思记录
        similar_reflections = self.reflector.search_similar_reflections(
            situation=situation,
            top_k=self.reflect_top_k
        )
        
        if not similar_reflections:
            return "暂无过往经验记录"
        
        memory_str = "过往经验教训：\n"
        for i, reflection in enumerate(similar_reflections, 1):
            content = reflection.get("content", "")
            memory_str += f"{i}. {content}\n"
        
        return memory_str
    
    def _build_decision_prompt(
        self,
        bull_bear_report: str,
        portfolio: PortfolioStatus,
        history: List[TradeRecord],
        past_memory: str
    ) -> str:
        """构建决策提示词"""
        # 格式化交易历史
        history_str = "最近交易历史：\n"
        if history:
            for i, record in enumerate(history[:5], 1):  # 显示最近5次交易
                history_str += f"{i}. {record.date.strftime('%Y-%m-%d')} {record.action} {record.quantity}手 @{record.price:.2f} - {record.reason}\n"
        else:
            history_str += "暂无交易历史\n"
        
        # 计算资金相关信息
        current_price = portfolio.current_price
        available_funds = portfolio.available_funds
        cost_per_lot = current_price * 100  # 每手成本（100股/手）
        max_affordable_lots = int(available_funds / cost_per_lot) if cost_per_lot > 0 else 0
        
        # 构建完整提示词
        prompt = dedent(f"""
            基于分析师团队的全面分析，以下是为{portfolio.symbol}量身定制的牛熊研究报告。该报告融合了技术分析、基本面分析、市场情绪和新闻事件的深度洞察。请将此报告作为评估您下一步交易决策的基础。

            牛熊研究报告：
            {bull_bear_report}

            当前投资组合状态：
            - 标的：{portfolio.symbol}
            - 可用资金：{portfolio.available_funds:.2f}元
            - 持有数量：{portfolio.holding_quantity}手
            - 持有价值：{portfolio.holding_val:.2f}元
            - 当前价格：{portfolio.current_price:.2f}元/股
            - 总价值：{portfolio.total_value:.2f}元
            - 每手成本：{cost_per_lot:.2f}元（100股/手）
            - 最大可买入手数：{max_affordable_lots}手
            - 剩余资金在买入后：{available_funds - cost_per_lot:.2f}元（买入1手后）

            {history_str}

            {past_memory}

            请利用这些洞察，做出明智且有策略的决策。考虑以下因素：
            1. 风险管理：单笔交易不超过总资金的30%，建议控制在20%以内
            2. 资金限制：确保买入数量不超过最大可买入手数（{max_affordable_lots}手）
            3. 持仓管理：避免过度集中或分散
            4. 经验教训：从过往成功或失败中学习
            5. 市场时机：结合技术面和基本面分析
            6. 持有策略：有时持有比交易更明智，避免过度交易
            7. 资金预留：建议预留一定资金应对市场波动

            注意事项：
            - 如果决定买入，数量必须在可承受范围内（1-{max_affordable_lots}手）
            - 如果买入可用资金不足1手或卖出持有数量不足一手，只能选择HOLD
            - 卖出时不能超过当前持仓数量（{portfolio.holding_quantity}手）

            请给出详细的分析和决策理由，并在最后用JSON格式明确表明您的最终决策。
        """).strip()
        
        return prompt
    
    def _validate_decision(self, decision_response: str, portfolio: PortfolioStatus) -> Dict[str, Any]:
        """解析XML标签格式的决策结果"""
        import re
        
        # 提取ACTION标签
        action_match = re.search(r'<ACTION>(.*?)</ACTION>', decision_response, re.IGNORECASE)
        if not action_match:
            raise LlmReplyInvalid("未找到ACTION标签", decision_response)
        
        action = action_match.group(1).strip().upper()
        if action not in ["BUY", "SELL", "HOLD"]:
            raise LlmReplyInvalid(f"无效的决策行动: {action}", decision_response)
        
        # 提取QUANTITY标签
        quantity_match = re.search(r'<QUANTITY>(.*?)</QUANTITY>', decision_response, re.IGNORECASE)
        if not quantity_match:
            raise LlmReplyInvalid("未找到QUANTITY标签", decision_response)
        
        try:
            quantity = int(quantity_match.group(1).strip())
        except ValueError:
            raise LlmReplyInvalid(f"无效的交易手数: {quantity_match.group(1)}", decision_response)
        
        # 验证quantity逻辑
        if action in ["BUY", "SELL"]:
            if quantity <= 0:
                raise LlmReplyInvalid(f"无效的交易手数: {quantity}", decision_response)

            if action == "BUY":
                # 验证买入数量是否超过可买入手数
                max_affordable_lots = int(portfolio.available_funds / (portfolio.current_price * 100))
                if quantity > max_affordable_lots:
                    raise LlmReplyInvalid(f"买入数量超过最大可买入手数: {max_affordable_lots}手", decision_response)
                
            if action == "SELL":
                # 验证卖出数量是否超过持仓数量
                if quantity > portfolio.holding_quantity:
                    raise LlmReplyInvalid(f"卖出数量超过持仓数量: {portfolio.holding_quantity}手", decision_response)
        
        elif action == "HOLD":
            if quantity != 0:
                raise LlmReplyInvalid(f"HOLD决策的数量必须为0: {quantity}", decision_response)
        
        # 提取reasoning（除了XML标签外的所有文本）
        reasoning = decision_response
        # 移除ACTION标签
        reasoning = re.sub(r'<ACTION>.*?</ACTION>', '', reasoning, flags=re.IGNORECASE)
        # 移除QUANTITY标签
        reasoning = re.sub(r'<QUANTITY>.*?</QUANTITY>', '', reasoning, flags=re.IGNORECASE)
        reasoning = reasoning.strip()
        
        if not reasoning:
            raise LlmReplyInvalid("决策理由不能为空", decision_response)
        
        # 标准化输出
        result = {
            "action": action,
            "quantity": quantity,
            "reasoning": reasoning,
            "full_response": decision_response
        }
        
        return result
                
    
    def _execute_trade(
        self,
        decision: Dict[str, Any],
        portfolio: PortfolioStatus,
    ) -> Dict[str, Any]:
        """执行交易"""
        try:
            action = decision["action"]
            quantity = decision["quantity"]
            current_price = portfolio.current_price
            
            # 计算交易金额
            trade_amount = quantity * 100 * current_price  # 100股/手
            
            # 验证交易可行性
            if action == "BUY":
                # 执行买入
                new_available_funds = portfolio.available_funds - trade_amount
                new_holding_quantity = portfolio.holding_quantity + quantity
                assert new_available_funds >= 0, "可用资金不足，无法执行买入"
                
            elif action == "SELL":
                assert portfolio.holding_quantity > quantity > 0, "卖出数量必须大于0且不超过持仓数量"
                # 执行卖出
                new_available_funds = portfolio.available_funds + trade_amount
                new_holding_quantity = portfolio.holding_quantity - quantity
            
            portfolio.holding_quantity = new_holding_quantity
            portfolio.available_funds = new_available_funds
            # 更新投资组合状态
            with create_transaction() as db:
                db.kv_store.set(self.portfolio_key, portfolio.to_dict())
                # 添加交易记录
                trade_record = TradeRecord(
                    date=datetime.now(),
                    action=action,
                    price=current_price,
                    quantity=quantity,
                    amount=trade_amount,
                    available_funds=new_available_funds,
                    holding_quantity=new_holding_quantity,
                    reason=decision["reasoning"],
                    bull_bear_report=self.bull_bear_research_report
                )
                # 获取现有历史记录
                history_data = db.kv_store.get(self.history_key) or []
                history_data.append(trade_record.to_dict())
                db.kv_store.set(self.history_key, history_data)

                db.commit()
            
            logger.info(f"交易执行成功：{action} {quantity}手 @{current_price:.2f}")
            
            return {
                "action": action,
                "quantity": quantity,
                "price": current_price,
                "amount": trade_amount,
                "new_available_funds": new_available_funds,
                "new_holding_quantity": new_holding_quantity,
                "message": f"成功{action} {quantity}手，价格{current_price:.2f}元/股"
            }
            
        except Exception as e:
            logger.error(f"交易执行失败: {e}")
            raise
    
    def reflect_on_past_decisions(self, days_ago: int = 1) -> Optional[Dict[str, Any]]:
        """
        对过往交易决策进行反思分析
        
        Args:
            days_ago: 距离决策日期过去的天数
            
        Returns:
            反思结果字典，如果没有找到历史记录则返回None
        """
        try:
            from lib.modules.agents.common import get_ohlcv_history
            from lib.utils.number import change_rate
            
            # 获取历史价格数据
            ohlcv_history = get_ohlcv_history(self.symbol, limit=days_ago + 1)
      
            # 计算实际收益率
            decision_date_price = ohlcv_history[0].close  # days_ago天前的价格
            current_price = ohlcv_history[-1].close  # 后来价格
            actual_return = change_rate(decision_date_price, current_price)
            
            # 获取历史交易记录
            decision_date = ohlcv_history[0].timestamp
            historical_trade = self.get_trade_detail_of_date(decision_date)
            
            if historical_trade is None:
                logger.warning(f"未找到{decision_date.strftime('%Y-%m-%d')}的交易记录")
                return None
            
            logger.info(f"🔍 开始对{self.symbol}的交易决策进行反思分析")
            logger.info(f"   决策日期: {decision_date.strftime('%Y-%m-%d')}")
            logger.info(f"   决策时价格: {decision_date_price:.2f}元")
            logger.info(f"   后来价格: {current_price:.2f}元")
            logger.info(f"   实际收益率: {actual_return:.2%}")
            logger.info(f"   历史决策: {historical_trade.action}")
            
            # 构建反思情况描述 - 包含当时的牛熊研究报告
            situation = dedent(f"""
                标的：{self.symbol}
                当前价格: {historical_trade.price:.2f}元
                持仓: {historical_trade.previous_holding_quantity}
                可用资金：{historical_trade.previous_available_funds:.2f}元
                牛熊研究报告：{historical_trade.bull_bear_report}
            """)
            
            analysis_opinion = dedent(
                f"""
                决策：{historical_trade.action}
                理由：{historical_trade.reason}
                """
            )
                                      
            # 创建反思数据
            reflection_data = ReflectionData(
                situation=situation,
                analysis_opinion=analysis_opinion,
                days_past=days_ago,
                return_loss_percentage=actual_return,
                decision_date=decision_date
            )
            
            # 执行反思
            logger.info("📝 执行投资决策反思...")
            reflection_result = self.reflector.reflect_on_decision(reflection_data)
            
            if reflection_result.success:
                logger.info("✅ 交易决策反思完成")
                logger.debug(f"反思内容: {reflection_result.reflection_content}")
                return {
                    "success": True,
                    "historical_trade": historical_trade,
                    "decision_date_price": decision_date_price,
                    "current_price": current_price,
                    "actual_return": actual_return,
                    "reflection_result": reflection_result
                }
            else:
                logger.warning("❌ 交易决策反思失败")
                return {
                    "success": False,
                    "error": "反思执行失败",
                    "historical_trade": historical_trade
                }
                
        except Exception as e:
            logger.error(f"反思过程中发生错误: {e}")
            logger.debug(traceback.format_exc())
            return {
                "success": False,
                "error": str(e)
            }
