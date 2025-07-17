from dataclasses import dataclass
from datetime import datetime, timedelta
from textwrap import dedent
from typing import List
from lib.adapter.llm import get_llm, get_llm_direct_ask
from lib.adapter.llm.interface import LlmAbstract
from lib.modules import get_agent
from lib.tools.cache_decorator import use_cache
from lib.tools.information_search import unified_search
from lib.utils.news import (
    news_list_to_markdown,
    render_news_in_markdown_group_by_time_for_each_platform,
    render_news_in_markdown_group_by_platform,
)
from lib.modules.news_proxy import news_proxy
from lib.tools.ashare_stock import get_ashare_stock_info, get_stock_news

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
class NewsSummaryer:
    llm: LlmAbstract

    def __init__(self, llm: LlmAbstract = None):
        self.llm = llm or get_llm("paoluz", "gpt-4o-mini", temperature=0.2)

    @use_cache(86400, use_db_cache=True, key_generator=cache_key_generator)
    def get_daily_global_news_report(self, from_time: datetime) -> str:
        """
        获取全球新闻和宏观经济信息
        """
        time_desc = f"从{from_time.strftime('%Y年%m月%d日 %H:%M')}到现在"

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
        
        agent = get_agent(llm = self.llm)
        agent.set_system_prompt(system_prompt)
        
        # 注册统一搜索工具 - 优先使用Google搜索，失败时使用DuckDuckGo
        agent.register_tool(search_tool)

        # 构建搜索提示
        prompt = f"""
        请根据{time_desc}的时间范围，智能生成相关的搜索关键词来获取最新的市场新闻。不要只使用下面的示例关键词，而是要根据当前市场热点和时事动态来生成更有针对性的搜索词。

        **搜索策略建议（仅供参考，请根据实际情况调整）：**
        
        **全球宏观经济领域：**
        - 可以搜索：美联储最新政策、欧央行利率决定、通胀数据CPI、GDP增长等
        - 根据当前时间节点，关注即将公布的重要经济数据
        
        **加密货币市场：**
        - 可以搜索：比特币价格走势、以太坊升级、加密货币监管、机构投资等
        - 关注最新的监管动态和技术发展
        
        **A股和中国市场：**
        - 可以搜索：中国股市政策、科技板块、新能源汽车、房地产政策等
        - 关注政府最新政策和行业发展动态
        
        **全球市场和大宗商品：**
        - 可以搜索：美股财报、石油价格、黄金走势、地缘政治等
        - 关注主要商品价格和国际形势变化

        **重要要求：**
        1. 请自主生成8-12个具有时效性和针对性的搜索关键词
        2. 优先搜索与当前市场热点相关的内容
        3. 根据初步搜索结果，动态调整后续搜索策略
        4. 每次搜索使用以下参数：
           - time_limit: "d" 或 "w"（优先使用"d"获取最新信息）
           - max_results: 8-10
           - region: "zh-cn"

        搜索完成后，请分析这些新闻信息并提供一份报告：
        
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
        
        ### 📚 信息来源
        本报告中的所有信息均来自以下具体新闻文章（请列出所有引用的具体文章链接）：
        - [在此列出所有引用的具体新闻文章标题和链接]
        
        **关键信息来源标注要求：**
        1. **必须使用搜索结果中的具体文章URL**，而不是网站首页链接
        2. **每条重要信息都要用 [文章标题](具体文章URL) 格式标注来源**
        3. **示例格式**：根据 [美联储宣布维持利率不变，市场预期下次会议或加息](https://www.example.com/fed-rate-decision-2024-07-17) 的报道...
        4. **如果同一信息有多个来源，选择最权威或最新的文章链接**
        5. **在信息来源章节中，按类别整理所有引用的文章链接**
        6. **确保每个链接都是可访问的具体新闻文章页面**

        **如果搜索结果中没有提供具体的文章链接，请在报告中明确说明："部分信息来源无法提供具体链接"**
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
            system_prompt,
            llm = self.llm,
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
            llm = self.llm
        )
        return ask_llm(news_in_md)


__all__ = ["NewsSummaryer"]
