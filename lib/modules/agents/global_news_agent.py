from dataclasses import dataclass
from datetime import datetime
from textwrap import dedent
from typing import List
from lib.adapter.llm import get_llm
from lib.adapter.llm.interface import LlmAbstract
from lib.modules import get_agent
from lib.modules.news_proxy import news_proxy
from lib.modules.agents.web_page_reader import WebPageReader
from lib.tools.cache_decorator import use_cache
from lib.tools.information_search import unified_search
from lib.utils.news import render_news_in_markdown_group_by_platform

# 全局系统提示词
GLOBAL_NEWS_SYSTEM_PROMPT_TEMPLATE = """
你是一个专业的金融分析师，擅长分析全球市场新闻和宏观经济信息。
"""

# 全局搜索提示词
# 使用小参数模型，比如QwQ-32B等，工具调用能力很弱：只有reasoning，没有tool_use
# 使用：qwen3-235b-a22b，每次又只会调用一次
GLOBAL_NEWS_SEARCH_PROMPT_TEMPLATE = """
请高效地搜索和收集最新的市场新闻信息。**重要：你可以同时调用多个工具来提高效率！**

**搜索策略：**

**第一阶段：批量搜索核心关键词和查询各平台热搜**
请**同时**搜索以下关键词，不要一个一个来，每次搜索后分析结果质量：

1. **全球宏观经济**（英文搜索，region="us-en"）关键词示例：
   - "Fed policy" (美联储政策)
   - "inflation data" (通胀数据)
   - "interest rates" (利率)
   - "GDP growth" (GDP增长)

2. **美国经济数据**（英文搜索，region="us-en"）关键词示例：
   - "employment report" (就业报告)
   - "CPI data" (CPI数据)
   - "consumer confidence" (消费者信心)

3. **加密货币**（英文搜索，region="us-en"）关键词示例：
   - "Bitcoin price" (比特币价格)
   - "crypto regulation" (加密货币监管)

4. **中国市场**（中文搜索，region="zh-cn"）关键词示例：
   - "中国股市政策" (中国股市政策)
   - "新能源汽车" (新能源汽车)
   - "中国GDP数据" (中国GDP数据)
   - "PMI指数" (PMI指数)

5. **全球市场**（英文搜索，region="us-en"）关键词示例：
   - "US stocks" (美国股市)
   - "oil prices" (石油价格)
   - "gold trend" (黄金趋势)

6. **全球热搜**（使用各大平台的热搜查询工具）：

**第二阶段：结果评估和深度获取**
每次搜索后，请评估：
1. **信息完整性**：新闻描述是否完整，是否包含关键数据
2. **重要性评级**：是否涉及重大政策变化或市场事件
3. **是否需要深度阅读**：对于以下情况，使用`_read_web_page`获取完整内容：
   - 新闻标题重要但描述过于简短
   - 涉及具体经济数据或政策细节
   - 可能对市场产生重大影响的新闻

**第三阶段：补充搜索**
根据前面搜索结果的分析，如果发现某些重要领域信息不足，请：
1. 调整关键词重新搜索
2. 使用更具体的关键词
3. 变换搜索区域

**搜索执行指导：**
- **开始搜索**：关键词搜索开始，同时发起多个搜索工具调用
- **分析结果**：查看搜索结果的质量和相关性
- **决定下一步**：
  - 如果结果好且信息完整：直接输出报告
  - 如果有重要但信息不完整的新闻：使用`_read_web_page(url)`获取详细内容
  - 如果结果不理想：调整关键词重新搜索
- **继续循环**：重复上述过程，直到覆盖所有重要市场领域

**重要要求：**
1. **并行执行**：一次性发起多个相互独立的搜索工具调用请求，提高效率
2. **深度获取**：对重要新闻必须获取完整内容
3. **灵活调整**：根据搜索结果动态调整策略

**使用工具说明：**
- `_search_tool(query, region)`：搜索新闻，一次只搜索一个关键词
- `_read_web_page(url)`：获取重要新闻的完整内容
- `_get_top_10_hot_news_of_platform(platforms, top_k)`：获取各大平台的热搜

**最终输出要求：**
搜索完成后，请分析这些新闻信息并提供一份报告，参考模板如下：

## 📊 市场分析报告

### 🌍 全球宏观经济动态
- **主要经济政策变化**：央行政策、利率调整、财政政策
- **通胀和经济数据**：CPI、GDP、就业数据等关键指标
- **地缘政治影响**：国际冲突、贸易政策对市场的影响

### 📈 统计数据解读
- **中国统计数据**：最新发布的GDP、CPI、PMI、工业增加值等数据解读
- **美国统计数据**：最新发布的就业报告、通胀数据、消费者信心等数据解读
- **数据影响分析**：统计数据对市场趋势和政策走向的指示意义

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

### ⚠️ 投资风险和机会提示

#### 🔴 主要风险提示
- **宏观风险**：政策变化、通胀压力、利率风险等系统性风险
- **地缘政治风险**：国际冲突、贸易摩擦对市场的冲击风险
- **行业风险**：特定行业面临的监管、技术或竞争风险
- **流动性风险**：市场流动性紧张可能带来的风险

#### 🟢 潜在投资机会
- **政策红利**：受益于政策扶持的行业和主题投资机会
- **技术创新**：新技术突破带来的投资机会
- **估值修复**：被错杀或低估的优质资产投资机会
- **周期性机会**：基于经济周期的资产配置机会

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
7. **对于通过网页读取工具获取的详细内容，特别标注"详细内容来源"**

**如果搜索结果中没有提供具体的文章链接，请在报告中明确说明："部分信息来源无法提供具体链接"**
"""


def cache_key_generator(kwargs: dict, *args) -> str:
    """
    生成缓存键，只要from_time的年月日相同就命中缓存
    """
    from_time: datetime = datetime.now()
    date_str = from_time.strftime("%Y-%m-%d")
    return f"global_news_report:{date_str}"

@dataclass
class GlobalNewsAgent:
    """
    全球新闻报告生成器，专门负责生成全球新闻和宏观经济信息的分析报告
    """
    _llm: LlmAbstract

    def __init__(
            self, 
            llm: LlmAbstract = None,
            web_page_reader: WebPageReader = None,
        ):
        self._llm = llm or get_llm("paoluz", "gpt-4o-mini", temperature=0.2)
        self._web_page_reader = web_page_reader or WebPageReader(llm=self._llm)
        self._agent = get_agent(llm=self._llm)
        self._agent.set_system_prompt(GLOBAL_NEWS_SYSTEM_PROMPT_TEMPLATE)
        self._agent.register_tool(self._search_tool)
        self._agent.register_tool(self._read_web_page)
        self._agent.register_tool(self._get_top_10_hot_news_of_platform)

    def _get_top_10_hot_news_of_platform(self, platforms: List[str], top_k: int = 5) -> str:

        """
        获取指定平台的前top_k条热门新闻
        Args:
            platforms: 字符串数组，新闻平台名称列表, 例如"36kr", "qq-news", "sina-news", "sina", "huxiu", "netease-news", "toutiao"
            top_k: 每个平台返回的热门新闻数量，默认为5

        Returns:
            返回格式化的新闻列表字符串
        """
        result = {}
        for platform in platforms:
            result[platform] = news_proxy.get_current_hot_news(platform)[:top_k]
        return render_news_in_markdown_group_by_platform(result)

    def _read_web_page(self, url: str) -> str:
        """
        读取网页内容并返回格式化的新闻列表字符串
        Args:
            url: 网页URL

        Returns:
            返回格式化的新闻列表字符串
        """
        return self._web_page_reader.read_and_summary(url)

    def _search_tool(self, query: str, region: str) -> str:
        """
        根据关键词使用搜索引擎搜索一天范围内的最新新闻，并返回格式化的新闻列表字符串。
        Args:
            query: 搜索查询字符串
            region: 搜索区域字符串, 例如 "zh-cn" 表示中文区域, "en-us" 表示美国英语区域等

        Returns:
            返回格式化的新闻列表字符串
        """
        return render_news_in_markdown_group_by_platform({
            "GoogleSearch": unified_search(
                query, 
                time_limit="d", 
                max_results=10,
                region=region
            )
        })
    
    @use_cache(86400, use_db_cache=True, key_generator=cache_key_generator)
    def get_recent_global_news_report(self) -> str:
        """
        获取全球新闻和宏观经济信息
        """
        # 构建搜索提示
        return self._agent.ask(GLOBAL_NEWS_SEARCH_PROMPT_TEMPLATE, tool_use=True)

__all__ = ["GlobalNewsAgent"]