#!/usr/bin/env python3
"""
Bull Bear Researcher Agent
牛熊辩论研究员Agent，通过两个对立观点的Agent进行多轮辩论分析
"""

import re
from textwrap import dedent
from typing import Optional, List, TypedDict
from jinja2 import Template

from lib.adapter.llm import LlmAbstract, get_llm
from lib.modules import get_agent
from lib.tools.information_search import unified_search
from lib.modules.agents.web_page_reader import WebPageReader
from lib.logger import logger

from lib.utils.news import render_news_in_markdown_group_by_platform
from lib.utils.string import escape_text_for_jinja2_temperate

# HTML报告模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>牛熊辩论分析报告 - {{ symbol }}</title>
    <script src="https://cdn.jsdelivr.net/npm/marked@9.1.6/lib/marked.umd.js"></script>
    <style>
        body {
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2c3e50;
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }
        h2 {
            color: #34495e;
            margin-top: 30px;
            margin-bottom: 15px;
            border-left: 4px solid #3498db;
            padding-left: 10px;
        }
        .info-box {
            background-color: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .summary-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }
        .stat-card {
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }
        .stat-number {
            font-size: 2em;
            font-weight: bold;
            color: #2980b9;
        }
        .stat-label {
            color: #7f8c8d;
            margin-top: 5px;
        }
        .debate-round {
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .round-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #dee2e6;
        }
        .round-title {
            font-weight: bold;
            font-size: 1.1em;
        }
        .bull-round {
            border-left: 4px solid #28a745;
        }
        .bull-title {
            color: #28a745;
        }
        .bear-round {
            border-left: 4px solid #dc3545;
        }
        .bear-title {
            color: #dc3545;
        }
        .debate-content {
            background-color: white;
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 15px;
            margin-top: 10px;
            line-height: 1.6;
        }
        .debate-content h1, .debate-content h2, .debate-content h3 {
            color: #2c3e50;
            margin-top: 20px;
            margin-bottom: 10px;
        }
        .debate-content h1 {
            border-bottom: 2px solid #3498db;
            padding-bottom: 8px;
            font-size: 1.5em;
        }
        .debate-content h2 {
            border-left: 4px solid #3498db;
            padding-left: 10px;
            font-size: 1.3em;
        }
        .debate-content h3 {
            color: #2980b9;
            font-size: 1.1em;
        }
        .debate-content h4 {
            color: #16a085;
            margin-top: 15px;
            margin-bottom: 8px;
        }
        .debate-content strong {
            color: #2c3e50;
            font-weight: bold;
        }
        .debate-content em {
            color: #7f8c8d;
            font-style: italic;
        }
        .debate-content ul, .debate-content ol {
            margin: 10px 0;
            padding-left: 25px;
        }
        .debate-content li {
            margin: 5px 0;
        }
        .debate-content blockquote {
            border-left: 4px solid #3498db;
            margin: 10px 0;
            padding: 8px 12px;
            background-color: #f0f7ff;
            font-style: italic;
        }
        .final-summary {
            background-color: #e8f5e8;
            border: 1px solid #4caf50;
            padding: 25px;
            border-radius: 8px;
            margin: 30px 0;
        }
        .summary-content {
            line-height: 1.8;
        }
        .summary-content h1, .summary-content h2, .summary-content h3 {
            color: #2c3e50;
            margin-top: 25px;
            margin-bottom: 15px;
        }
        .summary-content h1 {
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }
        .summary-content h2 {
            border-left: 4px solid #3498db;
            padding-left: 10px;
        }
        .summary-content h3 {
            color: #2980b9;
        }
        .summary-content table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background-color: white;
        }
        .summary-content th, .summary-content td {
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }
        .summary-content th {
            background-color: #f5f5f5;
            font-weight: bold;
        }
        .summary-content tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        .footer {
            text-align: center;
            margin-top: 40px;
            color: #7f8c8d;
            font-size: 0.9em;
            border-top: 1px solid #ecf0f1;
            padding-top: 20px;
        }
        .early-end-notice {
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            color: #856404;
        }
        .early-end-notice h3 {
            color: #856404;
            margin-top: 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎯 牛熊辩论分析报告</h1>
        
        <div class="info-box">
            <strong>分析标的:</strong> {{ symbol }}<br>
            <strong>计划轮数:</strong> {{ planned_rounds }}<br>
            <strong>实际轮数:</strong> {{ actual_rounds }}<br>
        </div>

        {% if market_research_report or sentiment_report or news_report or fundamentals_report %}
        <h2>📊 输入报告数据</h2>
        {% if market_research_report %}
        <div class="debate-round">
            <div class="round-header">
                <span class="round-title">📈 市场研究报告</span>
            </div>
            <div class="debate-content" id="market-report-content">
                <!-- 市场研究报告内容将通过JavaScript渲染 -->
            </div>
        </div>
        {% endif %}
        
        {% if sentiment_report %}
        <div class="debate-round">
            <div class="round-header">
                <span class="round-title">💭 情绪分析报告</span>
            </div>
            <div class="debate-content" id="sentiment-report-content">
                <!-- 情绪分析报告内容将通过JavaScript渲染 -->
            </div>
        </div>
        {% endif %}
        
        {% if news_report %}
        <div class="debate-round">
            <div class="round-header">
                <span class="round-title">📰 新闻报告</span>
            </div>
            <div class="debate-content" id="news-report-content">
                <!-- 新闻报告内容将通过JavaScript渲染 -->
            </div>
        </div>
        {% endif %}
        
        {% if fundamentals_report %}
        <div class="debate-round">
            <div class="round-header">
                <span class="round-title">📋 基本面报告</span>
            </div>
            <div class="debate-content" id="fundamentals-report-content">
                <!-- 基本面报告内容将通过JavaScript渲染 -->
            </div>
        </div>
        {% endif %}
        {% endif %}
        
        <div class="summary-stats">
            <div class="stat-card">
                <div class="stat-number">{{ actual_rounds }}</div>
                <div class="stat-label">实际轮数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ total_exchanges }}</div>
                <div class="stat-label">总发言次数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ bull_exchanges }}</div>
                <div class="stat-label">多头发言</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ bear_exchanges }}</div>
                <div class="stat-label">空头发言</div>
            </div>
        </div>
        
        <h2>⚔️ 辩论过程</h2>
        {% for entry in debate_history %}
        <div class="debate-round {{ 'bull-round' if entry.role == '多头' else 'bear-round' }}">
            <div class="round-header">
                <span class="round-title {{ 'bull-title' if entry.role == '多头' else 'bear-title' }}">
                    {{ '🐂' if entry.role == '多头' else '🐻' }} 第{{ entry.round }}轮 - {{ entry.role }}观点
                </span>
            </div>
            <div class="debate-content" id="debate-content-{{ loop.index }}">
                <!-- 辩论内容将通过JavaScript渲染 -->
            </div>
        </div>
        {% endfor %}
        
        <div class="final-summary">
            <h2>📋 综合总结</h2>
            <div class="summary-content" id="summary-content">
                <!-- 总结内容将通过JavaScript渲染 -->
            </div>
        </div>
        
        <div class="footer">
            <p>由牛熊辩论研究Agent自动生成</p>
            <p>⚠️ 本报告仅供参考，不构成投资建议</p>
        </div>
    </div>
    
    <script>
        // 初始化marked配置
        marked.setOptions({
            breaks: true,
            gfm: true,
            headerIds: false,
            mangle: false
        });
        
        // 渲染各种报告内容
        {% if market_research_report %}
        const marketReportContent = `{{ market_research_report }}`;
        document.getElementById('market-report-content').innerHTML = marked.parse(marketReportContent);
        {% endif %}
        
        {% if sentiment_report %}
        const sentimentReportContent = `{{ sentiment_report }}`;
        document.getElementById('sentiment-report-content').innerHTML = marked.parse(sentimentReportContent);
        {% endif %}
        
        {% if news_report %}
        const newsReportContent = `{{ news_report }}`;
        document.getElementById('news-report-content').innerHTML = marked.parse(newsReportContent);
        {% endif %}
        
        {% if fundamentals_report %}
        const fundamentalsReportContent = `{{ fundamentals_report }}`;
        document.getElementById('fundamentals-report-content').innerHTML = marked.parse(fundamentalsReportContent);
        {% endif %}
        
        // 渲染总结内容
        const summaryContent = `{{ debate_report }}`;
        document.getElementById('summary-content').innerHTML = marked.parse(summaryContent);
        
        // 渲染每轮辩论内容
        {% for entry in debate_history %}
        const debateContent{{ loop.index }} = `{{ entry.content }}`;
        document.getElementById('debate-content-{{ loop.index }}').innerHTML = marked.parse(debateContent{{ loop.index }});
        {% endfor %}
    </script>
</body>
</html>
"""

BULL_SYS_PROMPT = dedent(
    """
        你是一位专业的多头分析师，支持投资该标的。你的任务是构建强有力的、基于证据的论据，强调增长潜力、竞争优势和积极的市场指标。

        **重要说明：**
        1. 系统提示词中给出的参考信息完全可信，不需要验证
        2. 除了系统提示词中的参考信息外，所有论点都必须通过工具搜索获取具体出处：
            - 每个论点必须先使用`_search_information`搜索相关新闻报道或分析报告
            - 使用`_read_web_page`深入阅读搜索结果中的具体链接，获取详细信息
            - 引用时必须使用具体的新闻/报告URL，不能仅引用公司官网或平台首页
            - 即便你已经知道某个信息，也必须通过工具搜索找到对应的具体出处
        3. 在构建论点时：
            - 每个论点都必须有对应的具体新闻/报告URL支持
            - 如果搜索不到具体出处，就不要使用这个论点
            - 不要捏造或篡改任何数据和事实
        4. 当你的工具搜索结果找不到有力的反驳证据，且对方论点确实合理时，请输出：
            <DEBATE_CONCEDE>我承认对方的观点更有说服力</DEBATE_CONCEDE>

        **可用工具：**
        - `_search_information`: 搜索相关信息来支持你的论点
        - `_read_web_page`: 深入阅读网页内容获取详细信息

        **重点关注的要点：**
        - 增长潜力：突出市场机会、收入预测和可扩展性
        - 竞争优势：强调独特产品、强品牌或主导市场地位等因素
        - 积极指标：使用财务健康、行业趋势和最近的积极新闻作为证据
        - 反驳空头观点：用具体数据和合理推理批判性分析空头论点，彻底解决担忧，并说明为什么多头观点具有更强的价值
        - 参与：以对话风格呈现你的论点，直接回应空头分析师的观点并进行有效辩论，而不是仅仅列出数据

        请提供令人信服的多头论点，反驳空头的担忧，并参与动态辩论，展示多头立场的优势。你还必须处理反思并从过去的经验教训和错误中学习。
        
        参考信息：
        {context}

        相似场景下的经验：
        {past_memory}
    """
)

BEAR_SYS_PROMPT = dedent(
    """
        你是一位专业的空头分析师，反对投资该标的。你的目标是提出充分理由的论点，强调风险、挑战和负面指标。

        **重要说明：**
        1. 系统提示词中给出的参考信息完全可信，不需要验证
        2. 除了系统提示词中的参考信息外，所有论点都必须通过工具搜索获取具体出处：
            - 每个论点必须先使用`_search_information`搜索相关新闻报道或分析报告
            - 使用`_read_web_page`深入阅读搜索结果中的具体链接，获取详细信息
            - 引用时必须使用具体的新闻/报告URL，不能仅引用公司官网或平台首页
            - 即便你已经知道某个信息，也必须通过工具搜索找到对应的具体出处
        3. 在构建论点时：
            - 每个论点都必须有对应的具体新闻/报告URL支持
            - 如果搜索不到具体出处，就不要使用这个论点
            - 不要捏造或篡改任何数据和事实
        4. 当你的工具搜索结果找不到有力的反驳证据，且对方论点确实合理时，请输出：
            <DEBATE_CONCEDE>我承认对方的观点更有说服力</DEBATE_CONCEDE>

        **可用工具：**
        - `_search_information`: 搜索相关信息来支持你的论点
        - `_read_web_page`: 深入阅读网页内容获取详细信息

        **重点关注的要点：**
        - 风险和挑战：突出市场饱和、财务不稳定或可能阻碍表现的宏观经济威胁等因素
        - 竞争劣势：强调市场地位较弱、创新下降或来自竞争对手的威胁等脆弱性
        - 负面指标：使用财务数据、市场趋势或最近不利新闻的证据来支持你的立场
        - 反驳多头观点：用具体数据和合理推理批判性分析多头论点，暴露弱点或过度乐观的假设
        - 参与：以对话风格呈现你的论点，直接回应多头分析师的观点并进行有效辩论，而不是简单地列出事实

        请提供令人信服的空头论点，反驳多头的主张，并参与动态辩论，展示投资该标的的风险和弱点。你还必须处理反思并从过去的经验教训和错误中学习。
        
        参考信息：
        {context}

        相似场景下的经验：
        {past_memory}
    """
)

SUMMARY_SYS_PROMPT = dedent(
    """
        作为投资组合经理和辩论主持人，你的角色是对本轮辩论进行批判性评估，并做出明确的决定：支持空头分析师、支持多头分析师，或仅在有充分理由的情况下选择"持有"。

        请简明扼要地总结双方的关键观点，重点突出最有说服力的证据或推理。你的推荐——买入、卖出或持有——必须明确且可执行。避免仅因双方观点都有道理就默认选择"持有"；你需要基于辩论中最有力的论据做出立场。

        此外，请为交易员制定详细的投资计划，包括：

        你的推荐：基于最有说服力论据的明确立场。
        理由：解释为何这些论据支持你的结论。
        策略行动：实施该推荐的具体步骤。
        请考虑你在类似情境下曾犯过的错误。利用这些经验教训优化你的决策，确保不断学习和提升。请以自然对话的方式呈现分析，无需特殊格式。
    """
)

class DebateHistoryItem(TypedDict):
    round: int
    role: str
    content: str

class BullBearResearcher:
    """牛熊辩论研究员"""
    
    def __init__(
            self,
            rounds: int = 1,
            llm: LlmAbstract = None,
            web_page_reader: Optional[WebPageReader] = None,
            debate_llm: Optional[LlmAbstract] = None,
            decision_llm: Optional[LlmAbstract] = None
        ):

        """
        初始化牛熊辩论研究员
        
        Args:
            llm: 默认的LLM对象
            record_folder: 记录文件夹路径
            rounds: 辩论轮数 (1-5)
            web_page_reader: 可选的网页阅读器
            vector_db: 向量数据库（保留参数，暂不使用）
            bull_llm: 多头分析师使用的LLM，为None时使用默认llm
            bear_llm: 空头分析师使用的LLM，为None时使用默认llm
            decision_llm: 决策分析师使用的LLM，为None时使用默认llm
        """
        llm = llm or get_llm('paoluz', 'deepseek-v3')
        self._plan_rounds = max(1, min(5, rounds))  # 确保轮数在1-5之间
        self.web_page_reader = web_page_reader or WebPageReader(llm=llm)
        self.decision_llm = decision_llm or self.llm
        self.bull_agent = get_agent(llm=debate_llm or llm)
        self.bear_agent = get_agent(llm=debate_llm or llm)
        self.decision_agent = get_agent(llm=decision_llm or llm)
        
        # 注册工具
        self.bull_agent.register_tool(self._search_information)
        self.bull_agent.register_tool(self._read_web_page)
        self.bear_agent.register_tool(self._search_information)
        self.bear_agent.register_tool(self._read_web_page)
        # 私有临时变量
        self._debate_history: List[DebateHistoryItem] = []
        self._current_turns = 0
        self._symbol = None
        # 报告内容
        self.market_research_report = ""
        self.sentiment_report = ""
        self.news_report = ""
        self.fundamentals_report = ""
        self._debate_research_report = ""

    def set_symbol(self, symbol: str):
        """设置分析标的"""
        self._symbol = symbol

    def _init_debate(self):
        """设置牛熊双方的系统提示"""
        context = self._format_context()
        
        # 为每个agent搜索相似的反思记录作为参考
        bull_reflections = ""
        bear_reflections = ""

        bull_prompt = BULL_SYS_PROMPT.format(context=context, past_memory=bull_reflections)
        bear_prompt = BEAR_SYS_PROMPT.format(context=context, past_memory=bear_reflections)
        self.bull_agent.set_system_prompt(bull_prompt)
        self.bear_agent.set_system_prompt(bear_prompt)
        self.decision_agent.set_system_prompt(SUMMARY_SYS_PROMPT)

        self._current_turns = 0
        self._debate_history = []
        self._debate_research_report = ""

    def _search_information(self, query: str) -> str:
        """
        关键词搜索相关资料

        Args: 
            query: 搜索关键词

        Returns:
            返回搜索结果的摘要
        """

        search_results = unified_search(
            query=query,
            max_results=10,
            time_limit="y"
        )
        return render_news_in_markdown_group_by_platform({
            "搜索结果": search_results,
        })


    def _read_web_page(self, url: str) -> str:
        """
        读取网页内容
        
        Args:
            url: 网页链接
            
        Returns:
            网页内容
        """
        return self.web_page_reader.read_and_summary(url)
    
    def add_market_research_report(self, report: str):
        """添加市场研究报告"""
        self.market_research_report = report
        logger.info("已添加市场研究报告")
    
    def add_sentiment_report(self, report: str):
        """添加情绪报告"""
        self.sentiment_report = report
        logger.info("已添加情绪报告")
    
    def add_news_report(self, report: str):
        """添加新闻报告"""
        self.news_report = report
        logger.info("已添加新闻报告")
    
    def add_fundamentals_report(self, report: str):
        """添加基本面报告"""
        self.fundamentals_report = report
        logger.info("已添加基本面报告")
    
    def _format_debate_history(self) -> str:
         return "\n".join([
            f"第{entry['round']}轮 - {entry['role']}:\n{entry['content']}\n"
            for entry in self._debate_history
        ])
    
    def _format_context(self) -> str:
        """格式化上下文信息"""
        result = ""

        if self.market_research_report:
            result += f"市场研究报告：{self.market_research_report}\n"
        if self.sentiment_report:
            result += f"社交媒体情绪报告：{self.sentiment_report}\n"
        if self.news_report:
            result += f"最新世界事务新闻：{self.news_report}\n"
        if self.fundamentals_report:
            result += f"公司基本面报告：{self.fundamentals_report}\n"
        return result
    
    def _add_history(self, role: str, content: str):
        """添加辩论历史"""
        self._debate_history.append({
            "round": self._curr_rounds,
            "role": role,
            "content": content
        })
        self._current_turns += 1
    
    def _check_debate_concede(self, content: str) -> bool:
        """检查是否有认输标识"""
        return bool(re.search(r'<DEBATE_CONCEDE>.*?</DEBATE_CONCEDE>', content, re.IGNORECASE | re.DOTALL))
    
    @property
    def _curr_rounds(self):
        return (self._current_turns) // 2 + 1
    
    def _validate_debate(self) -> str:
        if not self._symbol:
            raise ValueError("请先调用set_symbol设置分析标的symbol")
        if not (self.market_research_report and self.sentiment_report and self.news_report and self.fundamentals_report):
            raise ValueError("请先通过add_xx_report方法设置四类报告")

    def start_debate(self) -> str:
        """
        开始牛熊辩论，需先设置symbol和四类report
        """
        # 初始化内部状态
        self._init_debate()
        logger.info(f"🎯 开始牛熊辩论，共{self._plan_rounds}轮")
        
        logger.info(f"第1轮辩论开始...")
        logger.info(f"🐂 多头分析中...")
        bull_response = self.bull_agent.ask(f"请开始发表你的观点，分析投资价值", tool_use=True)
        self._add_history("多头", bull_response)
        if self._check_debate_concede(bull_response):
            logger.info(f"🏁 辩论提前结束：多头分析师认输")
            return self._generate_summary()
        
        logger.info(f"🐻 空头分析中...")
        bear_response = self.bear_agent.ask(f"请基于多头的观点进行反驳，分析{self._symbol}的投资风险：{bull_response}", tool_use=True)
        self._add_history("空头", bear_response)
        if self._check_debate_concede(bear_response):
            logger.info(f"🏁 辩论提前结束：空头分析师认输")
            return self._generate_summary()
        
        while self._curr_rounds <= self._plan_rounds:
            logger.info(f"第{self._curr_rounds}轮辩论开始...")
            logger.info(f"🐂 多头分析中...")
            bull_response = self.bull_agent.ask(f"请基于空头的观点进行反驳：{bear_response}", tool_use=True)
            self._add_history("多头", bull_response)
            if self._check_debate_concede(bull_response):
                logger.info(f"🏁 辩论提前结束：多头分析师认输")
                return self._generate_summary()
            
            logger.info(f"🐻 空头分析中...")
            bear_response = self.bear_agent.ask(f"请基于多头的观点进行反驳：{bull_response}", tool_use=True)
            self._add_history("空头", bear_response)
            if self._check_debate_concede(bear_response):
                logger.info(f"🏁 辩论提前结束：空头分析师认输")
                return self._generate_summary()
            
        logger.info("📋 生成辩论总结...")
        return self._generate_summary()
    
    def _generate_summary(self) -> str:
        """
        生成辞论总结并自动保存辩论记录
        """
        # 创建专门用于总结的Agent
        # 格式化辩论历史为文本
        debate_history_text = self._format_debate_history()
        context = self._format_context()

        past_memory_str = ""

        self._debate_research_report = self.decision_agent.ask(
            dedent(
                f"""
                    辩论历史：
                    {debate_history_text}

                    辩论依据:
                    {context}

                    对过往的反思： "{past_memory_str}"
                """
            )
        )
        
        return self._debate_research_report
    
    def generate_html_report(self) -> str:
        """
        生成HTML报告
            
        Returns:
            HTML报告字符串
        """
        assert self._debate_research_report
        
        bull_exchanges = sum(1 for entry in self._debate_history if entry["role"] == "多头")
        bear_exchanges = sum(1 for entry in self._debate_history if entry["role"] == "空头")
        
        # 处理辩论内容，转义特殊字符
        processed_debate_history = []
        for entry in self._debate_history:
            processed_entry = entry.copy()
            processed_entry["content"] = escape_text_for_jinja2_temperate(entry["content"])
            processed_debate_history.append(processed_entry)

        # 渲染HTML内容
        html_content = Template(HTML_TEMPLATE).render(
            symbol=self._symbol,
            planned_rounds=self._plan_rounds,
            actual_rounds=self._curr_rounds - 1 if self._current_turns % 2 == 0 else self._curr_rounds,
            market_research_report=self.market_research_report,
            sentiment_report=self.sentiment_report,
            news_report=self.news_report,
            fundamentals_report=self.fundamentals_report,
            total_exchanges=self._current_turns,
            bull_exchanges=bull_exchanges,
            bear_exchanges=bear_exchanges,
            debate_history=processed_debate_history,
            debate_report=escape_text_for_jinja2_temperate(self._debate_research_report)
        )
        
        return html_content
    
   