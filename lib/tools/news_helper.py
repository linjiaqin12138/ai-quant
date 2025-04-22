from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List
from lib.adapter.llm import get_llm_tool
from lib.utils.news import render_news_in_markdown_group_by_time_for_each_platform, render_news_in_markdown_group_by_platform
from lib.modules.news_proxy import news_proxy
from .ashare_stock import get_ashare_stock_info, get_stock_news

CRYPTO_SYSTEM_PROMPT_TEMPLATE = """
你是一位资深的加密货币新闻分析师，擅长总结和分析加密货币新闻。
请总结加密货币新闻，特别关注对{coin_name}有影响的内容：
1. 提取出对{coin_name}有影响的新闻，包括：
    - 市场动态
    - 政策变化
    - 国际局势
    - 宏观经济数据
    - 主流加密货币的行情
    - {coin_name}币的相关新闻
    - {coin_name}项目的最新进展

2. 请使用中文对上述内容进行总结，并以分点形式呈现。
"""

ASHARE_SYSTEM_PROMPT_TEMPLATE  = """
你是一位资深的投资新闻分析师，擅长总结和分析A股市场新闻。
请总结不同平台获取到的新闻，特别关注对"{stock_name}({stock_code})"这只{stock_business}行业的{stock_type}有影响的内容：
1. 提取出对{stock_name}有影响的新闻，包括：
    - 市场动态
    - 政策变化
    - 国际局势
    - 宏观经济数据
    - 大盘的行情
    - {stock_name}的相关新闻

2. 请使用中文对上述内容进行总结，并以分点形式呈现。

注意：A股市场新闻通常"报喜不报忧"，注意甄别有价值的利好信息，关注利空消息的负面影响
"""

@dataclass
class NewsHelper:
    llm_provider: str = 'paoluz'
    model: str = 'gpt-4o-mini'
    temperature: float = 0.2

    def summary_crypto_news(
            self, 
            coin_name: str,
            from_time: datetime,
            end_time: datetime = datetime.now(),
            platforms: List[str] = ['cointime']
        ) -> str:
        system_prompt = CRYPTO_SYSTEM_PROMPT_TEMPLATE.format(coin_name = coin_name)
        news_by_platform = { platform: news_proxy.get_news_during(platform, from_time, end_time) for platform in platforms }

        news_in_md = render_news_in_markdown_group_by_platform(news_by_platform) if datetime.now() - from_time <= timedelta(hours=1) else render_news_in_markdown_group_by_time_for_each_platform(news_by_platform)

        ask_llm = get_llm_tool(system_prompt, self.llm_provider, self.model, temperature = self.temperature)
        return ask_llm(news_in_md)

    def summary_ashare_news(
            self,
            stock_code: str,
            from_time: datetime,
            end_time: datetime = datetime.now(),
            platforms: List[str] = ['cointime']
        ) -> str:
        stock_info = get_ashare_stock_info(stock_code)
        system_prompt = ASHARE_SYSTEM_PROMPT_TEMPLATE.format(
            stock_name=stock_info['stock_name'],
            stock_code=stock_code,
            stock_type=stock_info['stock_type'],
            stock_business=stock_info['stock_business']
        )
        news_by_platform = {}
        for platform in platforms:
            if platform == 'eastmoney':
                news_by_platform[platform] = list(filter(lambda n: from_time < n.timestamp < end_time, get_stock_news(stock_code)))
            else:
                news_by_platform[platform] = news_proxy.get_news_during(platform, from_time, end_time)

        news_in_md = render_news_in_markdown_group_by_time_for_each_platform(news_by_platform)
        ask_llm = get_llm_tool(system_prompt, self.llm_provider, self.model, temperature=self.temperature)
        return ask_llm(news_in_md)


__all__ = [
    'NewsHelper'
]