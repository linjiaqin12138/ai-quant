from datetime import datetime
from lib.adapter.llm import get_llm
from lib.modules.strategy.strategyv2 import StrategyBase
from lib.modules.agents.bull_bear_researcher import BullBearResearcher
from lib.modules.agents.fundamental_analyzer import FundamentalAnalyzer
from lib.modules.agents.web_page_reader import WebPageReader
from lib.modules.agents.news_agent import NewsAgent
from lib.modules.agents.stock_sentiment_analyzer import StockSentimentAnalyzer
from lib.modules.agents.market_analyst import MarketAnalyst
from lib.modules.agents.json_fixer import JsonFixer

class TradingAgent(StrategyBase):
    def __init__(self):
        self.data_foler = "data"
        self.quick_think_llm = get_llm("paoluz", "deepseek-v3")
        self.deep_think_llm = get_llm("paoluz", "deepseek-r1")
        self.cheap_mini_llm_for_tool = get_llm("paoluz", "gpt-4o-mini")
        self.web_page_reader = WebPageReader(self.cheap_mini_llm_for_tool)
        self.json_fixer = JsonFixer(self.cheap_mini_llm_for_tool)

        self.stock_sentiment_analyzer = StockSentimentAnalyzer(self.quick_think_llm, self.web_page_reader, self.json_fixer)
        self.fundamental_analyzer = FundamentalAnalyzer(self.quick_think_llm, self.web_page_reader)
        self.bull_bear_researcher = BullBearResearcher(self.quick_think_llm)
        self.news_agent = NewsAgent(self.quick_think_llm)
        self.market_analysis_agent = MarketAnalyst(self.quick_think_llm, self._data_fetch_amount)

    def _addtional_state_parameters(self):
        return {
            'operations': []
        }
    
    def _validate(self):
        if self._is_test_mode:
            raise Exception("不支持回测模式")
        if self.frame != '1d':
            raise Exception("仅支持1天周期的交易")
        if self.symbol.endswith('USDT'):
            raise Exception("仅支持A股交易")

    def _build_and_save_report(self, news_from: datetime) -> str:
        fundamental_result = self.fundamental_analyzer.analyze_fundamental_data(self.symbol)
        sentiment_result = self.stock_sentiment_analyzer.analyze_stock_sentiment(self.symbol)
        news_analysis_result = self.news_agent.analyze_news_for(self.symbol, news_from)
        market_analysis_result = self.market_analysis_agent.analyze_stock_market(self.symbol)

        
    def _core(self, ohlcv_history):
        self._validate()
        

        

if __name__ == "__main__":
    agent = TradingAgent()
    agent.run(
        symbol = "002594",
        investment = 100000,
        
    )