#!/usr/bin/env python3
"""
上市公司基本面数据分析工具
使用akshare获取财务数据和股东变动数据，结合搜索工具和网页阅读工具进行综合基本面分析
"""

import json
import os
from datetime import datetime
from typing import Optional
from textwrap import dedent, indent

from jinja2 import Template

from lib.utils.string import escape_text_for_jinja2_temperate
from lib.adapter.apis import read_web_page_by_jina
from lib.adapter.llm.interface import LlmAbstract
from lib.modules import get_agent
from lib.modules.agents.web_page_reader import WebPageReader
from lib.tools.cache_decorator import use_cache
from lib.tools.information_search import unified_search
from lib.tools.ashare_stock import (
    get_comprehensive_financial_data,
    get_shareholder_changes_data,
    get_ashare_stock_info,
    AShareStockInfo
)
from lib.logger import logger
from lib.utils.news import render_news_in_markdown_group_by_platform

# HTML报告模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>基本面数据分析报告 - {{ company_name }}({{ stock_code }})</title>
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
        h3 {
            color: #2980b9;
            margin-top: 25px;
            margin-bottom: 10px;
        }
        .info-box {
            background-color: #ecf0f1;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 25px;
            border-left: 4px solid #3498db;
        }
        .financial-summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 25px 0;
        }
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }
        .metric-value {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 5px;
        }
        .metric-label {
            font-size: 14px;
            opacity: 0.9;
        }
        .analysis-report {
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            padding: 25px;
            border-radius: 8px;
            margin: 25px 0;
        }
        .data-source {
            background-color: #e8f5e8;
            border: 1px solid #4caf50;
            padding: 15px;
            border-radius: 5px;
            margin: 15px 0;
            font-size: 0.9em;
        }
        .warning-box {
            background-color: #fff3cd;
            border: 1px solid #ffc107;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
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
        .footer {
            text-align: center;
            margin-top: 40px;
            color: #7f8c8d;
            font-size: 0.9em;
            border-top: 1px solid #ecf0f1;
            padding-top: 20px;
        }
        /* 工具调用结果样式 */
        .tool-section {
            background-color: #f9f9ff;
            border: 1px solid #d1e7dd;
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
        }
        .tool-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .tool-name {
            font-weight: bold;
            color: #333;
        }
        .tool-status {
            padding: 3px 8px;
            border-radius: 12px;
            font-size: 0.9em;
        }
        .status-success {
            background-color: #d1e7dd;
            color: #155724;
        }
        .status-error {
            background-color: #f8d7da;
            color: #721c24;
        }
        .error-message {
            color: #721c24;
            background-color: #f8d7da;
            padding: 10px;
            border-radius: 5px;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 基本面数据分析报告</h1>
        
        <div class="info-box">
            <h3>📈 公司基本信息</h3>
            <strong>公司名称:</strong> {{ company_name }}<br>
            <strong>股票代码:</strong> {{ stock_code }}<br>
            <strong>所属行业:</strong> {{ business }}<br>
        </div>

        <div class="analysis-report">
            <h3>🤖 AI基本面分析报告</h3>
            <div class="analysis-content" id="analysis-content"></div>
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
                <div class="error-message">
                    <strong>错误信息:</strong> {{ tool_result.error_message }}
                </div>
            {% endif %}
        </div>
        {% endfor %}
        
        <div class="warning-box">
            <strong>⚠️ 重要声明:</strong><br>
            • 本报告基于公开财务数据进行分析，仅供参考<br>
            • 投资决策需要综合考虑多种因素<br>
            • 财务数据存在滞后性，请结合最新市场情况判断<br>
            • 投资有风险，决策需谨慎<br>
        </div>
        
        <div class="footer">
            <p>报告生成时间: {{ analysis_time }}</p>
            <p>由基本面数据分析Agent自动生成</p>
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
        const markdownContent = `{{ escaped_content | escape }}`;
        const htmlContent = marked.parse(markdownContent);
        document.getElementById('analysis-content').innerHTML = htmlContent;
        
        // 渲染工具调用结果
        {% for tool_result in tool_results %}
        {% if tool_result.success %}
        (function() {
            const content = `{{ tool_result.content | escape }}`.trim();
            const html = marked.parse(content);
            document.getElementById('tool-content-{{ loop.index }}').innerHTML = html;
        })();
        {% endif %}
        {% endfor %}
    </script>
</body>
</html>
"""

# 系统提示模板
FUNDAMENTAL_ANALYZER_SYSTEM_PROMPT = """
你是一个专业的基本面分析师，专门分析上市公司的基本面数据。

你的任务是：
1. 分析某上市公司的最新财务数据和股东变动数据
2. 综合分析资产负债表、利润表、现金流量表和股东结构变化
3. **必须使用搜索工具**获取相关的基本面新闻、分析报告和行业动态
4. 提供专业的基本面健康度评估和投资价值分析

**重要：你必须使用以下工具来补充和验证分析**：
- _search_information: 搜索相关基本面新闻、行业分析和公司研报
- _read_web_page: 读取搜索结果中的分析文章链接正文

**必须执行的搜索策略**：
1. 搜索公司最新财务报告解读和分析
2. 搜索行业分析和公司竞争地位信息
3. 搜索公司估值分析和投资建议
4. 搜索股东变动和治理结构相关信息
5. 搜索行业发展趋势和政策影响

**搜索关键词示例**：
    - "<公司名> 2024年 财务报告 解读"
    - "<公司名> 基本面分析 投资价值"
    - "<公司名> 股东变动 增减持"
    - "<公司名> 行业地位 竞争优势"
    - "<公司名> 估值分析 PE PB"
    - "<公司名> 同行业对比 市场份额"

基本面分析时请重点关注：
- 财务健康度分析（资产负债结构、偿债能力、营运能力、盈利能力）
- 现金流量质量分析
- 股东结构变化分析（大股东增减持、机构投资者变化）
- 治理结构评估（股权集中度、股东稳定性）
- 成长性分析（收入增长、利润增长、ROE趋势）
- 估值水平分析（PE、PB、PEG等估值指标）
- 行业地位和竞争优势分析
- 与同行业公司对比分析

**报告要求**：
1. 必须使用搜索工具获取补充信息，不要直接说"数据未提供"
2. 所有数值都要具体标注，标注所有数据的来源和时间
3. 如果通过搜索仍无法获取某些信息，直接省略相关章节，不要说明未提供
4. 充分利用股东变动数据进行治理分析
5. 报告结构要完整，但只写有内容的章节

请用中文回复，提供详细的基本面分析报告，参考以下结构：

---
## <公司>(<股票代码>)基本面分析报告

### 1. 公司基本信息
- 公司名称和行业
- 主营业务和商业模式
- 行业地位和市场份额

### 2. 财务健康度分析
#### 2.1 资产负债表分析
- 总资产规模: [具体数值]
- 资产结构分析（流动资产、固定资产占比）
- 负债结构分析（流动负债、长期负债）
- 所有者权益分析
- 财务比率分析（资产负债率、流动比率、速动比率）

#### 2.2 利润表分析
- 营业收入及增长趋势: [具体数值和增长率]
- 盈利能力分析（毛利率、净利率、ROE、ROA）
- 成本控制能力
- 盈利质量评估

#### 2.3 现金流量表分析
- 经营活动现金流: [具体数值]
- 投资活动现金流分析
- 筹资活动现金流分析
- 现金流质量评估（现金流与净利润匹配度）

### 3. 股东结构与治理分析
#### 3.1 股东结构分析
- 前十大股东持股情况
- 股权集中度分析
- 机构投资者持股比例

#### 3.2 股东变动分析
- 近期大股东增减持情况
- 机构投资者进出动态
- 股东变动对公司治理的影响
- 股东变动的原因分析

#### 3.3 公司治理评估
- 股权结构的合理性
- 治理结构的透明度
- 管理层稳定性

### 4. 成长性分析
#### 4.1 历史成长性
- 收入增长趋势（3-5年）
- 利润增长趋势
- ROE变化趋势
- 市场份额变化

#### 4.2 成长质量评估
- 成长的可持续性
- 成长驱动因素分析
- 与行业增长对比

#### 4.3 未来成长预期
- 基于基本面的成长预测
- 主要成长风险因素

### 5. 估值分析
#### 5.1 估值水平
- PE估值（当前PE、历史PE区间）
- PB估值
- PEG估值（如适用）
- EV/EBITDA等其他估值指标

#### 5.2 估值合理性
- 与历史估值对比
- 与同行业公司估值对比
- 基于DCF的内在价值评估（如可行）

### 6. 行业与竞争分析
#### 6.1 行业基本面
- 行业发展趋势
- 行业景气度
- 政策环境影响

#### 6.2 竞争地位分析
- 在行业中的地位
- 核心竞争优势
- 与主要竞争对手对比

### 7. 风险评估
#### 7.1 财务风险
- 主要财务风险点
- 偿债能力风险
- 现金流风险

#### 7.2 经营风险
- 行业风险
- 竞争风险
- 政策风险
- 其他特定风险

#### 7.3 治理风险
- 股东结构风险
- 管理层风险
- 信息披露风险

### 8. 投资价值评估
#### 8.1 投资亮点
- 主要投资价值点
- 核心竞争优势
- 成长潜力

#### 8.2 投资建议
- 基于基本面的投资建议
- 目标价格区间（如可评估）
- 投资时机建议
- 适合的投资者类型

#### 8.3 关键监控指标
- 需要持续关注的财务指标
- 需要跟踪的经营指标
- 重要的市场和政策变化

---

**开始分析前，请先执行以下搜索任务**：
1. 搜索公司最新财务报告和分析师解读
2. 搜索行业分析和竞争对手信息
3. 搜索公司估值分析和投资建议
4. 根据搜索结果进行深入分析

记住：每个章节的数据都要标注来源和时间，如果某个章节缺乏信息就直接省略，不要说明未提供。
"""

class FundamentalAnalyzer:
    """上市公司基本面数据分析器"""
    
    def __init__(
            self, 
            llm: LlmAbstract, 
            web_page_reader: Optional[WebPageReader] = None
        ):
        """
        初始化基本面分析器
        
        Args:
            llm: LLM实例
        """
        self._agent = get_agent(llm = llm)
        self._web_page_reader = web_page_reader
        if not web_page_reader:
            self._web_page_reader = WebPageReader(llm)

        self._agent.register_tool(self._search_information)
        self._agent.register_tool(self._read_web_page)
        logger.info(f"已注册工具: {list(self._agent.tools.keys())}")

        # 开始分析之后才会有值，开始分析前清空
        self._stock_code: str = ""
        self._stock_info: Optional[AShareStockInfo] = None
        self._report_result: Optional[str] = None

    def _search_information(self, query: str) -> str:
        """
        使用搜索引擎搜索过去一年时间范围内的10条相关信息

        Args:
            query: 搜索关键词

        Returns:
            返回搜索结果的Markdown格式字符串
        """
        return render_news_in_markdown_group_by_platform(
            {
                "搜索结果": unified_search(
                    query, 
                    10, 
                    region="zh-cn", 
                    time_limit="y"
                )
            }
        )
    def _read_web_page(self, url: str) -> str:
        """
        读取网页内容
        
        Args:
            url: 网页URL
            
        Returns:
            网页正文内容
        """
        return self._web_page_reader.read_and_extract(url, "提取正文")
        
    def _init_analyzing(self, symbol: str = ""):
        """根据要分析的symbol初始化类的属性"""
        self._stock_code = symbol
        self._stock_info = get_ashare_stock_info(symbol)
        company_name = self._stock_info["stock_name"]
        # 设置系统提示
        system_prompt = FUNDAMENTAL_ANALYZER_SYSTEM_PROMPT.format(
            company_name=company_name,
            stock_code=self._stock_code,
            business=self._stock_info["stock_business"]
        )
        self._agent.set_system_prompt(system_prompt)
        self._report_result = None
    
    def _generate_user_prompt(self) -> str:
        company_name = self._stock_info["stock_name"]
        stock_code = self._stock_code

        financial_data = get_comprehensive_financial_data(self._stock_code)
        share_holder_change_data = get_shareholder_changes_data(self._stock_code)

        return dedent(f"""
        请帮我全面分析{company_name}（股票代码：{stock_code}）的最新基本面数据。

        财务数据（来源akshare）:
        ```json
        {indent(json.dumps(financial_data, indent=2, ensure_ascii=False), " " * 8)}
        ```

        股东变动数据（来源akshare）: 
        ```json
        {indent(json.dumps(share_holder_change_data, indent=2, ensure_ascii=False), " " * 8)}
        ```
        """)
    
    def analyze_fundamental_data(self, symbol: str = "") -> str:
        """
        分析指定公司的基本面数据
        
        Args:
            symbol: 股票代码
            
        Returns:
            分析结果字符串
        """

        # 初始化Agent
        self._init_analyzing(symbol)

        logger.info(f"开始分析{self._stock_info['stock_name']}({symbol})的基本面数据")

        # 执行分析
        logger.info("正在使用AI Agent分析基本面数据...")
        prompt = self._generate_user_prompt()
        result = self._agent.ask(prompt, tool_use=True)
        
        # 保存分析结果用于后续生成HTML报告
        self._report_result = result
        
        logger.info(f"✅ {self._stock_info['stock_name']}基本面分析完成")
        return result

    def generate_html_report(self) -> str:
        """
        生成HTML基本面分析报告
        """
        error_msg = "请先调用analyze_fundamental_data方法获取分析结果"
        assert self._stock_info is not None, error_msg
        assert self._report_result is not None, error_msg
        
        self._agent.tool_call_results
        tools_results = self._agent.tool_call_results.copy()
        for tool_result in tools_results:
            # 确保工具调用结果的content字段存在
            if tool_result["success"]:
                tool_result["content"] = escape_text_for_jinja2_temperate(tool_result["content"])
            if not tool_result["success"]:
                tool_result["error_message"] = escape_text_for_jinja2_temperate(tool_result.get("error_message", ""))

        # 渲染HTML内容
        return Template(HTML_TEMPLATE).render(
            company_name=self._stock_info["stock_name"],
            stock_code=self._stock_code,
            business=self._stock_info["stock_business"],
            analysis_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            escaped_content=escape_text_for_jinja2_temperate(self._report_result),
            tool_results=tools_results
        )