#!/usr/bin/env python3
"""
Bull Bear Researcher Agent
牛熊辩论研究员Agent，通过两个对立观点的Agent进行多轮辩论分析
"""

import os
import re
import json
from pathlib import Path
from textwrap import dedent
import traceback
from typing import Dict, Any, Optional, List, TypedDict
from datetime import datetime
from jinja2 import Template

from lib.adapter.llm.interface import LlmAbstract
from lib.adapter.vector_db import VectorDatabaseAbstract
from lib.modules import get_agent
from lib.tools.common import get_ohlcv_history
from lib.tools.information_search import unified_search
from lib.tools.web_page_reader import WebPageReader
from lib.tools.investment_reflector import InvestmentReflector, ReflectionData, ReflectionResult
from lib.logger import logger


from lib.utils.number import change_rate

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
            <strong>LLM提供商:</strong> {{ provider }}<br>
            <strong>使用模型:</strong> {{ model }}<br>
            <strong>分析时间:</strong> {{ analysis_time }}<br>
            {% if early_end %}
            <strong>提前结束:</strong> 是 - {{ early_end_reason }}<br>
            {% endif %}
        </div>
        
        {% if early_end %}
        <div class="early-end-notice">
            <h3>⚠️ 辩论提前结束</h3>
            <p>{{ early_end_reason }}</p>
        </div>
        {% endif %}
        
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
            <p>报告生成时间: {{ current_time }}</p>
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
        const summaryContent = `{{ escaped_summary }}`;
        document.getElementById('summary-content').innerHTML = marked.parse(summaryContent);
        
        // 渲染每轮辩论内容
        {% for entry in debate_history %}
        const debateContent{{ loop.index }} = `{{ entry.escaped_content }}`;
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
            - 每个论点必须先使用`unified_search`搜索相关新闻报道或分析报告
            - 使用`read_web_page`深入阅读搜索结果中的具体链接，获取详细信息
            - 引用时必须使用具体的新闻/报告URL，不能仅引用公司官网或平台首页
            - 即便你已经知道某个信息，也必须通过工具搜索找到对应的具体出处
        3. 在构建论点时：
            - 每个论点都必须有对应的具体新闻/报告URL支持
            - 如果搜索不到具体出处，就不要使用这个论点
            - 不要捏造或篡改任何数据和事实
        4. 当你的工具搜索结果找不到有力的反驳证据，且对方论点确实合理时，请输出：
            <DEBATE_CONCEDE>我承认对方的观点更有说服力</DEBATE_CONCEDE>

        **可用工具：**
        - `unified_search`: 搜索相关信息来支持你的论点
        - `read_web_page`: 深入阅读网页内容获取详细信息

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
            - 每个论点必须先使用`unified_search`搜索相关新闻报道或分析报告
            - 使用`read_web_page`深入阅读搜索结果中的具体链接，获取详细信息
            - 引用时必须使用具体的新闻/报告URL，不能仅引用公司官网或平台首页
            - 即便你已经知道某个信息，也必须通过工具搜索找到对应的具体出处
        3. 在构建论点时：
            - 每个论点都必须有对应的具体新闻/报告URL支持
            - 如果搜索不到具体出处，就不要使用这个论点
            - 不要捏造或篡改任何数据和事实
        4. 当你的工具搜索结果找不到有力的反驳证据，且对方论点确实合理时，请输出：
            <DEBATE_CONCEDE>我承认对方的观点更有说服力</DEBATE_CONCEDE>

        **可用工具：**
        - `unified_search`: 搜索相关信息来支持你的论点
        - `read_web_page`: 深入阅读网页内容获取详细信息

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

class DebateState(TypedDict):
    """牛熊辩论结果的类型定义"""
    symbol: Optional[str]
    planned_rounds: int
    actual_rounds: int
    early_end: bool
    early_end_reason: Optional[str]
    summary: Optional[str]
    context: str
    success: bool
    error_message: Optional[str]
    debate_history: List[DebateHistoryItem]  # 可选，在某些情况下会添加

class Reports(TypedDict):
    """辩论报告的类型定义"""
    market_research_report: str
    sentiment_report: str
    news_report: str
    fundamentals_report: str

class DebateRecord(TypedDict):
    """牛熊辩论记录的类型定义"""
    debate_result: DebateState
    reports: Reports

def _search_information(query: str, max_results: int = 10) -> str:
    """
    搜索相关信息的工具函数
    
    Args:
        query: 搜索关键词
        max_results: 最大结果数量
    
    Returns:
        搜索结果的文本描述
    """
    try:
        news_list = unified_search(query, max_results=max_results)
        if not news_list:
            return f"未找到关于'{query}'的相关信息"
        
        result = f"关于'{query}'的搜索结果：\n\n"
        for i, news in enumerate(news_list, 1):
            result += f"{i}. **{news.title}**\n"
            result += f"   来源: {news.platform}\n"
            result += f"   链接: {news.url}\n"
            result += f"   描述: {news.description}\n"
            result += f"   时间: {news.timestamp.strftime('%Y-%m-%d %H:%M')}\n\n"
        
        return result
    except Exception as e:
        return f"搜索失败: {str(e)}"

class BullBearResearcher:
    """牛熊辩论研究员"""
    
    def __init__(
            self,
            symbol: str,
            provider: str = 'paoluz',
            model: str = 'deeepseek-v3',
            record_folder = 'data/debate_records',
            rounds: int = 1,
            reflect_top_k: int = 3,
            web_page_reader: Optional[WebPageReader] = None,
            vector_db: Optional[VectorDatabaseAbstract] = None
        ):

        """
        初始化牛熊辩论研究员
        
        Args:
            symbol: 股票或资产的符号
            record_folder: 记录文件夹路径
            rounds: 辩论轮数 (1-5)
            web_page_reader: 可选的网页阅读器
        """
        self.symbol = symbol
        self.provider = provider
        self.model = model
        self.rounds = max(1, min(5, rounds))  # 确保轮数在1-5之间
        self.reflect_top_k = max(1, min(10, reflect_top_k))  # 确保反思记录数量在1-10之间
        self.record_folder = record_folder
        self.debate_result: DebateState = {
            "symbol": symbol,
            "planned_rounds": self.rounds,
            "actual_rounds": 0,
            "early_end": False,
            "success": False,
            "debate_history": [],
            "context": ""
        }

        # 创建两个Agent
        self.bull_agent = get_agent(provider, model, temperature=0.7)
        self.bear_agent = get_agent(provider, model, temperature=0.7)
        self.decision_agent = get_agent(provider, model, temperature=0.7)
        self.web_page_reader = web_page_reader or WebPageReader(provider=provider, model=model)
        
        # 待添加
        self.market_research_report = ""
        self.sentiment_report = ""
        self.news_report = ""
        self.fundamentals_report = ""

        # 创建三个反思器，分别对应三个agent
        self.bull_reflector = InvestmentReflector(
            provider=provider,
            model=model,
            index_name="bull-agent-reflections",
            embedding_dimension=1536,
            vector_db=vector_db
        )
        self.bear_reflector = InvestmentReflector(
            provider=provider,
            model=model,
            index_name="bear-agent-reflections",
            embedding_dimension=1536,
            vector_db=vector_db
        )
        self.decision_reflector = InvestmentReflector(
            provider=provider,
            model=model,
            index_name="decision-agent-reflections",
            embedding_dimension=1536,
            vector_db=vector_db
        )
    
        # 设置系统提示
        self.bull_agent.register_tool(_search_information)
        self.bull_agent.register_tool(self._read_web_page)
        self.bear_agent.register_tool(_search_information)
        self.bear_agent.register_tool(self._read_web_page)
    
    def _set_system_prompts(self):
        """设置牛熊双方的系统提示"""
        context = self._format_context()
        
        # 为每个agent搜索相似的反思记录作为参考
        bull_reflections = ""
        bear_reflections = ""

        # 搜索多头相似反思
        bull_similar = self.bull_reflector.search_similar_reflections(
            situation=f"{context}",
            top_k=self.reflect_top_k
        )
        if bull_similar:
            for i, reflection in enumerate(bull_similar[:3], 1):
                bull_reflections += f"{i}. {reflection['content']}...\n"
        
        # 搜索空头相似反思
        bear_similar = self.bear_reflector.search_similar_reflections(
            situation=context,
            top_k=self.reflect_top_k
        )
        if bear_similar:
            for i, reflection in enumerate(bear_similar[:3], 1):
                bear_reflections += f"{i}. {reflection['content']}...\n"

        bull_prompt = BULL_SYS_PROMPT.format(context=context, past_memory=bull_reflections)
        bear_prompt = BEAR_SYS_PROMPT.format(context=context, past_memory=bear_reflections)
        self.bull_agent.set_system_prompt(bull_prompt)
        self.bear_agent.set_system_prompt(bear_prompt)
        self.decision_agent.set_system_prompt(SUMMARY_SYS_PROMPT)

    def _read_web_page(self, url: str) -> str:
        """
        读取网页内容
        
        Args:
            url: 网页链接
            
        Returns:
            网页内容
        """
        return self.web_page_reader.read_and_extract(url, "提取正文内容")
    
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
            for entry in self.debate_result['debate_history']
        ])
    
    def _format_context(self) -> str:
        """格式化上下文信息"""
        return dedent(
            f"""
                市场研究报告：{self.market_research_report}
                社交媒体情绪报告：{self.sentiment_report}
                最新世界事务新闻：{self.news_report}
                公司基本面报告：{self.fundamentals_report}
            """
        )
    
    def _add_history(self, round_num: int, role: str, content: str):
        """添加辩论历史"""
        self.debate_result['debate_history'].append({
            "round": round_num,
            "role": role,
            "content": content
        })
    
    def _check_debate_concede(self, content: str) -> bool:
        """检查是否有认输标识"""
        return bool(re.search(r'<DEBATE_CONCEDE>.*?</DEBATE_CONCEDE>', content, re.IGNORECASE | re.DOTALL))
    
    def start_debate(self) -> Dict[str, Any]:
        """
        开始牛熊辩论
        
        Args:
            symbol: 标的名称
            
        Returns:
            辩论结果字典
        """
        logger.info(f"🎯 开始牛熊辩论，共{self.rounds}轮")
        try:
            # 使用symbol重新设置系统提示词，包含相似反思记录
            self._set_system_prompts()
            self.debate_result["context"] = self._format_context()
            symbol = self.debate_result["symbol"]
            # 初始化Agent，添加上下文信息
            round_num = 1

            logger.info(f"第{round_num}轮辩论开始...")

            logger.info(f"🐂 多头分析中...")
            bull_response = self.bull_agent.ask(f"请开始发表你的观点，分析投资价值", tool_use=True)
            self._add_history(round_num, "多头", bull_response)
            
            # 检查多头是否认输
            if self._check_debate_concede(bull_response):
                logger.info(f"🏁 辩论提前结束：多头分析师认输")
                # 直接生成总结
                self.debate_result.update({
                    "summary": self._generate_summary(),
                    "success": True,
                    "actual_rounds": round_num,
                    "early_end": True,
                    "early_end_reason": "多头分析师在第1轮认输"
                })
                return self.debate_result

            logger.info(f"🐻 空头分析中...")
            bear_response = self.bear_agent.ask(f"请基于多头的观点进行反驳，分析{symbol}的投资风险：{bull_response}", tool_use=True)
            self._add_history(round_num, "空头", bear_response)
            
            # 检查空头是否认输
            if self._check_debate_concede(bear_response):
                logger.info(f"🏁 辩论提前结束：空头分析师认输")
                # 直接生成总结
                self.debate_result.update({
                    "summary": self._generate_summary(),
                    "success": True,
                    "actual_rounds": round_num,
                    "early_end": True,
                    "early_end_reason": "空头分析师在第1轮认输"
                })
                return self.debate_result
            
            round_num += 1

            while round_num <= self.rounds:
                logger.info(f"第{round_num}轮辩论开始...")

                logger.info(f"🐂 多头分析中...")
                bull_response = self.bull_agent.ask(f"请基于空头的观点进行反驳：{bear_response}", tool_use=True)
                self._add_history(round_num, "多头", bull_response)
                
                # 检查多头是否认输
                if self._check_debate_concede(bull_response):
                    logger.info(f"🏁 辩论提前结束：多头分析师认输")
                    self.debate_result.update({
                        "summary": self._generate_summary(),
                        "success": True,
                        "actual_rounds": round_num,
                        "early_end": True,
                        "early_end_reason": f"多头分析师在第{round_num}轮认输"
                    })
                    break

                logger.info(f"🐻 空头分析中...")
                bear_response = self.bear_agent.ask(f"请基于多头的观点进行反驳：{bull_response}", tool_use=True)
                self._add_history(round_num, "空头", bear_response)
                
                # 检查空头是否认输
                if self._check_debate_concede(bear_response):
                    logger.info(f"🏁 辩论提前结束：空头分析师认输")
                    self.debate_result.update({
                        "summary": self._generate_summary(),
                        "success": True,
                        "actual_rounds": round_num,
                        "early_end": True,
                        "early_end_reason": f"空头分析师在第{round_num}轮认输"
                    })
                    break
                
                round_num += 1
            
            # 如果没有提前结束，设置实际轮数
            if not self.debate_result["early_end"]:
                self.debate_result["actual_rounds"] = self.rounds
            
            # 生成总结
            logger.info("📋 生成辩论总结...")
            self.debate_result.update({
                "summary": self._generate_summary(),
                "success": True
            })
            logger.info(f"📋 辩论总结完成")

            logger.info(f"保存辩论记录")
            self.save_debate_records()
        except Exception as e:
            error_msg = f"辩论过程中出错: {str(e)}"
            self.debate_result.update({
                "error_message": error_msg
            })
            logger.error(error_msg)
            logger.debug(f"错误详情: {traceback.format_exc()}")
        
        return self.debate_result
    
    def _generate_summary(self) -> str:
        """
        生成辞论总结并自动保存辩论记录
        """
        # 创建专门用于总结的Agent
        # 格式化辩论历史为文本
        debate_history_text = self._format_debate_history()
        context = self._format_context()
        similar_experience = self.decision_reflector.search_similar_reflections(
            situation=context,
            top_k=3
        )
        past_memory_str = ""
        if similar_experience:
            for i, reflection in enumerate(similar_experience[:3], 1):
                past_memory_str += f"{i}. {reflection['content']}\n"

        summary = self.decision_agent.ask(
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
        return summary
    
    def generate_html_report(self) -> str:
        """
        生成HTML报告
        
        Args:
            analysis_result: 分析结果
            
        Returns:
            HTML报告字符串
        """
        # 计算统计数据
        analysis_result = self.debate_result
        assert analysis_result['success']
        
        total_exchanges = len(analysis_result["debate_history"])
        bull_exchanges = sum(1 for entry in analysis_result["debate_history"] if entry["role"] == "多头")
        bear_exchanges = sum(1 for entry in analysis_result["debate_history"] if entry["role"] == "空头")
        
        # 处理辩论内容，转义特殊字符
        processed_debate_history = []
        for entry in analysis_result["debate_history"]:
            processed_entry = entry.copy()
            # 转义markdown内容
            content = entry["content"].replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
            processed_entry["escaped_content"] = content
            processed_debate_history.append(processed_entry)
        
        # 转义总结内容
        summary_content = analysis_result.get("summary", "")
        escaped_summary = summary_content.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
        
        # 渲染HTML内容
        html_content = Template(HTML_TEMPLATE).render(
            symbol=analysis_result["symbol"],
            planned_rounds=analysis_result["planned_rounds"],
            actual_rounds=analysis_result["actual_rounds"],
            early_end=analysis_result["early_end"],
            early_end_reason=analysis_result.get('early_end_reason'),
            provider=self.provider,
            model=self.model,
            analysis_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            market_research_report=self.market_research_report,
            sentiment_report=self.sentiment_report,
            news_report=self.news_report,
            fundamentals_report=self.fundamentals_report,
            total_exchanges=total_exchanges,
            bull_exchanges=bull_exchanges,
            bear_exchanges=bear_exchanges,
            debate_history=processed_debate_history,
            escaped_summary=escaped_summary,
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        return html_content
    
    def save_html_report(self, save_folder_path: Optional[str] = None) -> str:
        """
        保存HTML报告到文件
        
        Args:
            analysis_result: 分析结果
            save_folder_path: 保存文件夹路径，如果为None则使用当前目录
            
        Returns:
            报告文件路径
        """
        if save_folder_path is None:
            save_folder_path = os.getcwd()
        
        if not os.path.exists(save_folder_path):
            os.makedirs(save_folder_path)
        
        # 生成文件名
        analysis_result = self.debate_result
        assert analysis_result['success']
        symbol = analysis_result["symbol"].replace("/", "_").replace("\\", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"bull_bear_debate_{symbol}_{timestamp}.html"
        report_path = os.path.join(save_folder_path, report_filename)
        
        try:
            html_content = self.generate_html_report()
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"💾 牛熊辩论HTML报告已保存到: {report_path}")
            logger.info(f"✅ 辩论报告已导出到: {report_path}")
            return report_path
            
        except Exception as e:
            error_msg = f"导出报告失败: {str(e)}"
            logger.error(error_msg)
            return ""
    
    def reflect(
        self,
        days_ago: int = 1
    ) -> Dict[str, ReflectionResult]:
        """
        对三个agent的发言进行反思分析
        
        Args:
            days_ago: 距离决策日期过去的天数
            
        Returns:
            包含三个agent反思结果的字典
        """
        
        try:
            ohlcv_history = get_ohlcv_history(self.symbol, limit=days_ago + 1)
            actual_return = change_rate(ohlcv_history[0].close, ohlcv_history[-1].close)
            logger.info(f"🔍 开始对{self.symbol}的辩论进行反思分析（{days_ago}天后收益率：{actual_return:.2%}）")

            # 计算历史日期
            historical_date = ohlcv_history[0].timestamp
            # 尝试加载历史辩论记录
            historical_record: DebateRecord = self.load_debate_records(historical_date)
            if historical_record is None:
                logger.warning(f"未找到{historical_date.strftime('%Y-%m-%d')}的辩论记录")
                return
            reports = historical_record.get('reports')
            self.add_fundamentals_report(reports.get('fundamentals_report', ''))
            self.add_news_report(reports.get('news_report', ''))
            self.add_market_research_report(reports.get('market_research_report', ''))
            self.add_sentiment_report(reports.get('sentiment_report', ''))
            # 使用历史记录
            context = self._format_context()
            self.debate_result: DebateState = historical_record['debate_result']
            debate_history = self.debate_result["debate_history"]
            
            if not self.debate_result['success']:
                logger.warning("⚠️ 历史辩论记录未成功完成，无法进行反思")
                return

            logger.info(f"📂 使用{historical_date.strftime('%Y-%m-%d')}的历史辩论记录进行反思")
            # 1. 反思多头分析师的发言
            logger.info("🐂 反思多头分析师的发言...")
            bull_opinions = [entry['content'] for entry in debate_history if entry['role'] == '多头']
            result = self.bull_reflector.reflect_on_decision(
                ReflectionData(
                    situation=context,
                    analysis_opinion="\n".join(bull_opinions),
                    days_past=days_ago,
                    return_loss_percentage=actual_return,
                    decision_date=historical_date
                )
            )
            if result.success:
                logger.info(f"✅ 多头分析师反思完成")
                logger.debug(result.reflection_content)
        
            # 2. 反思空头分析师的发言
            logger.info("🐻 反思空头分析师的发言...")
            bear_opinions = [entry['content'] for entry in debate_history if entry['role'] == '空头']
            result = self.bear_reflector.reflect_on_decision(
                ReflectionData(
                    situation=context,
                    analysis_opinion="\n".join(bear_opinions),
                    days_past=days_ago,
                    return_loss_percentage=actual_return,
                    decision_date=historical_date
                )
            )
            if result.success:
                logger.info("✅ 空头分析师反思完成")
                logger.debug(result.reflection_content)
            
            # 3. 反思决策分析师的总结
            logger.info("👨‍⚖️反思决策分析师的总结...")
            result = self.decision_reflector.reflect_on_decision(
                ReflectionData(
                    situation=context,
                    analysis_opinion=self.debate_result["summary"],
                    days_past=days_ago,
                    return_loss_percentage=actual_return,
                    decision_date=historical_date
                )
            )
            if result.success:
                logger.info("✅ 决策分析师反思完成")
                logger.debug(result.reflection_content)
            
        except Exception as e:
            logger.error(f"反思过程中发生错误: {e}")
            logger.debug(traceback.format_exc())
    
    def save_debate_records(self):
        """
        保存当天的辩论记录和报告到文件
        
        Args:
            symbol: 分析标的
            summary: 总结内容
        """
        decision_date = datetime.now()
            
        # 创建保存目录
        date_str = decision_date.strftime('%Y-%m-%d')
        save_dir = Path(f"{self.record_folder}/{date_str}")
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # 构建完整的记录数据
        record_data = {
            "debate_result": self.debate_result,
            "reports": {
                "market_research_report": self.market_research_report,
                "sentiment_report": self.sentiment_report,
                "news_report": self.news_report,
                "fundamentals_report": self.fundamentals_report,
            }
        }
        
        # 保存到JSON文件
        symbol_clean = self.symbol.replace("/", "_").replace("\\", "_")
        record_file = save_dir / f"{symbol_clean}_debate_record.json"
        
        try:
            with open(record_file, 'w', encoding='utf-8') as f:
                json.dump(record_data, f, ensure_ascii=False, indent=4)
            
            logger.info(f"📝 辩论记录已保存到: {record_file}")
            
        except Exception as e:
            logger.error(f"保存辩论记录时发生错误: {e}")
            logger.debug(traceback.format_exc())
    
    def load_debate_records(self, date: datetime) -> Optional[DebateRecord]:
        """
        从文件加载指定日期的辩论记录
        
        Args:
            symbol: 分析标的
            target_date: 目标日期
            
        Returns:
            辩论记录数据，如果文件不存在返回None
        """
        date_str = date.strftime('%Y-%m-%d')
        symbol_clean = self.symbol.replace("/", "_").replace("\\", "_")
        record_file = Path(f"{self.record_folder}/{date_str}/{symbol_clean}_debate_record.json")
        
        if not record_file.exists():
            logger.warning(f"辩论记录文件不存在: {record_file}")
            return None
        
        try:
            with open(record_file, 'r', encoding='utf-8') as f:
                record_data = json.load(f)
            
            logger.info(f"📂 已加载辩论记录: {record_file}")
            return record_data
            
        except Exception as e:
            logger.error(f"加载辩论记录时发生错误: {e}")
            logger.debug(traceback.format_exc())
            return None