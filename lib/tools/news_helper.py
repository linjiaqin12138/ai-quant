from dataclasses import dataclass
from datetime import datetime, timedelta
from textwrap import dedent
from typing import List
from lib.adapter.llm import get_llm_direct_ask
from lib.modules import get_agent
from lib.tools.cache_decorator import use_cache
from lib.tools.information_search import unified_search
from lib.utils.news import (
    news_list_to_markdown,
    render_news_in_markdown_group_by_time_for_each_platform,
    render_news_in_markdown_group_by_platform,
)
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

search_tool = news_list_to_markdown(unified_search)

def cache_key_generator(kwargs: dict, *args) -> str:
    """
    生成缓存键，只要from_time的年月日相同就命中缓存
    """
    from_time: datetime = kwargs["from_time"]
    date_str = from_time.strftime("%Y-%m-%d")
    return f"global_news_report:{date_str}"
    
@dataclass
class NewsHelper:
    llm_provider: str = "paoluz"
    model: str = "gpt-4o-mini"
    temperature: float = 0.2

    @use_cache(86400, use_db_cache=True, key_generator=cache_key_generator)
    def get_global_news_report(self, from_time: datetime, end_time: datetime = datetime.now()) -> str:
        """
        获取全球新闻和宏观经济信息
        """
        time_desc = f"从{from_time.strftime('%Y年%m月%d日 %H:%M')}到{end_time.strftime('%Y年%m月%d日 %H:%M')}"

        # 统一的系统提示词，支持加密货币和A股市场
        system_prompt = dedent(f"""
        你是一个专业的金融分析师，擅长分析全球市场新闻和宏观经济信息。请搜索{time_desc}的全球新闻和宏观经济信息，重点关注对交易有用的信息，包括：

        **主要关注领域：**
        1. **全球宏观经济**：通胀数据、央行政策、利率变化、经济指标
        2. **地缘政治**：国际冲突、政策变化、贸易摩擦
        3. **加密货币市场**：比特币、以太坊等主流币种动态、监管政策
        4. **A股市场**：中国股市政策、行业动态、重要公司新闻
        5. **全球股市**：美股、欧股等主要市场动态
        6. **大宗商品**：石油、黄金、贵金属价格动向

        请分析这些新闻对市场的潜在影响，回复请使用中文。
        """)
        
        agent = get_agent(self.llm_provider, self.model)
        agent.set_system_prompt(system_prompt)
        
        # 注册统一搜索工具 - 优先使用Google搜索，失败时使用DuckDuckGo
        agent.register_tool(search_tool)

        # 构建搜索提示
        prompt = f"""
        请使用工具搜索以下关键词的最新新闻，获取{time_desc}的信息：

        **全球宏观经济搜索关键词：**
        1. "global economy macroeconomic indicators inflation central bank policy" (全球经济宏观指标)
        2. "federal reserve ECB interest rates monetary policy" (央行政策利率)
        3. "geopolitical events market impact trade war" (地缘政治市场影响)
        4. "economic data GDP unemployment inflation CPI" (经济数据指标)
        
        **加密货币市场搜索关键词：**
        5. "bitcoin cryptocurrency market regulation policy" (比特币加密货币市场)
        6. "ethereum DeFi blockchain technology adoption" (以太坊区块链技术)
        7. "crypto exchange regulation institutional investment" (加密货币监管机构投资)
        
        **A股和中国市场搜索关键词：**
        8. "China stock market A-shares policy regulation" (中国股市A股政策)
        9. "Chinese economy GDP manufacturing PMI data" (中国经济数据)
        10. "China technology sector semiconductor policy" (中国科技板块政策)
        
        **全球市场和大宗商品搜索关键词：**
        11. "US stock market volatility earnings reports" (美股市场波动)
        12. "oil gold commodity prices inflation hedge" (石油黄金商品价格)
        13. "global supply chain disruption energy crisis" (全球供应链能源危机)
        
        搜索时请使用以下参数：
        - time_limit: "w"/"d"/"m"/"y"（分别代表一周/一天/一个月/一年）
        - max_results: 8 - 10
        - region: "zh-cn"
        
        搜索完成后，请分析这些新闻信息并参考一下模板提供一份报告：
        
        ## 📊 市场分析报告
        
        ### 🌍 全球宏观经济动态
        - **主要经济政策变化**：央行政策、利率调整、财政政策
        - **通胀和经济数据**：CPI、GDP、就业数据等关键指标
        - **地缘政治影响**：国际冲突、贸易政策对市场的影响
        
        ### 💰 加密货币市场分析
        - **比特币和主流币动态**：价格趋势、技术发展、市场情绪
        - **监管政策影响**：各国对加密货币的最新政策和监管动向
        - **机构投资趋势**：大型机构和公司的加密货币投资动态
        
        ### 🇨🇳 A股和中国市场
        - **政策导向**：政府政策对股市的影响和行业扶持政策
        - **重要板块动态**：科技、新能源、医药等重点行业新闻
        - **宏观经济数据**：中国GDP、制造业PMI等经济指标
        
        ### 🌐 全球市场联动
        - **主要股指表现**：美股、欧股、亚太股市的表现和相互影响
        - **大宗商品走势**：石油、黄金、贵金属等价格变化
        - **货币汇率影响**：主要货币对的走势对各市场的影响
        
        ### 📈 投资策略建议
        
        #### 🔸 短期策略（1-2周）
        - **风险资产配置**：股票、加密货币的仓位建议
        - **避险资产**：黄金、债券等避险工具的配置
        - **关键技术位**：重要支撑阻力位和交易机会
        
        #### 🔸 中期策略（1-3个月）
        - **主题投资机会**：基于政策和趋势的主题投资方向
        - **资产轮动策略**：不同资产类别间的轮动配置
        - **风险管理**：仓位控制和止损策略
        
        ### ⚠️ 风险提示
        - **主要风险因素**：需要重点关注的市场风险
        - **黑天鹅事件**：可能对市场造成重大冲击的潜在事件
        - **风险控制措施**：建议的风险管理和资金管理策略
        
        ### 📅 重要时间节点
        - **经济数据发布**：未来1-2周重要经济数据发布时间
        - **政策会议**：央行会议、重要政策发布时间
        - **财报季**：重要公司财报发布时间
        
        请确保所有信息都基于搜索到的最新新闻数据，并保持客观和专业的分析态度。如果某个领域的搜索结果较少，请在分析中说明并基于一般市场知识提供补充分析。
        """
        
        response = agent.ask(prompt, tool_use=True)
        return response

    def get_crypto_news(
        self,
        from_time: datetime,
        end_time: datetime = datetime.now(),
        platforms: List[str] = ["cointime"],
    ) -> str:
        news_by_platform = {
            platform: news_proxy.get_news_during(platform, from_time, end_time)
            for platform in platforms
        }

        return (
            render_news_in_markdown_group_by_platform(news_by_platform)
            if datetime.now() - from_time <= timedelta(hours=1)
            else render_news_in_markdown_group_by_time_for_each_platform(
                news_by_platform
            )
        )

    def summary_crypto_news(
        self,
        coin_name: str,
        from_time: datetime,
        end_time: datetime = datetime.now(),
        platforms: List[str] = ["cointime"],
    ) -> str:
        system_prompt = CRYPTO_SYSTEM_PROMPT_TEMPLATE.format(coin_name=coin_name)
        news_in_md = self.get_crypto_news(from_time, end_time, platforms)
        ask_llm = get_llm_direct_ask(
            system_prompt, self.llm_provider, self.model, temperature=self.temperature
        )
        return ask_llm(news_in_md)

    def get_ashare_news(
        self,
        from_time: datetime,
        end_time: datetime = datetime.now(),
        platforms: List[str] = ["eastmoney", "caixin"],
        stock_code: str = None
    ) -> str:
        news_by_platform = {}
        for platform in platforms:
            if platform == "eastmoney" and stock_code:
                news_by_platform[platform] = list(
                    filter(
                        lambda n: from_time < n.timestamp < end_time,
                        get_stock_news(stock_code),
                    )
                )
            else:
                news_by_platform[platform] = news_proxy.get_news_during(
                    platform, from_time, end_time
                )
        return render_news_in_markdown_group_by_time_for_each_platform(news_by_platform)

    def summary_ashare_news(
        self,
        stock_code: str,
        from_time: datetime,
        end_time: datetime = datetime.now(),
        platforms: List[str] = ["cointime"],
    ) -> str:
        stock_info = get_ashare_stock_info(stock_code)
        system_prompt = ASHARE_SYSTEM_PROMPT_TEMPLATE.format(
            stock_name=stock_info["stock_name"],
            stock_code=stock_code,
            stock_type=stock_info["stock_type"],
            stock_business=stock_info["stock_business"],
        )
        news_in_md = self.get_ashare_news(
            from_time, end_time, platforms, stock_code=stock_code
        )
        ask_llm = get_llm_direct_ask(
            system_prompt, 
            self.llm_provider, 
            self.model, 
            temperature=self.temperature
        )
        return ask_llm(news_in_md)


__all__ = ["NewsHelper"]
