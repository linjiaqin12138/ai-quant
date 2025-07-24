import os
from datetime import datetime

from textwrap import dedent
from typing import Any, Dict, Optional

import typer
from lib.adapter.apis import get_crypto_info, get_fear_greed_index
from lib.adapter.notification.push_plus import PushPlus
from lib.utils.time import days_ago
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

CRYPTO_NAME_MAPPING = {
    "BTC/USDT": "bitcoin",
    "ETH/USDT": "ethereum",
    "BNB/USDT": "binancecoin",
    "XRP/USDT": "ripple",
    "SOL/USDT": "solana",
    "DOGE/USDT": "dogecoin",
    "TRUMP/USDT": "trumpcoin",
    "SHIB/USDT": "shiba-inu",
    "ADA/USDT": "cardano",
    "SUI/USDT": "sui",
    "TRX/USDT": "tron",
}

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
        # if self.symbol.endswith('USDT'):
        #     raise Exception("仅支持A股交易")

    @property
    def _report_prefix(self): 
        if '/' in self.symbol:
            base_symbol = self.symbol.split('/')[0]
            return f"{base_symbol}_{self.current_time.strftime('%Y%m%d')}"
        return f"{self.symbol}_{self.current_time.strftime('%Y%m%d')}"
    
    def _get_report_with_cache(self, agent_name: str, news_from: Optional[datetime] = None) -> str:
        with create_transaction() as db:
            report_txt = db.kv_store.get(self._report_prefix + f"_{agent_name}_report")
            print(report_txt)
            if report_txt:
                return report_txt
        
        report_html = ""
        report_txt = ""
        if agent_name == "fundamental_agent":
            report_txt = self.fundamental_agent.analyze_fundamental_data(self.symbol)
            report_html = self.fundamental_agent.generate_html_report()
            self.logger.msg(f"基本面分析")
            self.logger.msg(report_txt)
        elif agent_name == "sentiment_agent":
            report_txt = self.sentiment_agent.analyze_stock_sentiment(self.symbol)
            report_html = self.sentiment_agent.generate_html_report()
            self.logger.msg(f"情绪分析")
            self.logger.msg(report_txt)
        elif agent_name == "news_agent":
            report_txt = self.news_agent.analyze_news(self.symbol, news_from or days_ago(1))
            report_html = self.news_agent.generate_html_report()
            self.logger.msg(f"新闻分析")
            self.logger.msg(report_txt)
        elif agent_name == "market_agent":
            report_txt = self.market_agent.analyze_stock_market(self.symbol)
            report_html = self.market_agent.generate_html_report()
            self.logger.msg(f"技术分析")
            self.logger.msg(report_txt)
        elif agent_name == "bull_bear_agent":
            if 'USDT' in self.symbol:
                crypto_sentiment = get_fear_greed_index()
                
                self.bull_bear_agent.add_sentiment_report(
                    dedent(
                        f"""
                            加密货币恐慌与贪婪指数: {crypto_sentiment['value']} ({crypto_sentiment['value_classification']})
                            来源：Alternative.me
                        """
                    )
                )
                if CRYPTO_NAME_MAPPING.get(self.symbol):
                    crypto_fundamental = get_crypto_info(CRYPTO_NAME_MAPPING[self.symbol])[0]
                    self.bull_bear_agent.add_fundamentals_report(
                        dedent(
                            f"""
                                币种: {crypto_fundamental['name']} ({crypto_fundamental['symbol']})
                                当前价格: {crypto_fundamental['current_price']}
                                市值: {crypto_fundamental['market_cap']}
                                完全稀释市值: {crypto_fundamental['fully_diluted_valuation']}
                                市值排名： {crypto_fundamental['market_cap_rank']}
                                总代币数量: {crypto_fundamental['total_supply']}
                                最大代币数量: {crypto_fundamental['max_supply']}
                                流通量: {crypto_fundamental['circulating_supply']}
                                24h交易量: {crypto_fundamental['total_volume']}
                                24h最高价: {crypto_fundamental['high_24h']}
                                24h最低价: {crypto_fundamental['low_24h']}
                                24h涨跌幅: {crypto_fundamental['price_change_percentage_24h']}%
                                24h市值变化绝对值： {crypto_fundamental['market_cap_change_24h']}
                                24h市值变化百分比: {crypto_fundamental['market_cap_change_percentage_24h']}%
                                历史最高价: {crypto_fundamental['ath']}
                                历史最低价: {crypto_fundamental['atl']}
                                历史最高价时间: {crypto_fundamental['ath_date']}
                                历史最低价时间: {crypto_fundamental['atl_date']}
                                距离历史最高价的百分比变化: {crypto_fundamental['ath_change_percentage']}%
                                距离历史最低价的百分比变化: {crypto_fundamental['atl_change_percentage']}%
                                投资回报率（部分币种有）：{crypto_fundamental['roi']}
                                来源：CoinGecko
                            """
                        )
                    )
            else:
                if self.current_time.weekday() == 0:
                    self.bull_bear_agent.add_fundamentals_report(self._get_report_with_cache("fundamental_agent", news_from=news_from))
                self.bull_bear_agent.add_sentiment_report(self._get_report_with_cache("sentiment_agent", news_from=news_from))
            self.bull_bear_agent.add_market_research_report(self._get_report_with_cache("market_agent", news_from=news_from))
            self.bull_bear_agent.add_news_report(self._get_report_with_cache("news_agent", news_from=news_from))
            self.bull_bear_agent.set_symbol(self.symbol)
            report_txt = self.bull_bear_agent.start_debate()
            report_html = self.bull_bear_agent.generate_html_report()
            self.logger.msg(f"多空辩论")
            self.logger.msg(report_txt)

        with create_transaction() as db:
            db.kv_store.set(self._report_prefix + f"_{agent_name}_report", report_txt)
            db.commit()

        if report_html:
            if not os.path.exists(self.html_report_folder):
                os.makedirs(self.html_report_folder, exist_ok=True)
            today_str = datetime.now().strftime('%Y-%m-%d')
            report_dir = os.path.join(self.html_report_folder, today_str)
            os.makedirs(report_dir, exist_ok=True)

            with open(os.path.join(report_dir, f"{self._report_prefix}_{agent_name}_report.html"), "w", encoding="utf-8") as f:
                f.write(report_html)

        return report_txt


    def _core(self, ohlcv_history):
        self._validate()
        bull_bear_research_result = self._get_report_with_cache(
            "bull_bear_agent",
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
            llm=decision_llm
        )
        self.decision_agent.set_system_prompt(
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
                - QUANTITY标签：仅在BUY/SELL时需要大于0，HOLD时为0，单位为手(股票)或个(加密货币)
                - 除了这两个标签外，其余所有文本都将作为决策理由(reasoning)
                
                请先给出详细的分析过程和决策理由，然后在最后用XML标签明确表明你的决策。
                """
            )
        )
        self.summary_text = get_llm_direct_ask(
            system_prompt=dedent(
                """
                将以下内容转换为100个字以内的总结，主要体现决策的思路：
                """
            ),
            llm=summary_llm
        )

    def _get_crypto_portfolio_data(self) -> Dict[str, Any]:
        curr_price = self.trading_system.current_price
        free_money = self.trading_system.free_money
        hold_amount = self.trading_system.hold_amount
        holding_value = hold_amount * curr_price
        position_level = holding_value / (free_money + holding_value) * 100
        max_lots_can_buy = free_money // curr_price
        return {
            "current_price": curr_price,
            "free_money": free_money,
            "hold_amount": hold_amount,
            "holding_value": holding_value,
            "position_level": position_level,
            "max_lots_can_buy": max_lots_can_buy
        }
    
    def _get_stock_portfolio_data(self) -> Dict[str, Any]:
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
        if self.trading_system.symbol.endswith('USDT'):
            portfolio_data = self._get_crypto_portfolio_data()
            return f"""
            当前持仓情况：
            - 可用资金: {portfolio_data['free_money']}USDT
            - 持有数量: {portfolio_data['hold_amount']}个
            - 持有价值：{portfolio_data['holding_value']}USDT
            - 仓位水平: {portfolio_data['position_level']}%
            - 当前价格: {portfolio_data['current_price']}USDT
            - 当前资金可买：{portfolio_data['max_lots_can_buy']}个
            """
        portfolio_data = self._get_stock_portfolio_data()
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
            self.trading_system.state.set('historys', [])

        historys = self.trading_system.state.get('historys')
        if not historys:
            return "没有历史交易记录。"
    

        digest = f"交易计划开始时间：{historys[0]['date']}\n"
        digest += "过去10次历史交易决策记录摘要：\n"
        for record in historys[-10:]:
            if record["action"] == "HOLD":
                digest += f"  - {record['date']}: 观望, 理由: {record['summary']}"
            else:
                digest += f"  - {record['date']}: {record['action']} {record['quantity']}{'手' if self.trading_system.symbol.endswith('USDT') else '个'}, 理由: {record['summary']}\n"
        return digest
    
    def _validate_decision(self, decision_response: str) -> Dict[str, Any]:
        """解析XML标签格式的决策结果"""
        import re
        portfolio = self._get_stock_portfolio_data()
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
        portfolio = self._get_stock_portfolio_data()
        prompt = dedent(f"""
        基于分析师团队的全面分析，以下是为{symbol}量身定制的牛熊研究报告。该报告融合了技术分析、基本面分析、市场情绪和新闻事件的深度洞察。请将此报告作为评估您下一步交易决策的基础。

        牛熊研究报告：
        {research_report}

        当前投资组合状态：
        {self._get_portfolio_digest()}

        历史交易决策摘要：
        {self._get_history_digest()}

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

        请给出详细的分析和决策理由，并在最后用XML格式明确表明您的最终决策。
        """
        )
        rsp = self.decision_agent.ask(prompt, tool_use=True)
        return self._validate_decision(rsp)

    def execute_decision(self, decision: Dict[str, Any]) -> str:
        action = decision["action"]
        quantity = decision["quantity"]
        reasoning = decision["reasoning"]
        date = self.trading_system.current_time.strftime('%Y-%m-%d')
        if action == "BUY":
            self.trading_system.buy(amount = quantity* 100, comment=reasoning)
            self.trading_system.state.append('historys', {
                'date': date,
                'action': action,
                'quantity': quantity,
                'reasoning': reasoning,
                'summary': self.summary_text(reasoning)
            })
        elif action == "SELL":
            self.trading_system.sell(amount=quantity * 100, comment=reasoning)
            self.trading_system.state.append('historys', {
                'date': date,
                'action': action,
                'quantity': quantity,
                'reasoning': reasoning,
                'summary': self.summary_text(reasoning)
            })
        else:
            # action == "HOLD"
            self.trading_system.state.append('historys', {
                'date': date,
                'action': action,
                'reasoning': reasoning,
                'summary': self.summary_text(reasoning)
            })

def main(
    symbol: str = typer.Option(..., help="股票代码"),
    name: str = typer.Option(..., help="任务名称"),
    investment: float = typer.Option(..., help="初始投资金额")
):
    agent = TradingSystem()
    agent.run(
        name=name,
        symbol = symbol,
        investment = investment,
        notification=PushPlus(template="markdown"),
    )
    
if __name__ == "__main__":
    typer.run(main)
    