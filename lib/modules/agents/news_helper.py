from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List
from lib.adapter.llm import get_llm, get_llm_direct_ask
from lib.adapter.llm.interface import LlmAbstract
from lib.modules.agents.common import get_news_in_text
from lib.utils.news import (
    render_news_in_markdown_group_by_time_for_each_platform
)
from lib.modules.news_proxy import news_proxy
from lib.tools.ashare_stock import get_ashare_stock_info, get_stock_news, get_stock_news_during

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

ASHARE_SYSTEM_PROMPT_TEMPLATE = """
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
class NewsSummaryer:
    """
    用于获取平台在一定时间范围内的新闻并为某个投资标的进行总结分析。
    """
    llm: LlmAbstract

    def __init__(self, llm: LlmAbstract = None):
        self.llm = llm or get_llm("paoluz", "gpt-4o-mini", temperature=0.2)

    def summary_crypto_news(
        self,
        coin_name: str,
        from_time: datetime,
        end_time: datetime = datetime.now(),
        platforms: List[str] = ["cointime"],
    ) -> str:
        system_prompt = CRYPTO_SYSTEM_PROMPT_TEMPLATE.format(coin_name=coin_name)
        news_in_md = get_news_in_text(from_time, end_time, platforms)
        ask_llm = get_llm_direct_ask(
            system_prompt,
            llm = self.llm,
        )
        return ask_llm(news_in_md)

    def summary_ashare_news(
        self,
        stock_code: str,
        from_time: datetime,
        end_time: datetime = datetime.now(),
        platforms: List[str] = ["caixin"],
    ) -> str:
        stock_info = get_ashare_stock_info(stock_code)
        system_prompt = ASHARE_SYSTEM_PROMPT_TEMPLATE.format(
            stock_name=stock_info["stock_name"],
            stock_code=stock_code,
            stock_type=stock_info["stock_type"],
            stock_business=stock_info["stock_business"],
        )
        platform_news = {
            platform: news_proxy.get_news_during(platform, from_time, end_time)
            for platform in platforms
        }
        platform_news["eastmoney"] = get_stock_news_during(stock_code, from_time, end_time)
        news_in_md = render_news_in_markdown_group_by_time_for_each_platform(platform_news)
        ask_llm = get_llm_direct_ask(
            system_prompt, 
            llm = self.llm
        )
        return ask_llm(news_in_md)


__all__ = ["NewsSummaryer"]
