#!/usr/bin/env python3
"""
新闻分析Agent
根据给定的symbol和时间范围，调用NewsHelper中的工具进行相关新闻的搜索和总结，并提供HTML报告
"""

from functools import wraps
import os
import re
from datetime import datetime
import traceback
from typing import Dict, Any, Optional
from textwrap import dedent
from jinja2 import Template

from lib.modules import get_agent
from lib.modules.agents.common import escape_tool_call_results
from lib.modules.news_proxy import news_proxy
from lib.modules.agents.global_news_agent import GlobalNewsAgent
from lib.utils.news import render_news_in_markdown_group_by_platform
from lib.tools.information_search import unified_search
from lib.tools.ashare_stock import get_ashare_stock_info, get_stock_news_during
from lib.modules.agents.web_page_reader import WebPageReader
from lib.logger import logger
from lib.adapter.llm import get_llm, LlmAbstract
from lib.utils.string import escape_text_for_jinja2_temperate

# HTML报告模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>新闻分析报告 - {{ symbol }}</title>
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
        .tool-section {
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .tool-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 2px solid #dee2e6;
        }
        .tool-name {
            font-weight: bold;
            color: #2980b9;
            font-size: 1.1em;
        }
        .tool-status {
            padding: 4px 12px;
            border-radius: 15px;
            font-size: 0.9em;
            font-weight: bold;
        }
        .status-success {
            background-color: #d4edda;
            color: #155724;
        }
        .status-error {
            background-color: #f8d7da;
            color: #721c24;
        }
        /* 工具输出的Markdown渲染样式 */
        .tool-content {
            background-color: white;
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 15px;
            margin-top: 10px;
            max-height: 400px;
            overflow-y: auto;
            line-height: 1.6;
        }
        .tool-content h1, .tool-content h2, .tool-content h3 {
            color: #2c3e50;
            margin-top: 20px;
            margin-bottom: 10px;
        }
        .tool-content h1 {
            border-bottom: 2px solid #3498db;
            padding-bottom: 8px;
            font-size: 1.5em;
        }
        .tool-content h2 {
            border-left: 4px solid #3498db;
            padding-left: 10px;
            font-size: 1.3em;
        }
        .tool-content h3 {
            color: #2980b9;
            font-size: 1.1em;
        }
        .tool-content h4 {
            color: #16a085;
            margin-top: 15px;
            margin-bottom: 8px;
        }
        .tool-content table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            background-color: white;
        }
        .tool-content th, .tool-content td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        .tool-content th {
            background-color: #f5f5f5;
            font-weight: bold;
        }
        .tool-content tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        .tool-content code {
            background-color: #f1f1f1;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }
        .tool-content pre {
            background-color: #f8f8f8;
            border: 1px solid #e1e1e1;
            border-radius: 5px;
            padding: 10px;
            overflow-x: auto;
            margin: 10px 0;
        }
        .tool-content blockquote {
            border-left: 4px solid #3498db;
            margin: 10px 0;
            padding: 8px 12px;
            background-color: #f0f7ff;
            font-style: italic;
        }
        .tool-content ul, .tool-content ol {
            margin: 10px 0;
            padding-left: 25px;
        }
        .tool-content li {
            margin: 5px 0;
        }
        .tool-content strong {
            color: #2c3e50;
            font-weight: bold;
        }
        .tool-content em {
            color: #7f8c8d;
            font-style: italic;
        }
        .tool-content a {
            color: #3498db;
            text-decoration: none;
        }
        .tool-content a:hover {
            text-decoration: underline;
        }
        .final-analysis {
            background-color: #e8f5e8;
            border: 1px solid #4caf50;
            padding: 25px;
            border-radius: 8px;
            margin: 30px 0;
        }
        .analysis-content {
            line-height: 1.8;
        }
        /* Markdown渲染样式优化 */
        .analysis-content h1, .analysis-content h2, .analysis-content h3 {
            color: #2c3e50;
            margin-top: 25px;
            margin-bottom: 15px;
        }
        .analysis-content h1 {
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }
        .analysis-content h2 {
            border-left: 4px solid #3498db;
            padding-left: 10px;
        }
        .analysis-content h3 {
            color: #2980b9;
        }
        .analysis-content h4 {
            color: #16a085;
            margin-top: 20px;
            margin-bottom: 10px;
        }
        .analysis-content table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background-color: white;
        }
        .analysis-content th, .analysis-content td {
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }
        .analysis-content th {
            background-color: #f5f5f5;
            font-weight: bold;
        }
        .analysis-content tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        .analysis-content code {
            background-color: #f1f1f1;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }
        .analysis-content pre {
            background-color: #f8f8f8;
            border: 1px solid #e1e1e1;
            border-radius: 5px;
            padding: 15px;
            overflow-x: auto;
            margin: 15px 0;
        }
        .analysis-content blockquote {
            border-left: 4px solid #3498db;
            margin: 15px 0;
            padding: 10px 15px;
            background-color: #f0f7ff;
            font-style: italic;
        }
        .analysis-content ul, .analysis-content ol {
            margin: 15px 0;
            padding-left: 30px;
        }
        .analysis-content li {
            margin: 8px 0;
        }
        .analysis-content strong {
            color: #2c3e50;
            font-weight: bold;
        }
        .analysis-content em {
            color: #7f8c8d;
            font-style: italic;
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
    </style>
</head>
<body>
    <div class="container">
        <h1>📰 新闻分析报告</h1>
        
        <div class="info-box">
            <strong>分析标的:</strong> {{ symbol }}<br>
            {% if symbol_name %}
            <strong>标的名称:</strong> {{ symbol_name }}<br>
            {% endif %}
            {% if symbol_business %}
            <strong>所属行业:</strong> {{ symbol_business }}<br>
            {% endif %}
            <strong>新闻起始时间:</strong> {{ from_time }} <br>
        </div>
        
        <div class="summary-stats">
            <div class="stat-card">
                <div class="stat-number">{{ tools_called }}</div>
                <div class="stat-label">工具调用次数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ successful_tools }}</div>
                <div class="stat-label">成功调用工具</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ total_news_count }}</div>
                <div class="stat-label">获取新闻数量</div>
            </div>
        </div>
        
        <h2>🔧 工具调用详情</h2>
        {% for tool_result in tool_results %}
        <div class="tool-section">
            <div class="tool-header">
                <span class="tool-name">🛠️ {{ tool_result.tool_name }}</span>
                <span class="tool-status {{ 'status-success' if tool_result.success else 'status-error' }}">
                    {{ '✅ 成功' if tool_result.success else '❌ 失败' }}
                </span>
            </div>
            <p><strong>调用参数:</strong> {{ tool_result.parameters }}</p>
            {% if tool_result.success %}
                <div class="tool-content" id="tool-content-{{ loop.index }}">
                    <!-- 工具输出内容将通过JavaScript渲染 -->
                </div>
            {% else %}
                <p><strong>错误信息:</strong> {{ tool_result.error_message }}</p>
            {% endif %}
        </div>
        {% endfor %}
        
        <div class="final-analysis">
            <h2>🤖 AI 新闻分析总结</h2>
            <div class="analysis-content" id="analysis-content"></div>
        </div>
        
        <div style="text-align: center; margin-top: 30px; color: #7f8c8d; font-size: 0.9em;">
            <p>由新闻分析Agent自动生成</p>
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
        
        // 获取原始markdown内容并渲染
        const markdownContent = `{{ markdown_content }}`;
        const htmlContent = marked.parse(markdownContent);
        document.getElementById('analysis-content').innerHTML = htmlContent;
        
        // 渲染每个工具的输出内容
        {% for tool_result in tool_results %}
            {% if tool_result.success %}
                const toolContent{{ loop.index }} = `{{ tool_result.content }}`;
                document.getElementById('tool-content-{{ loop.index }}').innerHTML = marked.parse(toolContent{{ loop.index }});
            {% endif %}
        {% endfor %}
    </script>
</body>
</html>
"""

# 加密货币分析提示词模板
CRYPTO_ANALYSIS_PROMPT_TEMPLATE = """
请分析加密货币标的 {symbol} 从 {from_time_str} 至今的相关新闻信息。

**分析要求：**
1. 使用 serch_engine 搜索 "{symbol}" 相关的最新消息
2. 如发现重要新闻链接，使用 read_page_content 深入了解详情

**重点关注：**
- {symbol} 的价格动态和技术发展
- 相关监管政策变化
- 市场情绪和投资者关注度
- 技术更新和项目进展
- 宏观经济对加密市场的影响

请基于获取的信息提供专业的投资分析报告。
"""

# A股股票分析提示词模板
STOCK_ANALYSIS_PROMPT_TEMPLATE = """
请分析A股股票 {stock_name}({stock_code})({stock_business}行业) 从 {from_time_str} 至今的相关新闻信息。

**分析要求：**
1. 使用 serch_engine 搜索 "{stock_name}" 或 "{stock_code}" 相关消息
2. 如发现重要新闻链接，使用 read_page_content 深入了解详情

**重点关注：**
- 公司业务动态和经营状况
- 行业政策和监管变化
- 财务数据和业绩预期
- 市场情绪和机构观点
- 相关概念和热点炒作
- 宏观经济对该股的影响

请基于获取的信息提供专业的投资分析报告。
"""

SYS_PROMPT = """
你是一位专业的金融新闻分析师，擅长为某个投资标的收集和分析各类金融市场新闻信息。

你的主要任务是：
1. 首先阅读系统已为你收集的相关新闻（包括标的本身及相关行业新闻）
2. 在理解已有新闻基础上，调用合适的工具（如搜索引擎、网页阅读器等）
3. 深度分析新闻内容，提供有价值的投资参考

**工具使用指南：**
- `serch_engine`: 通用搜索工具，可用于补充搜索相关信息
- `read_page_content`: 阅读网页详细内容，用于深入了解重要新闻

**分析流程：**
1. 先仔细阅读系统已收集的新闻内容，理解核心信息
2. 针对不明确或需要补充的点，使用serch_engine等工具进一步搜索相关行业、市场、政策等新闻
3. 如重要新闻描述不清晰，使用read_page_content深入了解详情
4. 综合所有信息，提供专业的分析报告

**报告要求：**
- 使用中文撰写
- 结构清晰，包含市场分析、风险提示、投资建议
- 基于事实，客观专业
- 重点关注对交易决策有影响的信息

请始终保持专业和客观的态度，提供有价值的分析内容。
"""

class NewsAgent:
    """新闻分析Agent"""
    
    def __init__(
            self, 
            llm: LlmAbstract = None,
            web_page_reader: Optional[WebPageReader] = None,
            global_news_reporter: Optional[GlobalNewsAgent] = None
        ):
        """初始化新闻分析器"""
        self.llm = llm or get_llm("paoluz", "deepseek-v3", temperature=0.2)
        self.agent = get_agent(llm=self.llm)
        self.web_page_reader = web_page_reader or WebPageReader(llm=self.llm)
        self.global_news_reporter = global_news_reporter or GlobalNewsAgent(
            llm=self.llm,
            web_page_reader=WebPageReader(llm=self.llm)
        )
        self.agent.register_tool(self._serch_engine)
        self.agent.register_tool(self._read_page_content)
        self.agent.set_system_prompt(SYS_PROMPT)

        # 开始分析之后才会有值，开始分析前清空
        self._current_symbol = None
        self._current_symbol_name = ""
        self._symbol_business_name = ""
        self._global_news_report = ""
        self._platform_news = {}
        self._from_time = None
        self._user_prompt = ""
        self._analysis_report = ""
    
    @property
    def _is_crypto(self) -> bool:
        return 'USDT' in self._current_symbol

    def _read_page_content(self, url: str) -> str:
        """
        读取网页并提取文章内容
        Args:
            url: 网页URL
        
        Returns:
            网页内容
        """
        return self.web_page_reader.read_and_summary(url)

    def _serch_engine(self, query: str, max_result: int = 10) -> str:
        """
        搜索相关新闻
        Args:
            query: 搜索关键词
            max_result: 最大结果数, 默认为10
        
        Returns:
            新闻搜索结果
        """
        # 判断一下from_time距离现在有多久，来决定time_limit参数d/w/m/y
        now = datetime.now()
        time_diff = now - self._from_time
        if time_diff.days >= 30:
            time_limit = 'y'  # month
        elif time_diff.days >= 7:
            time_limit = 'm'  # week
        elif time_diff.days >= 1:
            time_limit = 'w'  # week
        else:
            time_limit = 'd'  # day
        
        result_list = unified_search(
            query=query,
            max_results=max_result,
            time_limit=time_limit
        )

        # 修复filter问题：将filter结果转换为list
        filtered_results = list(filter(lambda x: x.timestamp >= self._from_time, result_list))
        if self._platform_news.get("Search"):
            self._platform_news["Search"].extend(filtered_results)
        else:
            self._platform_news["Search"] = filtered_results
        return render_news_in_markdown_group_by_platform({"搜索引擎": filtered_results})
    
    def _init_analyzing(self, symbol: str, from_time: datetime):
        self.agent.clear_context()
        self._current_symbol = symbol
        self._from_time = from_time
        self._global_news_report = self.global_news_reporter.get_recent_global_news_report()
        from_time_str = from_time.strftime("%Y-%m-%d %H:%M")
        
        if 'USDT' in self._current_symbol:
            # 如果是加密货币，初始化平台新闻
            self._symbol_name = symbol.split('/')[0]  # 提取币种名称
            self._symbol_business_name = ""
            self._user_prompt = CRYPTO_ANALYSIS_PROMPT_TEMPLATE.format(
                symbol=symbol,
                from_time_str=from_time_str
            )
            self._platform_news = {
                "cointime": news_proxy.get_news_from(
                    start=from_time, 
                    platform='cointime'
                )
            }
        else:
            stock_info = get_ashare_stock_info(symbol)
            self._symbol_name = stock_info["stock_name"]
            self._symbol_business_name = stock_info["stock_business"]
            self._user_prompt = STOCK_ANALYSIS_PROMPT_TEMPLATE.format(
                stock_name=self._symbol_name,
                stock_code=symbol,
                stock_business=self._symbol_business_name,
                from_time_str=from_time_str
            )
            self._platform_news = {
                "caixin": news_proxy.get_news_from(
                    start=from_time, 
                    platform='caixin'
                ),
                "eastmoney": get_stock_news_during(self._current_symbol, from_time)
            }

        self._user_prompt += f"\n\n{render_news_in_markdown_group_by_platform(self._platform_news)}"

    def analyze_news(self, symbol: str, from_time: datetime) -> str:
        """
        分析指定symbol的新闻
        
        Args:
            symbol: 符号（股票代码、加密货币，如600588,BTC/USDT...）
            from_time: 开始时间
            
        Returns:
            完整的分析报告
        """
        
        logger.info(f"开始分析 {symbol} 的新闻信息")
        self._init_analyzing(symbol, from_time)
        self._analysis_report = self.agent.ask(self._user_prompt, tool_use=True)
        return self._analysis_report

    def generate_html_report(self) -> str:
        """
        生成HTML报告
        
        Args:
            analysis_result: 分析结果
            
        Returns:
            HTML报告字符串
        """
        # 计算统计数据
        assert self._analysis_report, "请先调用analyze_news方法进行分析"
        
        # 格式化时间
        from_time_str = self._from_time.strftime("%Y-%m-%d %H:%M")
        total_news_count = sum(len(news) for news in self._platform_news.values())
        # 渲染HTML内容
        html_content = Template(HTML_TEMPLATE).render(
            symbol=self._current_symbol,
            symbol_name= self._symbol_name,
            symbol_business=self._symbol_business_name,
            from_time=from_time_str,
            tools_called=len(self.agent.tool_call_results),
            successful_tools=len([t for t in self.agent.tool_call_results if t["success"]]),
            total_news_count=total_news_count,
            tool_results=escape_tool_call_results(self.agent.tool_call_results.copy()),
            markdown_content=escape_text_for_jinja2_temperate(self._analysis_report),
        )
        
        return html_content
 