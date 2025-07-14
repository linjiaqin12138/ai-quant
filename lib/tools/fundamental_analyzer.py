#!/usr/bin/env python3
"""
上市公司基本面数据分析工具
使用akshare获取财务数据和股东变动数据，结合搜索工具和网页阅读工具进行综合基本面分析
"""

import json
import os
from datetime import datetime
from typing import Optional, Dict, Any
from textwrap import dedent
import traceback

from jinja2 import Template
from lib.adapter.apis import read_web_page_by_jina
from lib.adapter.llm.interface import LlmAbstract
from lib.modules import get_agent
from lib.tools.information_search import unified_search

from lib.tools.ashare_stock import (
    get_comprehensive_financial_data,
    get_shareholder_changes_data,
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
            <strong>股票类型:</strong> {{ stock_type }}<br>
            <strong>分析时间:</strong> {{ analysis_time }}<br>
        </div>
        
        <div class="data-source">
            <strong>📋 数据来源说明:</strong><br>
            • 财务数据来源: akshare接口<br>
            • 数据获取时间: {{ analysis_time }}<br>
            • 分析工具: AI基本面分析Agent<br>
        </div>
        
        <div class="analysis-report">
            <h3>🤖 AI基本面分析报告</h3>
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
        const markdownContent = `{{ escaped_content }}`;
        const htmlContent = marked.parse(markdownContent);
        document.getElementById('analysis-content').innerHTML = htmlContent;
    </script>
</body>
</html>
"""

# 系统提示模板
FUNDAMENTAL_ANALYZER_SYSTEM_PROMPT = """你是一个专业的基本面分析师，专门分析上市公司的基本面数据。

你的任务是：
1. 使用akshare工具获取{company_name}（股票代码：{stock_code}，行业：{business}）的最新财务数据和股东变动数据
2. 综合分析资产负债表、利润表、现金流量表和股东结构变化
3. 搜索相关的基本面新闻、分析报告和行业动态
4. 提供专业的基本面健康度评估和投资价值分析

请使用以下工具：
- unified_search: 搜索相关基本面新闻、行业分析和公司研报
- read_web_page: 读取具体网页内容

基本面分析时请重点关注：
- 财务健康度分析（资产负债结构、偿债能力、营运能力、盈利能力）
- 现金流量质量分析
- 股东结构变化分析（大股东增减持、机构投资者变化）
- 治理结构评估（股权集中度、股东稳定性）
- 成长性分析（收入增长、利润增长、ROE趋势）
- 估值水平分析（PE、PB、PEG等估值指标）
- 行业地位和竞争优势分析
- 与同行业公司对比分析
- **重要：在分析报告中必须标注每个数据的来源和时间**

请用中文回复，提供详细的基本面分析报告。"""

class FundamentalAnalyzer:
    """上市公司基本面数据分析器"""
    
    def __init__(self, llm: LlmAbstract):
        """
        初始化基本面分析器
        
        Args:
            llm: LLM实例
        """
        self.agent = get_agent(llm = llm)
        self.agent.register_tool(unified_search)
        self.agent.register_tool(read_web_page_by_jina)
        logger.info(f"已注册工具: {list(self.agent.tools.keys())}")

    def _init_fundamental_agent_context(self, stock_info: dict, stock_code: str = ""):
        """
        创建基本面数据分析Agent
        
        Args:
            stock_info: 股票信息字典(行业、股票名称)
            stock_code: 股票代码
            
        Returns:
            配置好的Agent实例
        """
        # 创建Agent实例
        company_name = stock_info.get("stock_name", "未知公司")
        # 设置系统提示
        system_prompt = FUNDAMENTAL_ANALYZER_SYSTEM_PROMPT.format(
            company_name=company_name,
            stock_code=stock_code,
            business=stock_info.get("stock_business", "未知行业")
        )
        self.agent.set_system_prompt(system_prompt)
        # 调用工具获取financial_data和股东变动数据，直接喂给大模型
        financial_data = get_comprehensive_financial_data(stock_code)
        share_holder_change_data = get_shareholder_changes_data(stock_code)
        self.agent.chat_context.append({
            "role": "user",
            "content": f"财务数据（来源akshare）: {json.dumps(financial_data, indent=2, ensure_ascii=False)}"
                       f"股东变动数据（来源akshare）: {json.dumps(share_holder_change_data, indent=2, ensure_ascii=False)}"
        })
    
    def _generate_analysis_prompt(self, company_name: str, stock_code: str) -> str:
        """
        生成基本面分析提示
        
        Args:
            company_name: 公司名称
            stock_code: 股票代码
            
        Returns:
            分析提示文本
        """
        return dedent(f"""
        请帮我全面分析{company_name}（股票代码：{stock_code}）的最新基本面数据。

        使用unified_search工具搜索相关的基本面分析和新闻，如：
           - "{company_name} {stock_code} 基本面分析"
           - "{company_name} 财务报告 解读"
           - "{company_name} 股东变动 增减持"
           - "{company_name} 行业地位 竞争优势"
           - "{company_name} 估值分析"

        如果搜索结果中有具体的分析文章链接，使用read_web_page工具读取详细内容

        最后提供综合基本面分析报告，参考以下结构模板进行适当调整：

        ## {company_name}（{stock_code}）基本面分析报告

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

        **数据来源**: akshare财务数据接口，报告期

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

        **数据来源**: akshare股东变动数据，报告期

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
        - **对比数据来源**: [标注数据来源]

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

        ### 9. 数据来源汇总
        - akshare财务数据接口
        - akshare股东变动数据接口  
        - 相关新闻和分析文章链接
        - 数据获取时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

        **重要说明**: 
        - 所有财务和股东数据来源于akshare接口
        - 分析基于最新可获得的数据
        - 请结合最新的市场环境和行业趋势进行判断
        - 投资有风险，决策需谨慎

        请确保：
        1. 所有数值都要具体标注（不要使用[具体数值]这样的占位符）
        2. 计算所有提及的财务比率和估值指标
        3. 充分利用股东变动数据进行治理分析
        4. 提供具体的分析结论和投资建议
        5. 标注所有数据的来源和时间
        6. 如果某些信息无法获取/未提供，就不需要在报告中写出，也不要在报告中指出未提供
        """)
    
    def analyze_fundamental_data(self, symbol: str = "") -> Dict[str, Any]:
        """
        分析指定公司的基本面数据
        
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
            
            logger.info(f"开始分析{company_name}（{symbol}）的基本面数据")
            
            # 创建Agent
            self._init_fundamental_agent_context(result['stock_info'], symbol)
            
            # 生成分析提示
            analysis_prompt = self._generate_analysis_prompt(company_name, symbol)
            
            # 执行分析
            logger.info("正在使用AI Agent分析基本面数据...")
            response = self.agent.ask(analysis_prompt, tool_use=True)
            
            result["success"] = True
            result["analysis_report"] = response
            
            logger.info(f"✅ {company_name}基本面分析完成")
            
        except Exception as e:
            logger.error(f"分析过程中发生错误: {str(e)}")
            logger.debug(f"错误详情: {traceback.format_exc()}")
        
        return result
    
    def generate_html_report(self, analysis_result: Dict[str, Any]) -> str:
        """
        生成HTML基本面分析报告
        
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
        保存HTML基本面分析报告到文件
        
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
        report_filename = f"{safe_company_name}_{stock_code}_fundamental_analysis_{timestamp}.html"
        report_path = os.path.join(save_folder_path, report_filename)
        
        try:
            html_content = self.generate_html_report(analysis_result)
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"💾 基本面分析HTML报告已保存到: {report_path}")
            return report_path
            
        except Exception as e:
            logger.error(f"保存HTML报告失败: {str(e)}")
            return None

        """
        保存基本面分析报告到文件（HTML格式）
        
        Args:
            analysis_result: 分析结果
            save_folder_path: 保存文件夹路径，如果为None则使用当前目录
            
        Returns:
            报告文件路径，如果保存失败返回None
        """
        return self.save_html_report(analysis_result, save_folder_path)