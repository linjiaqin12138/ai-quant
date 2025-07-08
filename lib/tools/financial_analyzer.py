#!/usr/bin/env python3
"""
上市公司财务数据分析工具
使用akshare获取财务数据，结合搜索工具和网页阅读工具进行综合分析
"""

import json
import os
from datetime import datetime
from typing import Optional, Dict, Any
from textwrap import dedent
import traceback

from jinja2 import Template
from lib.adapter.llm import get_agent
from lib.tools.information_search import unified_search, read_web_page
from lib.tools.ashare_stock import (
    get_comprehensive_financial_data,
    get_ashare_stock_info
)
from lib.logger import logger

# HTML报告模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>财务数据分析报告 - {{ company_name }}({{ stock_code }})</title>
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
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 财务数据分析报告</h1>
        
        <div class="info-box">
            <h3>📈 公司基本信息</h3>
            <strong>公司名称:</strong> {{ company_name }}<br>
            <strong>股票代码:</strong> {{ stock_code }}<br>
            <strong>所属行业:</strong> {{ business }}<br>
            <strong>股票类型:</strong> {{ stock_type }}<br>
            <strong>分析时间:</strong> {{ analysis_time }}<br>
        </div>
        
        <div class="data-source">
            <strong>📋 数据来源说明:</strong><br>
            • 财务数据来源: akshare接口<br>
            • 数据获取时间: {{ analysis_time }}<br>
            • 分析工具: AI财务分析Agent<br>
        </div>
        
        <div class="analysis-report">
            <h3>🤖 AI财务分析报告</h3>
            <div class="analysis-content" id="analysis-content"></div>
        </div>
        
        <div class="warning-box">
            <strong>⚠️ 重要声明:</strong><br>
            • 本报告基于公开财务数据进行分析，仅供参考<br>
            • 投资决策需要综合考虑多种因素<br>
            • 财务数据存在滞后性，请结合最新市场情况判断<br>
            • 投资有风险，决策需谨慎<br>
        </div>
        
        <div class="footer">
            <p>报告生成时间: {{ current_time }}</p>
            <p>由财务数据分析Agent自动生成</p>
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
    </script>
</body>
</html>
"""

# 系统提示模板
FINANCIAL_ANALYZER_SYSTEM_PROMPT = """你是一个专业的财务分析师，专门分析上市公司的财务数据。

你的任务是：
1. 使用akshare工具获取{company_name}（股票代码：{stock_code}，行业：{business}）的最新财务数据
2. 重点分析资产负债表、利润表和现金流量表
3. 搜索相关的财务新闻和分析报告
4. 提供专业的财务健康度评估和投资建议

请使用以下工具：
- get_comprehensive_financial_data: 获取公司综合财务数据
- get_ashare_stock_info: 获取公司基本信息
- unified_search: 搜索相关财务新闻和分析
- read_web_page: 读取具体网页内容

分析时请注意：
- 资产负债结构分析
- 偿债能力评估
- 营运能力分析
- 盈利能力分析
- 现金流量健康度
- 与同行业公司对比
- **重要：在分析报告中必须标注每个数据的来源和时间**

请用中文回复，提供详细的财务分析报告。"""

class FinancialAnalyzer:
    """上市公司财务数据分析器"""
    
    def __init__(self, provider: str = "paoluz", model: str = "deepseek-v3"):
        """
        初始化财务分析器
        
        Args:
            provider: LLM提供商
            model: 使用的模型
        """
        self.provider = provider
        self.model = model
    
    def get_stock_code_by_name(self, company_name: str) -> str:
        """
        根据公司名称获取股票代码
        
        Args:
            company_name: 公司名称
            
        Returns:
            股票代码，如果未找到返回空字符串
        """
        return self.stock_mapping.get(company_name, "")
    
    def create_financial_agent(self, stock_info: dict, stock_code: str = ""):
        """
        创建财务数据分析Agent
        
        Args:
            stock_info: 股票信息字典(行业、股票名称)
            stock_code: 股票代码
            
        Returns:
            配置好的Agent实例
        """
        # 创建Agent实例
        agent = get_agent(self.provider, self.model)
        company_name = stock_info.get("stock_name", "未知公司")
        # 设置系统提示
        system_prompt = FINANCIAL_ANALYZER_SYSTEM_PROMPT.format(
            company_name=company_name,
            stock_code=stock_code,
            business=stock_info.get("stock_business", "未知行业")
        )
        agent.set_system_prompt(system_prompt)
        # 调用工具获取financial_data，直接喂给大模型
        financial_data = get_comprehensive_financial_data(stock_code)
        agent.chat_context.append({
            "role": "user",
            "content": f"财务数据（来源skshare）: {json.dumps(financial_data, indent=2, ensure_ascii=False)}"
        })
        agent.register_tool(unified_search)
        agent.register_tool(read_web_page)
        
        logger.info(f"✅ {company_name}财务数据分析Agent创建成功")
        logger.info(f"已注册工具: {list(agent.llm.tools.keys())}")
        
        return agent
    
    def generate_analysis_prompt(self, company_name: str, stock_code: str) -> str:
        """
        生成财务分析提示
        
        Args:
            company_name: 公司名称
            stock_code: 股票代码
            
        Returns:
            分析提示文本
        """
        return dedent(f"""
        请帮我全面分析{company_name}（股票代码：{stock_code}）的最新财务数据。

        使用unified_search工具搜索相关的财务分析和新闻，如：
           - "{company_name} {stock_code} 财务分析"
           - "{company_name} 资产负债表 分析"
           - "{company_name} 财务报告 解读"

        如果搜索结果中有具体的分析文章链接，使用read_web_page工具读取详细内容

        最后提供以下结构的综合分析报告：

        ## {company_name}（{stock_code}）财务数据分析报告

        ### 1. 公司基本信息
        - 公司名称和行业
        - 主营业务

        ### 2. 资产负债表分析
        #### 2.1 资产结构分析
        - 总资产规模: [具体数值]
        - 流动资产占比: [计算百分比]
        - 固定资产占比: [计算百分比]
        - 主要资产项目分析（货币资金、应收账款、存货、固定资产等）

        #### 2.2 负债结构分析
        - 总负债规模: [具体数值]
        - 流动负债占比: [计算百分比]
        - 长期负债占比: [计算百分比]
        - 主要负债项目分析（短期借款、长期借款、应付账款等）

        #### 2.3 所有者权益分析
        - 所有者权益总额: [具体数值]
        - 股本结构
        - 资本公积和盈余公积情况
        - 未分配利润分析

        #### 2.4 财务比率分析
        - 资产负债率: [计算公式和结果]
        - 流动比率: [计算公式和结果]
        - 速动比率: [计算公式和结果]
        - 权益乘数: [计算公式和结果]

        ### 3. 利润表分析
        #### 3.1 收入分析
        - 营业收入: [具体数值]
        - 收入增长率: [同比分析]
        - 主要收入来源

        #### 3.2 成本和费用分析
        - 营业成本: [具体数值]
        - 毛利率: [计算结果]
        - 期间费用分析

        #### 3.3 盈利能力分析
        - 营业利润: [具体数值]
        - 净利润: [具体数值]
        - 净利率: [计算结果]
        - 每股收益: [具体数值]

        **数据来源**: akshare - 利润表数据，报告期

        ### 4. 现金流量表分析
        #### 4.1 经营活动现金流
        - 经营活动产生的现金流量净额: [具体数值]
        - 经营现金流与净利润的匹配度

        #### 4.2 投资活动现金流
        - 投资活动产生的现金流量净额: [具体数值]
        - 主要投资项目分析

        #### 4.3 筹资活动现金流
        - 筹资活动产生的现金流量净额: [具体数值]
        - 筹资结构分析

        **数据来源**: akshare - 现金流量表数据，报告期

        ### 5. 财务健康度评估
        #### 5.1 偿债能力评估
        - 短期偿债能力（流动比率、速动比率）
        - 长期偿债能力（资产负债率、利息保障倍数）

        #### 5.2 营运能力评估
        - 总资产周转率
        - 存货周转率
        - 应收账款周转率

        #### 5.3 盈利能力评估
        - ROE（净资产收益率）
        - ROA（总资产收益率）
        - 毛利率和净利率趋势

        #### 5.4 现金流健康度
        - 现金流量结构分析
        - 现金流充足性评估

        ### 6. 同行业对比分析
        - 与同行业主要公司的财务指标对比
        - 行业地位分析
        - **对比数据来源**: [如果有的话，标注来源]

        ### 7. 风险提示
        - 主要财务风险点
        - 需要关注的财务指标
        - 潜在的经营风险

        ### 8. 投资建议
        - 基于财务数据的投资建议
        - 估值水平分析
        - 投资风险评估

        ### 9. 数据来源汇总
        - akshare财务数据接口
        - 相关新闻和分析文章链接
        - 数据获取时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

        **重要说明**: 
        - 所有财务数据来源于akshare接口
        - 分析基于最新可获得的数据
        - 请结合最新的市场环境和行业趋势进行判断
        - 投资有风险，决策需谨慎

        请确保：
        1. 所有数值都要具体标注（不要使用[具体数值]这样的占位符）
        2. 计算所有提及的财务比率
        3. 提供具体的分析结论
        4. 标注所有数据的来源和时间
        5. 如果某些信息无法获取/未提供，就不需要在报告中写出，也不要在报告中指出未提供
        """)
    
    def analyze_financial_data(self, symbol: str = "") -> Dict[str, Any]:
        """
        分析指定公司的财务数据
        
        Args:
            symbol: 股票代码
            
        Returns:
            分析结果字典
        """
        result = {
            "success": False,
            "symbol": symbol,
            "analysis_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        try:
            # 获取股票基本信息
            result['stock_info'] = get_ashare_stock_info(symbol)
            company_name = result['stock_info'].get("stock_name", "未知公司")
            
            logger.info(f"开始分析{company_name}（{symbol}）的财务数据")
            
            # 创建Agent
            agent = self.create_financial_agent(result['stock_info'], symbol)
            
            # 生成分析提示
            analysis_prompt = self.generate_analysis_prompt(company_name, symbol)
            
            # 执行分析
            logger.info("正在使用AI Agent分析财务数据...")
            response = agent.ask(analysis_prompt, tool_use=True)
            
            result["success"] = True
            result["analysis_report"] = response
            
            logger.info(f"✅ {company_name}财务分析完成")
            
        except Exception as e:
            logger.error(f"分析过程中发生错误: {str(e)}")
            logger.debug(f"错误详情: {traceback.format_exc()}")
        
        return result
    
    def generate_html_report(self, analysis_result: Dict[str, Any]) -> str:
        """
        生成HTML财务分析报告
        
        Args:
            analysis_result: 分析结果
            
        Returns:
            HTML报告字符串
        """
        stock_code = analysis_result["symbol"]
        company_name = analysis_result["stock_info"].get("stock_name", "未知公司")
        business = analysis_result["stock_info"].get("stock_business", "未知行业")
        
        # 预处理markdown内容，转义特殊字符
        markdown_content = analysis_result["analysis_report"]
        # 替换反引号和反斜杠
        escaped_content = markdown_content.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
        
        # 渲染HTML内容
        html_content = Template(HTML_TEMPLATE).render(
            company_name=company_name,
            stock_code=stock_code,
            business=business,
            stock_type=analysis_result["stock_info"].get("stock_type", "未知"),
            analysis_time=analysis_result["analysis_time"],
            escaped_content=escaped_content,
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        return html_content
    
    def save_html_report(self, analysis_result: Dict[str, Any], save_folder_path: Optional[str] = None) -> Optional[str]:
        """
        保存HTML财务分析报告到文件
        
        Args:
            analysis_result: 分析结果
            save_folder_path: 保存文件夹路径，如果为None则使用当前目录
            
        Returns:
            报告文件路径，如果保存失败返回None
        """
        if not analysis_result.get("success"):
            logger.error("分析结果不成功，无法保存报告")
            return None
        
        if save_folder_path is None:
            save_folder_path = os.getcwd()
        
        if not os.path.exists(save_folder_path):
            os.makedirs(save_folder_path)
        
        # 生成文件名
        company_name = analysis_result["stock_info"].get("stock_name", "未知公司")
        stock_code = analysis_result["symbol"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_company_name = company_name.replace(" ", "_").replace("/", "_")
        report_filename = f"{safe_company_name}_{stock_code}_financial_analysis_{timestamp}.html"
        report_path = os.path.join(save_folder_path, report_filename)
        
        try:
            html_content = self.generate_html_report(analysis_result)
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"💾 财务分析HTML报告已保存到: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"保存HTML报告失败: {str(e)}")
            return None

    def save_analysis_report(self, analysis_result: Dict[str, Any], save_folder_path: Optional[str] = None) -> Optional[str]:
        """
        保存分析报告到文件（HTML格式）
        
        Args:
            analysis_result: 分析结果
            save_folder_path: 保存文件夹路径，如果为None则使用当前目录
            
        Returns:
            报告文件路径，如果保存失败返回None
        """
        return self.save_html_report(analysis_result, save_folder_path)