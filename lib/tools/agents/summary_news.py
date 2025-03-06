from typing import List, Dict
from lib.model.news import NewsInfo
from lib.adapter.gpt import get_agent
from lib.utils.news import render_news_in_markdown_group_by_time_for_each_platform

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

def summary_crypto_news(
    coin_name: str,
    news_by_platform: Dict[str, List[NewsInfo]],
    llm_provider: str, 
    model: str,
    temperature: float = 0.2
) -> str:
    system_prompt = CRYPTO_SYSTEM_PROMPT_TEMPLATE.format(
        coin_name = coin_name
    )
    news_in_md = render_news_in_markdown_group_by_time_for_each_platform(news_by_platform)
    llm = get_agent(llm_provider, model, temperature=temperature)
    llm.set_system_prompt(system_prompt)
    return llm.ask(news_in_md)

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

def summary_ashare_news(
    stock_name: str,
    stock_code: str,
    stock_business: str,
    news_by_platform: Dict[str, List[NewsInfo]],
    llm_provider: str, 
    model: str,
    stock_type: str = '股票',
    temperature: float = 0.2
) -> str:
    system_prompt = ASHARE_SYSTEM_PROMPT_TEMPLATE.format(
        stock_name=stock_name,
        stock_code=stock_code,
        stock_type=stock_type,
        stock_business=stock_business
    )
    news_in_md = render_news_in_markdown_group_by_time_for_each_platform(news_by_platform)
    llm = get_agent(llm_provider, model, temperature=temperature)
    llm.set_system_prompt(system_prompt)
    return llm.ask(news_in_md)

__all__ = [
    'summary_crypto_news',
    'summary_ashare_news'
]