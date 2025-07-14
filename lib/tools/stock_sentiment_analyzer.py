#!/usr/bin/env python3
"""
股票市场情绪分析工具
通过分析雪球和股吧评论区数据，生成0-100的情绪评分和对应等级
"""

import os
import re
from datetime import datetime
import traceback
from typing import List, Dict, Any, Optional, Tuple
from textwrap import dedent

from jinja2 import Template
from lib.adapter.llm import get_llm, get_llm_direct_ask
from lib.adapter.llm.interface import LlmAbstract
from lib.utils.string import has_json_features
from lib.tools.json_fixer import JsonFixer
from lib.tools.web_page_reader import WebPageReader
from lib.tools.ashare_stock import get_ashare_stock_info, determine_exchange
from lib.logger import logger
from lib.utils.string import extract_json_string
from lib.utils.decorators import with_retry
from lib.model.error import LlmReplyInvalid

# HTML报告模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>股票市场情绪分析报告 - {{ stock_symbol }}</title>
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
        .sentiment-score {
            text-align: center;
            padding: 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 15px;
            margin: 20px 0;
            color: white;
        }
        .score-circle {
            width: 150px;
            height: 150px;
            border-radius: 50%;
            background-color: {{ sentiment_color }};
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 20px;
            font-size: 48px;
            font-weight: bold;
            color: white;
        }
        .sentiment-level {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 10px;
        }
        .info-box {
            background-color: #ecf0f1;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        .url-section {
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
        }
        .comment {
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
        }
        .comment-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            padding-bottom: 8px;
            border-bottom: 1px solid #dee2e6;
        }
        .author {
            font-weight: bold;
            color: #2980b9;
        }
        .time {
            color: #7f8c8d;
            font-size: 0.9em;
        }
        .content {
            color: #2c3e50;
            margin-bottom: 10px;
        }
        .stats {
            display: flex;
            gap: 15px;
            font-size: 0.9em;
            color: #7f8c8d;
        }
        .sentiment-analysis {
            background-color: #e8f5e8;
            border: 1px solid #4caf50;
            padding: 20px;
            border-radius: 8px;
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
        .raw-response {
            background-color: #2c3e50;
            color: #ecf0f1;
            padding: 20px;
            border-radius: 5px;
            overflow-x: auto;
            white-space: pre-wrap;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 股票市场情绪分析报告</h1>
        
        <div class="info-box">
            <strong>股票代码:</strong> {{ stock_symbol }}<br>
            <strong>股票名称:</strong> {{ stock_name }}<br>
            <strong>股票类型:</strong> {{ stock_type }}<br>
            <strong>所属行业:</strong> {{ stock_business }}<br>
            <strong>交易所:</strong> {{ exchange }}<br>
            <strong>分析时间:</strong> {{ analysis_time }}<br>
            <strong>总评论数:</strong> {{ total_comments }} 条<br>
            <strong>分析页面:</strong> {{ url_results_count }} 个
        </div>
        
        <div class="sentiment-score">
            <div class="score-circle">{{ sentiment_score }}</div>
            <div class="sentiment-level">情绪等级: {{ sentiment_level }}</div>
            <div>市场情绪评分: {{ sentiment_score }}/100</div>
        </div>
        
        <div class="sentiment-analysis">
            <h3>🤖 AI情绪分析报告</h3>
            <div class="analysis-content" id="analysis-content"></div>
        </div>
        
        <h2>📱 各平台评论统计</h2>
        {% for url_result in url_results %}
        <div class="url-section">
            <h3>平台 {{ loop.index }}: {{ url_result.platform }}</h3>
            <p><strong>URL:</strong> <a href="{{ url_result.url }}" target="_blank">{{ url_result.url }}</a></p>
            <p><strong>评论数量:</strong> {{ url_result.comments_count }} 条</p>
            
            <h4>评论内容:</h4>
            {% if url_result.comments %}
                {% for comment in url_result.comments %}
                <div class="comment">
                    <div class="comment-header">
                        <span class="author">👤 {{ comment.get('author', '未知用户') }}</span>
                        <span class="time">🕐 {{ comment.get('time', '未知时间') }}</span>
                    </div>
                    <div class="content">{{ comment.get('content', '无内容') }}</div>
                    <div class="stats">
                        <span>👍 {{ comment.get('likes', 0) }} 赞</span>
                        <span>💬 {{ comment.get('replies', 0) }} 回复</span>
                    </div>
                </div>
                {% endfor %}
            {% else %}
                <p><em>未获取到评论内容</em></p>
            {% endif %}
        </div>
        {% endfor %}
        
        <div style="text-align: center; margin-top: 30px; color: #7f8c8d; font-size: 0.9em;">
            <p>报告生成时间: {{ current_time }}</p>
            <p>由股票市场情绪分析Agent自动生成</p>
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
    </script>
</body>
</html>
"""

# 评论提取器系统提示词模板
COMMENT_EXTRACTOR_SYS_PROMPT_TEMPLATE = """
你是一个专业的股票数据分析助手，擅长从网页内容中提取和分析股票相关信息。
现在时间是{curr_time_str}。
请按照以下要求操作：
1. 仔细分析页面内容，找出评论区域
2. 提取过去24小时内的评论，包括：
   - 评论者用户名/昵称
   - 评论时间
   - 评论内容
   - 点赞数、阅读数、回复数等互动数据（如果有）
3. 以JSON数组格式返回所有评论数据

如果页面没有评论区或评论为空，请说明具体情况。

Response Format Example (请严格follow)
[
    {{
        "author": "用户名",
        "time": "评论时间",
        "content": "评论内容",
        "likes": 0,
        "replies": 0
    }},
    ...
]
"""

# 情绪分析器系统提示词模板
SENTIMENT_ANALYZER_SYS_PROMPT_TEMPLATE = """
你是一个专业的股票市场情绪分析专家，擅长分析投资者评论并评估市场情绪。

你的任务是：
1. 分析用户提供的股票评论数据
2. 综合考虑评论内容、点赞数、回复数等因素
3. 生成0-100的情绪评分和对应等级
4. 提供详细的分析报告

情绪等级划分：
- 0-20: 极度恐慌 (Extreme Fear)
- 21-40: 恐慌 (Fear)  
- 41-60: 中等 (Neutral)
- 61-80: 贪婪 (Greed)
- 81-100: 极度贪婪 (Extreme Greed)

分析维度：
1. 评论情绪倾向：积极/消极/中性评论的比例
2. 互动热度：点赞数、回复数反映的关注度
3. 情绪强度：使用的词汇强度和情绪表达
4. 市场预期：对未来走势的预测倾向

请在最后用XML标签给出结果：
<sentiment_score>数值</sentiment_score>
<sentiment_level>等级</sentiment_level>
"""

LLM_RETRY_TIME = 1

class StockSentimentAnalyzer:
    """股票市场情绪分析器"""
    
    def __init__(
            self, 
            llm: LlmAbstract = None,
            web_page_reader: Optional[WebPageReader] = None,
            json_fixer: Optional[JsonFixer] = None
        ):
        """初始化分析器"""
        self.llm = llm or get_llm("paoluz", "deepseek-v3", temperature=0.2)
        
        # 创建评论提取工具
        self.comment_extractor = get_llm_direct_ask(
            system_prompt=COMMENT_EXTRACTOR_SYS_PROMPT_TEMPLATE.format(curr_time_str=datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            llm = self.llm,
            response_format="json_object"
        )
        
        # 创建情绪分析工具
        self.sentiment_analyzer = get_llm_direct_ask(
            system_prompt=SENTIMENT_ANALYZER_SYS_PROMPT_TEMPLATE,
            llm = self.llm
        )

        self.web_page_reader = web_page_reader or WebPageReader(llm=self.llm)
        # Fix Json Tool
        self.fix_json_tool = json_fixer.fix if json_fixer else JsonFixer(llm=self.llm).fix
    
    def _validate_comment_schema(self, comment: Any) -> bool:
        """
        验证评论数据的schema是否符合要求
        
        Args:
            comment: 评论数据对象
            
        Returns:
            bool: 是否符合schema要求
        """
        if not isinstance(comment, dict):
            return False
        
        # 检查必需字段
        required_fields = ['author', 'time', 'content']
        for field in required_fields:
            if field not in comment:
                return False
            if not isinstance(comment[field], str):
                return False
            if not comment[field].strip():  # 不能为空字符串
                return False
        
        # 检查可选的数值字段
        optional_numeric_fields = ['likes', 'replies']
        for field in optional_numeric_fields:
            if field in comment:
                if not isinstance(comment[field], (int, float)):
                    # 尝试转换为数值
                    try:
                        comment[field] = int(comment[field])
                    except (ValueError, TypeError):
                        comment[field] = 0
        
        return True
    
    def build_ashare_stock_dicussion_urls(self, stock_symbol: str, exchange: str) -> List[str]:
        """
        构建股票页面URL
        
        Args:
            stock_symbol: 股票代码
            exchange: 交易所代码(SH/SZ)
            
        Returns:
            URL列表
        """
        urls = []
        
        # 雪球URL - 需要加上交易所前缀
        xueqiu_symbol = f"{exchange}{stock_symbol}"
        xueqiu_url = f"https://xueqiu.com/S/{xueqiu_symbol}"
        urls.append(xueqiu_url)
        
        # 东方财富股吧URL
        guba_url = f"https://guba.eastmoney.com/list,{stock_symbol}.html"
        urls.append(guba_url)
        
        return urls
    
    def _filter_valid_comments(self, json_list: list) -> list:
        # 验证每条评论的schema
        valid_comments = []
        invalid_comments = []
        for comment in json_list:
            if self._validate_comment_schema(comment):
                valid_comments.append(comment)
            else:
                invalid_comments.append(comment)
                logger.warning("发现%d条不符合schema的评论数据, 如%r", len(invalid_comments), invalid_comments[0])
        if not valid_comments:
            logger.warning("没有有效的评论数据")
        return valid_comments

    def extract_comments_from_url(self, url: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        从单个URL提取评论
        
        Args:
            url: 页面URL
            
        Returns:
            Tuple[原始响应, 评论列表]
        """
        # 直接调用read_page_content获取页面内容
        logger.info(f"正在获取页面内容: {url}")
        page_content = self.web_page_reader.read_and_extract(url, '提取评论区')
        
        # 使用LLM分析页面内容并提取评论, 截取前15000个字符以避免过长
        
        prompt = dedent(f"""
            请分析以下页面内容，提取其中的评论区信息：

            页面URL: {url}
            页面内容: {page_content[:15000]}

            请提取所有评论并按JSON格式返回。
        """)
        
        @with_retry((LlmReplyInvalid,), LLM_RETRY_TIME)
        def retryable_extract():
            logger.info(f"开始分析页面: {url}")
            response = self.comment_extractor(prompt)
            logger.info("分析页面内容完成：%s...%s", response[:1], response[-1:])
            logger.debug("完整分析结果: %s", response)
            
            json_or_none = extract_json_string(response)
            logger.debug("提取到的JSON对象: %r", json_or_none)
            if json_or_none and isinstance(json_or_none, list):
                # 验证每条评论的schema
                return response, self._filter_valid_comments(json_or_none)
            else:
                logger.warning("大模型JSON响应错误")
                # 尝试使用大模型修复JSON
                if has_json_features(response) and json_or_none is None:
                    logger.info("检测到JSON特征字符，尝试使用大模型修复")
                    fixed_json = self.fix_json_tool(response)
                    if fixed_json and isinstance(fixed_json, list):
                        return response, self._filter_valid_comments(fixed_json)
                    else:
                        logger.warning("大模型修复JSON失败 %s", fixed_json)
                else:
                    logger.error("响应中未检测到JSON特征字符")
                
                raise LlmReplyInvalid("未找到JSON格式的评论数据", response)
        
        return retryable_extract()
    
    @with_retry((LlmReplyInvalid,), LLM_RETRY_TIME)
    def analyze_sentiment(self, stock_symbol: str, stock_name: str, all_comments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析市场情绪
        
        Args:
            stock_symbol: 股票代码
            stock_name: 股票名称
            all_comments: 所有评论数据
            
        Returns:
            情绪分析结果
        """
        assert len(all_comments) > 0, "评论数据不能为空"
        
        # 准备评论数据
        comments_summary = self._prepare_comments_for_analysis(all_comments)
        
        prompt = dedent(f"""
            请分析以下股票 {stock_name}({stock_symbol}) 的评论数据，评估当前市场情绪：

            评论数据统计：
            - 总评论数: {len(all_comments)}
            - 总点赞数: {sum(comment.get('likes', 0) for comment in all_comments)}
            - 总回复数: {sum(comment.get('replies', 0) for comment in all_comments)}

            评论内容示例：
            {comments_summary}

            请从以下维度进行分析：
            1. 整体情绪倾向 (积极/消极/中性)
            2. 互动活跃度 (点赞和回复情况)
            3. 情绪强度 (用词激烈程度)
            4. 市场预期 (看涨/看跌倾向)

            最后给出0-100的情绪评分和对应等级，并用XML标签标注。
        """)
        
        logger.info(f"开始分析股票 {stock_symbol} 的市场情绪")
        response = self.sentiment_analyzer(prompt)
        logger.info("完成情绪分析")
        
        # 提取XML标签中的数据
        score_match = re.search(r'<sentiment_score>(\d+)</sentiment_score>', response)
        level_match = re.search(r'<sentiment_level>([^<]+)</sentiment_level>', response)
        
        if not score_match or not level_match:
            logger.error("情绪分析结果中未找到评分或等级信息")
            raise LlmReplyInvalid("情绪分析结果格式错误", response)
        
        score = int(score_match.group(1)) if score_match else 50
        level = level_match.group(1) if level_match else "中等"
        
        return {
            "score": score,
            "level": level,
            "report": response,
            "raw_response": response
        }
    
    def _prepare_comments_for_analysis(self, comments: List[Dict[str, Any]], max_comments: int = 20) -> str:
        """
        准备评论数据供分析使用
        
        Args:
            comments: 评论列表
            max_comments: 最大评论数量
            
        Returns:
            格式化的评论字符串
        """
        if not comments:
            return "无评论数据"
        
        
        # 按点赞数排序，取前max_comments条
        sorted_comments = sorted(comments, key=lambda x: x.get('likes', 0), reverse=True)
        selected_comments = sorted_comments[:max_comments]
        
        comment_strings = []
        for i, comment in enumerate(selected_comments, 1):
            comment_str = f"""
{i}. [{comment.get('author', '匿名用户')}] {comment.get('time', '未知时间')}
内容: {comment.get('content', '评论内容缺失')}
点赞: {comment.get('likes', 0)} | 回复: {comment.get('replies', 0)}
"""
            comment_strings.append(comment_str)
        
        return "\n".join(comment_strings)
    
    def analyze_stock_sentiment(self, stock_symbol: str) -> Dict[str, Any]:
        """
        分析股票市场情绪
        
        Args:
            stock_symbol: 股票代码
            
        Returns:
            完整的分析结果
        """
        result = { "success": False, 'stock_symbol': stock_symbol }
        try:
            logger.info(f"开始分析股票 {stock_symbol} 的市场情绪")

            # 1. 获取股票基本信息
            stock_info = get_ashare_stock_info(stock_symbol)
            stock_name = stock_info.get('stock_name', '未知股票')
            result["stock_info"] = stock_info
            result["stock_name"] = stock_name
            logger.info(f"获取到股票信息: {stock_name}")

            # 2. 判断交易所
            exchange = determine_exchange(stock_symbol)
            result["exchange"] = exchange
            logger.info(f"判断交易所: {exchange}")
        
            # 3. 构建URL
            urls = self.build_ashare_stock_dicussion_urls(stock_symbol, exchange)
            logger.info(f"构建URL: {urls}")
        
            # 4. 爬取评论
            all_comments = []
            url_results = []
            for url in urls:
                try:
                    logger.info(f"爬取页面: {url}")
                    raw_response, comments = self.extract_comments_from_url(url)
                    
                    url_results.append({
                        "success": True,
                        "url": url,
                        "comments_count": len(comments),
                        "comments": comments,
                        "raw_response": raw_response
                    })
                    
                    all_comments.extend(comments)
                    logger.info(f"从 {url} 获取到 {len(comments)} 条评论")
                    
                except Exception as e:
                    logger.error(f"爬取页面 {url} 失败: {e}")
                    logger.debug(f"错误详情: {traceback.format_exc()}")
                    url_results.append({
                        "success": False,
                        "url": url,
                    })
            result["urls"] = urls
            result["url_results"] = url_results
            result["all_comments"] = all_comments
            result["total_comments"] = len(all_comments)

            if not all_comments:
                logger.warning(f"没有评论数据，无法进行情绪分析: {stock_symbol}")
                return result
            # 5. 分析市场情绪
            sentiment_result = self.analyze_sentiment(stock_symbol, stock_name, all_comments)
            result['analysis_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            result['sentiment_score'] = sentiment_result['score']
            result['sentiment_level'] = sentiment_result['level']
            result['sentiment_report'] = sentiment_result['report']
            
            logger.info(f"完成情绪分析: {stock_symbol} - 评分: {sentiment_result['score']} - 等级: {sentiment_result['level']}")
            result["success"] = True

        except Exception as e:
            logger.error(f"分析股票 {stock_symbol} 情绪失败: {e}")
            logger.debug(f"错误详情: {traceback.format_exc()}")
            
        return result

    def generate_html_report(self, analysis_result: Dict[str, Any]) -> str:
        """
        生成HTML报告
        
        Args:
            analysis_result: 分析结果
            
        Returns:
            HTML报告字符串
        """
        
        stock_symbol = analysis_result["stock_symbol"]
        # 根据情绪评分确定颜色
        score = analysis_result["sentiment_score"]
        if score <= 20:
            sentiment_color = "#d32f2f"  # 红色 - 极度恐慌
        elif score <= 40:
            sentiment_color = "#f57c00"  # 橙色 - 恐慌
        elif score <= 60:
            sentiment_color = "#616161"  # 灰色 - 中等
        elif score <= 80:
            sentiment_color = "#388e3c"  # 绿色 - 贪婪
        else:
            sentiment_color = "#1976d2"  # 蓝色 - 极度贪婪
        
        # 预处理markdown内容，转义特殊字符
        markdown_content = analysis_result["sentiment_report"]
        escaped_content = markdown_content.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
        
        # 处理URL结果，添加平台信息
        processed_url_results = []
        for url_result in analysis_result["url_results"]:
            platform = "雪球" if "xueqiu.com" in url_result["url"] else "股吧" if "guba.eastmoney.com" in url_result["url"] else "其他平台"
            processed_url_result = url_result.copy()
            processed_url_result["platform"] = platform
            processed_url_results.append(processed_url_result)
        
        # 渲染HTML内容
        html_content = Template(HTML_TEMPLATE).render(
            stock_symbol=stock_symbol,
            stock_name=analysis_result["stock_name"],
            stock_type=analysis_result["stock_info"].get("stock_type", "未知"),
            stock_business=analysis_result["stock_info"].get("stock_business", "未知"),
            exchange=analysis_result["exchange"],
            analysis_time=analysis_result["analysis_time"],
            total_comments=analysis_result["total_comments"],
            url_results_count=len(analysis_result["url_results"]),
            sentiment_score=analysis_result["sentiment_score"],
            sentiment_level=analysis_result["sentiment_level"],
            sentiment_color=sentiment_color,
            escaped_content=escaped_content,
            url_results=processed_url_results,
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
        
        file_name = f"{analysis_result['stock_symbol']}_sentiment_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        file_path = os.path.join(save_folder_path, file_name)
        
        html_content = self.generate_html_report(analysis_result)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTML报告已保存到: {file_path}")
        return file_path