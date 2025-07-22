from datetime import datetime

from textwrap import dedent
from typing import Any, Dict, Optional
from lib.adapter.database.db_transaction import create_transaction
from lib.adapter.llm import get_llm, get_llm_direct_ask
from lib.adapter.llm.interface import LlmAbstract
from lib.model.error import LlmReplyInvalid
from lib.modules.agent import get_agent
from lib.modules.agents.comment_extractor_agent import CommentExtractorAgent
from lib.modules.agents.global_news_agent import GlobalNewsAgent
from lib.modules.strategy.strategyv2 import StrategyBase
from lib.modules.agents.bull_bear_researcher import BullBearResearcher
from lib.modules.agents.fundamental_analyzer import FundamentalAnalyzer
from lib.modules.agents.web_page_reader import WebPageReader
from lib.modules.agents.news_agent import NewsAgent
from lib.modules.agents.stock_sentiment_analyzer import StockSentimentAnalyzer
from lib.modules.agents.market_analyst import MarketAnalyst
from lib.modules.agents.json_fixer import JsonFixer
import os


class TradingSystem(StrategyBase):
    def __init__(self):
        super().__init__()
        self.html_report_folder = "./report"
        web_page_reader = WebPageReader(llm=get_llm("paoluz", "gpt-4o-mini"))
        json_fixer = JsonFixer(llm=get_llm("paoluz", "gemini-2.0-flash-lite"))
        
        comment_agent = CommentExtractorAgent(
            llm=get_llm("paoluz", "gemini-2.0-flash-lite"), 
            web_page_reader=web_page_reader, 
            json_fixer=json_fixer
        )
        global_news_reporter = GlobalNewsAgent(
            llm=get_llm("paoluz", "deepseek-v3"), 
            web_page_reader=web_page_reader
        )
        self.fundamental_agent = FundamentalAnalyzer(
            llm=get_llm("paoluz", "deepseek-v3"), 
            web_page_reader=web_page_reader
        )
        self.sentiment_agent = StockSentimentAnalyzer(
            llm=get_llm("paoluz", "deepseek-v3"),
            comment_agent=comment_agent
        )
        self.news_agent = NewsAgent(
            llm=get_llm("paoluz", "deepseek-v3"), 
            web_page_reader=web_page_reader,
            global_news_reporter=global_news_reporter
        )
        self.market_agent = MarketAnalyst(
            llm=get_llm("paoluz", "deepseek-r1"), 
            ohlcv_days=self._data_fetch_amount
        )
        self.bull_bear_agent = BullBearResearcher(
            web_page_reader=web_page_reader,
            debate_llm=get_llm("paoluz", "gemini-2.5-flash"),
            decision_llm=get_llm("paoluz", "deepseek-r1"),
            rounds=2,
        )
        self.trading_decision_agent = TradeDecisionAgent(
            decision_llm=get_llm("paoluz", "deepseek-r1"),
            summary_llm=get_llm("paoluz", "gpt-4o-mini"),
            trading_system=self
        )
    
    def _validate(self):
        if self._is_test_mode:
            raise Exception("不支持回测模式")
        if self.frame != '1d':
            raise Exception("仅支持1天周期的交易")
        if self.symbol.endswith('USDT'):
            raise Exception("仅支持A股交易")

    @property
    def _report_prefix(self):
        return f"{self.symbol}_{self.current_time.strftime('%Y%m%d')}"

    def _build_and_save_reports(self, news_from: datetime) -> str:
        fundamental_result = self.fundamental_agent.analyze_fundamental_data(self.symbol)
        sentiment_result = self.sentiment_agent.analyze_stock_sentiment(self.symbol)
        news_analysis_result = self.news_agent.analyze_news(self.symbol, news_from)
        market_analysis_result = self.market_agent.analyze_stock_market(self.symbol)
        self.bull_bear_agent.add_fundamentals_report(fundamental_result)
        self.bull_bear_agent.add_sentiment_report(sentiment_result)
        self.bull_bear_agent.add_news_report(news_analysis_result)
        self.bull_bear_agent.add_market_research_report(market_analysis_result)
        self.bull_bear_agent.set_symbol(self.symbol)
        bull_bear_research_result = self.bull_bear_agent.start_debate()
        with create_transaction() as db:
            db.kv_store.set(self._report_prefix + "_bull_bear_research_result", bull_bear_research_result)
            db.kv_store.set(self._report_prefix + "_fundamental_result", fundamental_result)
            db.kv_store.set(self._report_prefix + "_sentiment_result", sentiment_result)
            db.kv_store.set(self._report_prefix + "_news_analysis_result", news_analysis_result)
            db.kv_store.set(self._report_prefix + "_market_analysis_result", market_analysis_result)
            db.commit()
        
        # 创建以当前日期为目录的文件夹，存放html报告
        # 确保html_report_folder存在
        if not os.path.exists(self.html_report_folder):
            os.makedirs(self.html_report_folder, exist_ok=True)
        today_str = datetime.now().strftime('%Y-%m-%d')
        report_dir = os.path.join(self.html_report_folder, today_str)
        os.makedirs(report_dir, exist_ok=True)
        # 这里可以将报告保存到report_dir目录下
        fundamental_html_report = self.fundamental_agent.generate_html_report()
        sentiment_html_report = self.sentiment_agent.generate_html_report()
        news_html_report = self.news_agent.generate_html_report()
        market_html_report = self.market_agent.generate_html_report()
        bull_bear_html_report = self.bull_bear_agent.generate_html_report()

        self.logger.msg(f"基本面分析")
        self.logger.msg(fundamental_html_report)
        self.logger.msg(f"情绪分析")
        self.logger.msg(sentiment_html_report)
        self.logger.msg(f"新闻分析")
        self.logger.msg(news_html_report)
        self.logger.msg(f"技术分析")
        self.logger.msg(market_html_report)
        self.logger.msg(f"多空辩论")
        self.logger.msg(bull_bear_html_report)

        with open(os.path.join(report_dir, f"{self._report_prefix}_fundamental_report.html"), "w", encoding="utf-8") as f:
            f.write(fundamental_html_report)
        
        with open(os.path.join(report_dir, f"{self._report_prefix}_sentiment_report.html"), "w", encoding="utf-8") as f:
            f.write(sentiment_html_report)

        with open(os.path.join(report_dir, f"{self._report_prefix}_news_report.html"), "w", encoding="utf-8") as f:
            f.write(news_html_report)
        
        with open(os.path.join(report_dir, f"{self._report_prefix}_market_report.html"), "w", encoding="utf-8") as f:
            f.write(market_html_report)

        with open(os.path.join(report_dir, f"{self._report_prefix}_bull_bear_report.html"), "w", encoding="utf-8") as f:
            f.write(bull_bear_html_report)
    
        return bull_bear_research_result


    def _core(self, ohlcv_history):
        self._validate()
        bull_bear_research_result = self._build_and_save_reports(
            news_from=ohlcv_history[-1].timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
        )
        decision = self.trading_decision_agent.make_decision(bull_bear_research_result)
        self.logger.msg(f"交易决策:\n{decision['reasoning']}\n\n决策结果: {decision['action']} {decision['quantity']}手")

        self.trading_decision_agent.execute_decision(decision)
        

class TradeDecisionAgent:
    def __init__(
        self, 
        trading_system: TradingSystem,
        summary_llm: Optional[LlmAbstract] = None, 
        decision_llm: Optional[LlmAbstract] = None,
    ):
        summary_llm = summary_llm or get_llm("paoluz", "gpt-4o-mini")
        decision_llm = decision_llm or get_llm("paoluz", "deepseek-r1")
        self.trading_system = trading_system

        self.decision_agent = get_agent(
            dedent(
            """
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
            """
            ),
            llm=decision_llm
        )
        self.summary_text = get_llm_direct_ask(
            system_prompt=dedent(
                """
                将以下内容转换为100个字以内的总结，主要体现决策的思路：
                """
            ),
            llm=summary_llm
        )

    def _get_portfolio_data(self) -> Dict[str, Any]:
        curr_price = self.trading_system.current_price
        free_money = self.trading_system.free_money
        hold_amount = self.trading_system.hold_amount
        holding_lots = hold_amount // 100
        cost_per_lot = curr_price * 100
        position_level = hold_amount * curr_price / (free_money + hold_amount * curr_price) * 100
        max_lots_can_buy = free_money // cost_per_lot
        return {
            "current_price": curr_price,
            "free_money": free_money,
            "hold_amount": hold_amount,
            "holding_lots": holding_lots,
            "holding_value": hold_amount * curr_price,
            "cost_per_lot": cost_per_lot,
            "position_level": position_level,
            "max_lots_can_buy": max_lots_can_buy
        }
    
    def _get_portfolio_digest(self) -> str:
        portfolio_data = self._get_portfolio_data()
        return f"""
        当前持仓情况：
        - 可用资金: {portfolio_data['free_money']}元
        - 持有股票数量: {portfolio_data['holding_lots']}手
        - 持有价值：{portfolio_data['holding_value']}元
        - 仓位水平: {portfolio_data['position_level']}%
        - 当前价格: {portfolio_data['current_price']}元
        - 当前资金可买：{portfolio_data['max_lots_can_buy']}手
        """
    
    def _get_history_digest(self) -> str:
        if self.trading_system.state.get('historys') is None:
            self.trading_system.state.set('historys', {})

        historys = self.trading_system.state.get('historys')
        if not historys:
            return "没有历史交易记录。"
        
        sorted_history_dates = sorted(historys.keys())

        digest = f"交易计划开始时间：{sorted_history_dates[0]}\n"
        digest += "过去10次历史交易决策记录摘要：\n"
        for date in sorted_history_dates[-10:]:
            record = historys[date]
            if record["action"] == "HOLD":
                digest += f"  - {date}: 观望, 理由: {record['reasoning']}"
            else:
                digest += f"  - {date}: {record['action']} {record['quantity']}手, 理由: {record['reasoning']}\n"
        return digest
    
    def _validate_decision(self, decision_response: str) -> Dict[str, Any]:
        """解析XML标签格式的决策结果"""
        import re
        portfolio = self._get_portfolio_data()
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
                max_affordable_lots = portfolio["max_lots_can_buy"]
                if quantity > max_affordable_lots:
                    raise LlmReplyInvalid(f"买入数量超过最大可买入手数: {max_affordable_lots}手", decision_response)
                
            if action == "SELL":
                # 验证卖出数量是否超过持仓数量
                holding_lots = portfolio["holding_lots"]
                if quantity > holding_lots:
                    raise LlmReplyInvalid(f"卖出数量超过持仓数量: {holding_lots}手", decision_response)
        
        # elif action == "HOLD":
        #     if quantity != 0:
        #         raise LlmReplyInvalid(f"HOLD决策的数量必须为0: {quantity}", decision_response)
        
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
    
    def make_decision(self, research_report:str) -> str:
        symbol = self.trading_system.symbol
        portfolio = self._get_portfolio_data()
        prompt = dedent(f"""
        基于分析师团队的全面分析，以下是为{symbol}量身定制的牛熊研究报告。该报告融合了技术分析、基本面分析、市场情绪和新闻事件的深度洞察。请将此报告作为评估您下一步交易决策的基础。

        牛熊研究报告：
        {research_report}

        当前投资组合状态：
        {self._get_portfolio_digest()}

        历史交易决策摘要：
        {self._get_history_digest}

        请利用这些洞察，做出明智且有策略的决策。考虑以下因素：
        1. 风险管理：单笔交易不超过总资金的30%，建议控制在20%以内
        2. 资金限制：确保买入数量不超过最大可买入手数（{portfolio['max_lots_can_buy']}手）
        3. 持仓管理：避免过度集中或分散
        4. 经验教训：从过往成功或失败中学习
        5. 市场时机：结合技术面和基本面分析
        6. 持有策略：有时持有比交易更明智，避免过度交易
        7. 资金预留：建议预留一定资金应对市场波动

        注意事项：
        - 如果决定买入，数量必须在可承受范围内（{portfolio['max_lots_can_buy']}手）
        - 如果买入可用资金不足1手或卖出持有数量不足一手，只能选择HOLD
        - 卖出时不能超过当前持仓数量（{portfolio['holding_lots']}手）

        请给出详细的分析和决策理由，并在最后用JSON格式明确表明您的最终决策。
        """
        )
        rsp = self.decision_agent.ask(prompt, tool_use=True)
        return self._validate_decision(rsp)

    def execute_decision(self, decision: Dict[str, Any]) -> str:
        action = decision["action"]
        quantity = decision["quantity"]
        reasoning = decision["reasoning"]
        
        if action == "BUY":
            self.trading_system.buy(amount = quantity* 100, comment=reasoning)
            self.trading_system.state.append('historys', {
                'action': action,
                'quantity': quantity,
                'reasoning': reasoning,
                'summary': self.summary_text(reasoning)
            })
        elif action == "SELL":
            self.trading_system.sell(amount=quantity * 100, comment=reasoning)
            self.trading_system.state.append('historys', {
                'action': action,
                'quantity': quantity,
                'reasoning': reasoning,
                'summary': self.summary_text(reasoning)
            })
        else:
            # action == "HOLD"
            self.trading_system.state.append('historys', {
                'action': action,
                'reasoning': reasoning,
                'summary': self.summary_text(reasoning)
            })
        # elif action == "HOLD":
        #     pass

    
if __name__ == "__main__":
    agent = TradingSystem()
    agent.run(
        symbol = "002594",
        investment = 1000000,
    )