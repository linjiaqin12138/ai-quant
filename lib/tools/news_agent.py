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
from lib.utils.news import render_news_in_markdown_group_by_platform
from lib.tools.news_helper import NewsHelper
from lib.tools.information_search import unified_search
from lib.tools.ashare_stock import get_ashare_stock_info
from lib.tools.web_page_reader import WebPageReader
from lib.logger import logger

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
            <strong>标的类型:</strong> {{ symbol_type }}<br>
            {% if stock_info %}
            <strong>股票名称:</strong> {{ stock_info.stock_name }}<br>
            <strong>所属行业:</strong> {{ stock_info.stock_business }}<br>
            {% endif %}
            <strong>分析时间:</strong> {{ analysis_time }}<br>
            <strong>时间范围:</strong> {{ from_time }} 至 {{ end_time }}<br>
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
                <p><strong>获取新闻数量:</strong> {{ tool_result.news_count }} 条</p>
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
            <p>报告生成时间: {{ current_time }}</p>
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
        const markdownContent = `{{ escaped_content }}`;
        const htmlContent = marked.parse(markdownContent);
        document.getElementById('analysis-content').innerHTML = htmlContent;
        
        // 渲染每个工具的输出内容
        {% for tool_result in tool_results %}
        document.getElementById('tool-content-{{ loop.index }}').innerHTML = marked.parse(`{{ tool_result.content|replace("`", "\\`") }}`);
        {% endfor %}
    </script>
</body>
</html>
"""

# 加密货币分析提示词模板
CRYPTO_ANALYSIS_PROMPT_TEMPLATE = """
请分析加密货币标的 {symbol} 从 {from_time_str} 至今的相关新闻信息。

**分析要求：**
1. 调用 get_global_news_report 获取全球宏观经济新闻
2. 调用 get_crypto_news_from_cointime 获取加密货币专业新闻  
3. 使用 serch_engine 搜索 "{symbol}" 相关的最新消息
4. 如发现重要新闻链接，使用 read_page_content 深入了解详情

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
1. 调用 get_china_economy_news 获取中国经济新闻
2. 调用 get_global_news_report 获取全球宏观经济新闻
3. 调用 get_stock_news 获取该股票的专门新闻、该股票所属行业市场动态
4. 使用 serch_engine 搜索 "{stock_name}" 或 "{stock_code}" 相关消息
5. 如发现重要新闻链接，使用 read_page_content 深入了解详情

**重点关注：**
- 公司业务动态和经营状况
- 行业政策和监管变化
- 财务数据和业绩预期
- 市场情绪和机构观点
- 相关概念和热点炒作
- 宏观经济对该股的影响

请基于获取的信息提供专业的投资分析报告。
"""

class NewsAgent:
    """新闻分析Agent"""
    
    def __init__(
            self, 
            provider: str = "paoluz", 
            model: str = "deepseek-v3",
            web_page_reader: Optional[WebPageReader] = None
        ):
        """初始化新闻分析器"""
        self.news_helper = NewsHelper(llm_provider=provider, model=model)
        self.agent = get_agent(provider, model)
        self.web_page_reader = web_page_reader or WebPageReader(provider, model)
        # 记录工具调用结果
        self.tool_results = []
        
        # 注册工具，包装工具调用以记录结果
        self.agent.register_tool(self._wrap_tool(self.get_china_economy_news))
        self.agent.register_tool(self._wrap_tool(self.get_global_news_report))
        self.agent.register_tool(self._wrap_tool(self.get_crypto_news_from_cointime))
        self.agent.register_tool(self._wrap_tool(self.get_stock_news))
        self.agent.register_tool(self._wrap_tool(self.serch_engine))
        self.agent.register_tool(self._wrap_tool(self.read_page_content))

        self.agent.set_system_prompt(dedent("""
        你是一位专业的金融新闻分析师，擅长收集和分析各类金融市场新闻信息。

        你的主要任务是：
        1. 根据用户提供的交易标的（股票代码或加密货币交易对）智能判断标的类型
        2. 调用合适的工具获取相关新闻信息
        3. 深度分析新闻内容，提供有价值的投资参考

        **工具使用指南：**
        - `get_china_economy_news`: 获取财新中国经济新闻，适用于所有标的
        - `get_global_news_report`: 获取全球新闻和宏观经济信息，适用于所有标的  
        - `get_crypto_news_from_cointime`: 获取加密货币新闻，仅适用于加密货币标的
        - `get_stock_news`: 获取A股股票新闻，仅适用于A股股票代码
        - `serch_engine`: 通用搜索工具，可用于补充搜索相关信息
        - `read_page_content`: 阅读网页详细内容，用于深入了解重要新闻

        **分析流程：**
        1. 先判断标的类型（A股股票 vs 加密货币）
        2. 调用相应的新闻获取工具
        3. 如发现重要新闻链接，使用read_page_content深入了解
        4. 综合所有信息，提供专业的分析报告

        **报告要求：**
        - 使用中文撰写
        - 结构清晰，包含市场分析、风险提示、投资建议
        - 基于事实，客观专业
        - 重点关注对交易决策有影响的信息

        请始终保持专业和客观的态度，提供有价值的分析内容。
        """))
    
    def _wrap_tool(self, tool_func):
        """包装工具函数以记录调用结果"""
        @wraps(tool_func)
        def wrapped_tool(*args, **kwargs):
            tool_name = tool_func.__name__
            parameters = f"args={args}, kwargs={kwargs}"
            
            try:
                result = tool_func(*args, **kwargs)
                # 计算新闻数量（简单估算，按行数计算）
                # 计算新闻数量
                if tool_name in ['read_page_content', 'get_global_news_report']:
                    news_count = 0  # 这两个工具不参与新闻统计
                else:
                    # 统计类似"### [标题](链接)"格式的新闻行数
                    news_count = len(re.findall(r'#+\s*\[.*?\]\(.*?\)', result)) if result else 0
                
                self.tool_results.append({
                    "tool_name": tool_name,
                    "parameters": parameters,
                    "success": True,
                    "content": result,
                    "news_count": news_count,
                    "error_message": None
                })
                
                return result
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"工具 {tool_name} 调用失败: {error_msg}")
                
                self.tool_results.append({
                    "tool_name": tool_name,
                    "parameters": parameters,
                    "success": False,
                    "content": "",
                    "news_count": 0,
                    "error_message": error_msg
                })
                
                raise e
        
        # # 保持原函数的元数据，这很重要！
        # wrapped_tool.__name__ = tool_func.__name__
        # wrapped_tool.__doc__ = tool_func.__doc__
        
        # # 添加函数签名信息，让Agent能正确调用
        
        # wrapped_tool.__signature__ = inspect.signature(tool_func)
        # wrapped_tool.__annotations__ = getattr(tool_func, '__annotations__', {})
        
        return wrapped_tool
    
    def is_crypto_symbol(self, symbol: str) -> bool:
        """
        检测symbol类型
        """
        # 检查是否是加密货币交易对格式
        crypto_patterns = [
            r'.*USDT$',  # 以USDT结尾
            r'.*USD$',   # 以USD结尾
            r'BTC.*',    # BTC开头
            r'ETH.*',    # ETH开头
            r'.*/.*',    # 包含斜杠的交易对格式
        ]
        
        for pattern in crypto_patterns:
            if re.match(pattern, symbol.upper()):
                return True
        return False
    
    def parse_time_str(self, time_str: str) -> datetime:
        """
        解析时间字符串为datetime对象
        支持格式: '2023-10-01 12:00'
        """
        return datetime.strptime(time_str, "%Y-%m-%d %H:%M")

    def read_page_content(self, url: str) -> str:
        """
        读取网页并提取文章内容
        Args:
            url: 网页URL
        
        Returns:
            网页内容
        """
        return self.web_page_reader.read_and_extract(url, "提取正文")

    def serch_engine(self, query: str, from_time: str, max_result: int = 10) -> str:
        """
        搜索相关新闻
        Args:
            query: 搜索关键词
            from_time: 开始时间, 格式：'YYYY-MM-DD HH:MM'
            max_result: 最大结果数, 默认为10
        
        Returns:
            新闻搜索结果
        """
        # 判断一下from_time距离现在有多久，来决定time_limit参数d/w/m/y
        from_time_dt = self.parse_time_str(from_time)
        now = datetime.now()
        time_diff = now - from_time_dt
        if time_diff.days >= 365:
            time_limit = 'y'
        elif time_diff.days >= 30:
            time_limit = 'm'  # month
        elif time_diff.days >= 7:
            time_limit = 'w'  # week
        else:
            time_limit = 'd'  # day
        
        result_list = unified_search(
            query=query,
            max_results=max_result,
            time_limit=time_limit
        )

        # 修复filter问题：将filter结果转换为list
        filtered_results = list(filter(lambda x: x.timestamp >= from_time_dt, result_list))
        return render_news_in_markdown_group_by_platform({"搜索引擎": filtered_results})

    def get_global_news_report(self, from_time: str) -> str:
        """
        获取全球新闻和宏观经济信息报告
        
        Args:
            from_time: 开始时间, 格式：'YYYY-MM-DD HH:MM'
            
        Returns:
            全球新闻和宏观经济信息报告
        """
        return self.news_helper.get_global_news_report(
            from_time=self.parse_time_str(from_time)
        )
    
    def get_china_economy_news(self, from_time: str) -> str:
        """
        获取财新中国经济新闻
        
        Args:
            from_time: 开始时间, 格式：'YYYY-MM-DD HH:MM'
            
        Returns:
            中国经济新闻列表
        """
        return self.news_helper.get_ashare_news(
            from_time=self.parse_time_str(from_time), 
            platforms=['caixin']
        )

    def get_crypto_news_from_cointime(self, from_time: str) -> str:
        """
        从Cointime获取加密货币新闻
        
        Args:
            from_time: 开始时间, 格式：'YYYY-MM-DD HH:MM'
            
        Returns:
            加密货币新闻列表
        """
        return self.news_helper.get_crypto_news(
            from_time = self.parse_time_str(from_time), 
            platforms=['cointime']
        )
    
    def get_stock_news(self, stock_code: str, from_time: str) -> str:
        """
        获取指定股票代码的A股新闻
        
        Args:
            stock_code: 股票代码 如 600511
            from_time: 开始时间, 格式：'YYYY-MM-DD HH:MM'
        
        Returns:
            股票对应新闻列表
        """
        return self.news_helper.get_ashare_news(
            from_time=self.parse_time_str(from_time), 
            stock_code=stock_code, 
            platforms=['eastmoney']
        )

    def analyze_news_for(self, symbol: str, from_time: datetime) -> Dict[str, Any]:
        """
        分析指定symbol的新闻
        
        Args:
            symbol: 符号（股票代码、加密货币，如600588,BTC/USDT...）
            from_time: 开始时间
            
        Returns:
            完整的分析结果
        """
        result = {
            "success": False,
            "symbol": symbol,
            "from_time": from_time,
            "end_time": datetime.now(),
            "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tool_results": [],
            "final_analysis": "",
            "error_message": None
        }
        
        try:
            logger.info(f"开始分析 {symbol} 的新闻信息")
            
            # 重置工具调用记录
            self.tool_results = []
            
            # 判断标的类型
            is_crypto = self.is_crypto_symbol(symbol)
            result["symbol_type"] = "加密货币" if is_crypto else "A股股票"
            if not is_crypto:
                result["stock_info"] = get_ashare_stock_info(symbol)
            
            # 构建分析提示词
            from_time_str = from_time.strftime("%Y-%m-%d %H:%M")
            
            if is_crypto:
                prompt = CRYPTO_ANALYSIS_PROMPT_TEMPLATE.format(
                    symbol=symbol,
                    from_time_str=from_time_str
                )
            else:
                prompt = STOCK_ANALYSIS_PROMPT_TEMPLATE.format(
                    stock_name=result["stock_info"].get('stock_name', symbol),
                    stock_code=symbol,
                    stock_business=result["stock_info"].get('stock_business', '未知'),
                    from_time_str=from_time_str
                )
            
            # 使用Agent进行分析
            logger.info("开始调用Agent进行新闻分析")
            analysis_response = self.agent.ask(prompt, tool_use=True)
            
            result["final_analysis"] = analysis_response
            result["tool_results"] = self.tool_results
            result["success"] = True
            
            logger.info(f"完成 {symbol} 的新闻分析")
            
        except Exception as e:
            error_msg = f"分析 {symbol} 新闻失败: {str(e)}"
            logger.error(error_msg)
            logger.debug(f"错误详情: {traceback.format_exc()}")
            result["error_message"] = error_msg
            result["tool_results"] = self.tool_results
            
        return result
    
    def generate_html_report(self, analysis_result: Dict[str, Any]) -> str:
        """
        生成HTML报告
        
        Args:
            analysis_result: 分析结果
            
        Returns:
            HTML报告字符串
        """
        # 计算统计数据
        tools_called = len(analysis_result["tool_results"])
        successful_tools = sum(1 for tool in analysis_result["tool_results"] if tool["success"])
        total_news_count = sum(tool.get("news_count", 0) for tool in analysis_result["tool_results"])
        
        # 预处理markdown内容，转义特殊字符
        markdown_content = analysis_result.get("final_analysis", "")
        escaped_content = markdown_content.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
        
        # 格式化时间
        from_time_str = analysis_result["from_time"].strftime("%Y-%m-%d %H:%M")
        end_time_str = analysis_result["end_time"].strftime("%Y-%m-%d %H:%M")
        
        # 渲染HTML内容
        html_content = Template(HTML_TEMPLATE).render(
            symbol=analysis_result["symbol"],
            symbol_type=analysis_result.get("symbol_type", "未知"),
            stock_info=analysis_result.get("stock_info"),
            analysis_time=analysis_result["analysis_time"],
            from_time=from_time_str,
            end_time=end_time_str,
            tools_called=tools_called,
            successful_tools=successful_tools,
            total_news_count=total_news_count,
            tool_results=analysis_result["tool_results"],
            escaped_content=escaped_content,
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        return html_content
    
    def save_html_report(self, analysis_result: Dict[str, Any], save_folder_path: Optional[str] = None) -> str:
        """
        保存HTML报告到指定文件夹
        
        Args:
            analysis_result: 分析结果
            save_folder_path: 保存文件夹路径，如果为None则使用当前目录
            
        Returns:
            HTML文件路径
        """
        if save_folder_path is None:
            save_folder_path = os.getcwd()
        
        if not os.path.exists(save_folder_path):
            os.makedirs(save_folder_path)
        
        # 清理symbol中的特殊字符用作文件名
        safe_symbol = re.sub(r'[<>:"/\\|?*]', '_', analysis_result['symbol'])
        file_name = f"{safe_symbol}_news_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        file_path = os.path.join(save_folder_path, file_name)
        
        html_content = self.generate_html_report(analysis_result)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTML报告已保存到: {file_path}")
        return file_path




