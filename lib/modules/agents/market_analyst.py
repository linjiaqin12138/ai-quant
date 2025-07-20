#!/usr/bin/env python3
"""
智能市场分析工具
使用Agent自主选择工具进行技术分析，生成HTML报告
"""

import json
from datetime import datetime
from typing import List, Dict, Annotated

from jinja2 import Template
from lib.model import Ohlcv
from lib.modules.agents.common import format_indicators, format_ohlcv_list, format_ohlcv_pattern, get_ohlcv_history
from lib.tools.ashare_stock import get_ashare_stock_info
from lib.utils.indicators import calculate_indicators
from lib.modules import get_agent
from lib.logger import logger
from lib.adapter.llm import get_llm
from lib.adapter.llm.interface import LlmAbstract
from lib.utils.string import escape_text_for_jinja2_temperate

# HTML报告模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>智能市场技术分析报告 - {{ symbol }}</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
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
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
        }
        .info-item {
            display: flex;
            align-items: center;
            padding: 10px;
            background-color: white;
            border-radius: 5px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .info-label {
            font-weight: bold;
            color: #2c3e50;
            margin-right: 10px;
            min-width: 80px;
        }
        .info-value {
            color: #34495e;
            flex: 1;
            word-break: break-all;
        }
        .chart-container {
            background-color: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .chart-title {
            font-size: 18px;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 15px;
            text-align: center;
        }
        .chart {
            width: 100%;
            height: 500px;
        }
        .indicators-chart {
            width: 100%;
            height: 300px;
        }
        .analysis-content {
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 8px;
            padding: 25px;
            margin: 20px 0;
            line-height: 1.8;
        }
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
        .raw-data-section {
            background-color: #2c3e50;
            color: #ecf0f1;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .raw-data-content {
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            white-space: pre-wrap;
            max-height: 400px;
            overflow-y: auto;
            background-color: #34495e;
            padding: 15px;
            border-radius: 5px;
            margin-top: 10px;
        }
        .footer {
            text-align: center;
            margin-top: 40px;
            color: #7f8c8d;
            font-size: 0.9em;
            border-top: 1px solid #e9ecef;
            padding-top: 20px;
        }
        .toggle-button {
            background-color: #3498db;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            margin-left: 10px;
        }
        .toggle-button:hover {
            background-color: #2980b9;
        }
        .hidden {
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 智能市场技术分析报告</h1>
        
        <div class="info-box">
            <div class="info-item">
                <span class="info-label">代码:</span>
                <span class="info-value">{{ symbol }}</span>
            </div>
            <div class="info-item">
                <span class="info-label">名称:</span>
                <span class="info-value">{{ symbol_name }}</span>
            </div>
            <div class="info-item">
                <span class="info-label">分析时间:</span>
                <span class="info-value">{{ analysis_time }}</span>
            </div>
            <div class="info-item">
                <span class="info-label">数据天数:</span>
                <span class="info-value">{{ data_days }}天</span>
            </div>
            <div class="info-item">
                <span class="info-label">使用指标:</span>
                <span class="info-value">{{ indicators_used }}</span>
            </div>
        </div>
        
        <div class="chart-container">
            <div class="chart-title">📈 K线图与技术指标</div>
            <div id="candlestick-chart" class="chart"></div>
        </div>
        
        <div class="chart-container">
            <div class="chart-title">📊 技术指标详情</div>
            <div id="indicators-chart" class="indicators-chart"></div>
        </div>
        
        <h2>🤖 AI技术分析报告</h2>
        <div class="analysis-content" id="analysis-content"></div>
        
        <h2>📄 原始数据 
            <button class="toggle-button" onclick="toggleRawData()">显示/隐藏</button>
        </h2>
        <div id="raw-data-section" class="raw-data-section hidden">
            <h3>OHLCV数据</h3>
            <div class="raw-data-content">{{ raw_ohlcv_data }}</div>
            
            <h3>技术指标数据</h3>
            <div class="raw-data-content">{{ raw_indicators_data }}</div>
            
            {% if raw_patterns_data %}
            <h3>K线形态数据</h3>
            <div class="raw-data-content">{{ raw_patterns_data }}</div>
            {% endif %}
        </div>
        
        <div class="footer">
            <p>由智能市场分析Agent自动生成</p>
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
        
        // 渲染AI分析内容
        const markdownContent = `{{ markdown_report }}`;
        const htmlContent = marked.parse(markdownContent);
        document.getElementById('analysis-content').innerHTML = htmlContent;
        
        // K线图数据
        const ohlcvData = {{ ohlcv_data_json }};
        const indicatorsData = {{ indicators_data_json }};
        
        // 公共函数：对齐技术指标数据到时间轴
        function alignIndicatorData(indicatorData, totalLength) {
            if (!indicatorData || indicatorData.length === 0) {
                return [];
            }
            const nullCount = totalLength - indicatorData.length;
            const nullArray = new Array(nullCount).fill(null);
            return nullArray.concat(indicatorData);
        }
        
        // 初始化K线图
        function initCandlestickChart() {
            const chart = echarts.init(document.getElementById('candlestick-chart'));
            
            const candleData = ohlcvData.map(item => [
                item.open, item.close, item.low, item.high
            ]);
            
            const dates = ohlcvData.map(item => item.date);
            const volumes = ohlcvData.map(item => item.volume);
            
            const sma20Data = alignIndicatorData(indicatorsData.sma20 || [], dates.length);
            const sma5Data = alignIndicatorData(indicatorsData.sma5 || [], dates.length);
            const bollUpperData = alignIndicatorData(indicatorsData.boll_upper || [], dates.length);
            const bollMiddleData = alignIndicatorData(indicatorsData.boll_middle || [], dates.length);
            const bollLowerData = alignIndicatorData(indicatorsData.boll_lower || [], dates.length);
            
            const option = {
                title: { text: '{{ symbol }} K线图', left: 'center' },
                tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
                legend: {
                    data: ['K线', 'SMA 5', 'SMA 20',  '布林上轨', '布林中轨', '布林下轨', '成交量'],
                    top: 30
                },
                grid: [
                    { left: '10%', right: '8%', height: '50%' },
                    { left: '10%', right: '8%', top: '70%', height: '16%' }
                ],
                xAxis: [
                    {
                        type: 'category', data: dates, scale: true, boundaryGap: false,
                        axisLine: {onZero: false}, splitLine: {show: false},
                        min: 'dataMin', max: 'dataMax'
                    },
                    {
                        type: 'category', gridIndex: 1, data: dates, scale: true, boundaryGap: false,
                        axisLine: {onZero: false}, axisTick: {show: false}, splitLine: {show: false},
                        axisLabel: {show: false}, min: 'dataMin', max: 'dataMax'
                    }
                ],
                yAxis: [
                    { scale: true, splitArea: { show: true } },
                    {
                        scale: true, gridIndex: 1, splitNumber: 2, axisLabel: {show: false},
                        axisLine: {show: false}, axisTick: {show: false}, splitLine: {show: false}
                    }
                ],
                dataZoom: [
                    { type: 'inside', xAxisIndex: [0, 1], start: 70, end: 100 },
                    { show: true, xAxisIndex: [0, 1], type: 'slider', top: '88%', start: 70, end: 100 }
                ],
                series: [
                    {
                        name: 'K线', type: 'candlestick', data: candleData,
                        itemStyle: {
                            color: '#ef232a', color0: '#14b143',
                            borderColor: '#ef232a', borderColor0: '#14b143'
                        }
                    },
                    {
                        name: 'SMA 20', type: 'line', data: sma20Data, smooth: true,
                        lineStyle: { opacity: 0.8, color: '#3498db', width: 2 },
                        symbol: 'none', connectNulls: false
                    },
                    {
                        name: 'SMA 5', type: 'line', data: sma5Data, smooth: true,
                        lineStyle: { opacity: 0.8, color: '#4398db', width: 2 },
                        symbol: 'none', connectNulls: false
                    },
                    {
                        name: '布林上轨', type: 'line', data: bollUpperData,
                        lineStyle: { opacity: 0.6, color: '#e74c3c', width: 1, type: 'dashed' },
                        symbol: 'none', connectNulls: false
                    },
                    {
                        name: '布林中轨', type: 'line', data: bollMiddleData,
                        lineStyle: { opacity: 0.6, color: '#f39c12', width: 1 },
                        symbol: 'none', connectNulls: false
                    },
                    {
                        name: '布林下轨', type: 'line', data: bollLowerData,
                        lineStyle: { opacity: 0.6, color: '#27ae60', width: 1, type: 'dashed' },
                        symbol: 'none', connectNulls: false
                    },
                    {
                        name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: volumes,
                        itemStyle: {
                            color: function(params) {
                                const index = params.dataIndex;
                                if (index === 0) return '#14b143';
                                return ohlcvData[index].close > ohlcvData[index].open ? '#ef232a' : '#14b143';
                            }
                        }
                    }
                ]
            };
            
            chart.setOption(option);
            window.addEventListener('resize', function() { chart.resize(); });
        }
        
        // 初始化技术指标图表
        function initIndicatorsChart() {
            const chart = echarts.init(document.getElementById('indicators-chart'));
            
            const dates = ohlcvData.map(item => item.date);
            const rsiData = alignIndicatorData(indicatorsData.rsi || [], dates.length);
            const macdData = alignIndicatorData(indicatorsData.macd || [], dates.length);
            const signalData = alignIndicatorData(indicatorsData.signal || [], dates.length);
            const histogramData = alignIndicatorData(indicatorsData.histogram || [], dates.length);
            
            const option = {
                title: { text: '技术指标', left: 'center' },
                tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
                legend: { data: ['RSI', 'MACD', 'Signal', 'Histogram'], top: 30 },
                grid: [
                    { left: '10%', right: '8%', height: '35%' },
                    { left: '10%', right: '8%', top: '55%', height: '35%' }
                ],
                xAxis: [
                    { type: 'category', data: dates, gridIndex: 0 },
                    { type: 'category', data: dates, gridIndex: 1 }
                ],
                yAxis: [
                    {
                        gridIndex: 0, min: 0, max: 100,
                        axisLine: { lineStyle: { color: '#5793f3' } }
                    },
                    {
                        gridIndex: 1,
                        axisLine: { lineStyle: { color: '#675bba' } }
                    }
                ],
                series: [
                    {
                        name: 'RSI', type: 'line', data: rsiData,
                        lineStyle: { color: '#5793f3' }, connectNulls: false,
                        markLine: {
                            data: [
                                {yAxis: 70, lineStyle: {color: '#ff4757', type: 'dashed'}},
                                {yAxis: 30, lineStyle: {color: '#2ed573', type: 'dashed'}}
                            ]
                        }
                    },
                    {
                        name: 'MACD', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: macdData,
                        lineStyle: { color: '#675bba' }, connectNulls: false
                    },
                    {
                        name: 'Signal', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: signalData,
                        lineStyle: { color: '#ff7675' }, connectNulls: false
                    },
                    {
                        name: 'Histogram', type: 'bar', xAxisIndex: 1, yAxisIndex: 1, data: histogramData,
                        itemStyle: {
                            color: function(params) {
                                return params.value > 0 ? '#2ed573' : '#ff4757';
                            }
                        }
                    }
                ]
            };
            
            chart.setOption(option);
            window.addEventListener('resize', function() { chart.resize(); });
        }
        
        function toggleRawData() {
            const section = document.getElementById('raw-data-section');
            section.classList.toggle('hidden');
        }
        
        window.addEventListener('load', function() {
            initCandlestickChart();
            initIndicatorsChart();
        });
    </script>
</body>
</html>
"""

MARKET_ANALYST_PROMPT = """
你是一位经验丰富的技术分析专家，擅长分析股票和加密货币市场。你的任务是根据用户的请求，自主选择合适的工具进行深入的技术分析。

## 可用工具说明
1. **calculate_technical_indicators(indicators, max_length)**: 计算技术指标

## 分析原则

1. **工具选择**: 根据市场情况和分析目标，选择最相关的指标组合（建议4-6个指标）
2. **综合分析**: 结合价格走势、技术指标和K线形态进行综合判断
3. **风险评估**: 务必评估当前市场风险，给出明确的风险提示

## 输出要求

1. 提供详细的技术分析报告，包含：
    - 趋势分析（短期、中期、长期）
    - 关键支撑和阻力位
    - 技术指标解读
    - K线形态分析（如果检测到）
    - 风险评估

2. 给出明确的交易建议：
    - **买入**: 多个指标显示积极信号，风险可控
    - **卖出**: 多个指标显示负面信号，风险较高
    - **持有**: 信号不明确或处于关键位置

3. 在报告末尾添加一个Markdown表格，总结关键要点：
    | 分析项目 | 状态 | 说明 |
    |----------|------|------|
    | 趋势方向 | 上升/下降/震荡 | 具体说明 |
    | 技术指标 | 积极/中性/消极 | 主要信号 |
    | K线形态 | 看涨/看跌/中性 | 形态说明 |
    | 风险等级 | 低/中/高 | 风险因素 |
    | 交易建议 | 买入/卖出/持有 | 建议理由 |

请根据用户的具体需求，主动选择和调用相应的工具，进行专业的技术分析。记住要获取足够的历史数据以确保技术指标计算的准确性。
"""
class MarketAnalyst:
    """智能市场分析师"""
    
    def __init__(self, llm: LlmAbstract = None, ohlcv_days: int = 50):
        """
        初始化市场分析师
        
        Args:
            llm: LLM实例
            ohlcv_days: 获取OHLCV数据的天数
        """
        self._llm = llm or get_llm("paoluz", "deepseek-v3", temperature=0.2)
        self._ohlcv_days = ohlcv_days
        
        # 创建Agent
        self._agent = get_agent(llm=self._llm)
        self._agent.register_tool(self.calculate_technical_indicators)
        logger.info("已注册技术指标计算工具")
        self._agent.set_system_prompt(MARKET_ANALYST_PROMPT)
        
        # 开始分析之后才会有值，开始分析前清空
        self._current_symbol = ""
        self._analysis_result = ""
        self._analysis_time = ""
        self._user_request = ""
        self._current_symbol_name = ""
        self._ohlcv_list = []
        self._use_indicators = ""
        self._indicators_result = ""

    def _init_analyzing(self, symbol: str, user_req: str):
        """根据要分析的symbol初始化类的属性"""
        self._current_symbol = symbol
        self._user_request = user_req
        self._analysis_result = None
        self._use_indicators = ""
        self._indicators_result = ""
        self._analysis_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._current_symbol_name = self._get_symbol_name()
        self._ohlcv_list = get_ohlcv_history(self._current_symbol, frame="1d", limit=self._ohlcv_days)
    
    def _get_symbol_name(self) -> str:
        if "USDT" in self._current_symbol.upper():
            return self._current_symbol.replace("USDT", "").replace("/", "")
        else:
            stock_info = get_ashare_stock_info(self._current_symbol)
            return stock_info["stock_name"]
    
    def calculate_technical_indicators(
        self,
        indicators: Annotated[str, "技术指标列表，用逗号分隔，可选：sma,rsi,boll,macd,stoch,atr,vwma"] = "sma,rsi,boll,macd",
        max_length: Annotated[int, "返回最近多少个数据点，默认20"] = 20
    ) -> str:
        """计算技术指标"""
        self._use_indicators = indicators
        indicator_list = [ind.strip() for ind in indicators.split(",")]
        result = format_indicators(self._ohlcv_list, indicator_list, max_length)
        logger.info(f"成功计算{self._current_symbol}的技术指标: {indicator_list}")
        self._indicators_result = result
        return result

    def _build_user_prompt(self) -> str:
        prompt = ""
        if self._user_request:
            prompt = f"请对{self._current_symbol_name}进行技术分析，并满足用户需求：{self._user_request}"
        else:
            prompt = f"请对{self._current_symbol_name}进行全面的技术分析，包括趋势分析、技术指标分析、K线形态分析，并给出交易建议。"

        prompt += f"\n\n过去{len(self._ohlcv_list)}天的OHLCV数据如下:\n\n"
        prompt += format_ohlcv_list(self._ohlcv_list)

        prompt += "\n\n检测到的K线形态：\n\n"
        prompt += format_ohlcv_pattern(self._ohlcv_list)

        prompt += "\n\n请继续使用calculate_technical_indicators工具计算必要的技术指标，并给出详细的分析报告。"
    
        return prompt

    def analyze_stock_market(self, symbol: str, user_request: str = None) -> str:
        """
        分析股票市场并生成完整报告
        
        Args:
            symbol: 股票代码或加密货币交易对
            user_request: 用户的具体分析需求
        
        Returns:
            分析结果字符串
        """
        logger.info(f"开始针对{symbol}进行技术分析")
        self._init_analyzing(symbol, user_request)
        prompt = self._build_user_prompt()

        self._analysis_result = self._agent.ask(prompt, tool_use=True)
        
        return self._analysis_result
    
    def _build_ohlcv_chart_data(self, ohlcv_list: List[Ohlcv]) -> List[Dict]:
        """准备图表数据"""
        chart_data = []
        for ohlcv in ohlcv_list:
            chart_data.append({
                "date": ohlcv.timestamp.strftime("%Y-%m-%d"),
                "open": float(ohlcv.open),
                "high": float(ohlcv.high),
                "low": float(ohlcv.low),
                "close": float(ohlcv.close),
                "volume": float(ohlcv.volume)
            })
        return chart_data
    
    def _build_indicators_char_data(self, ohlcv_list: List[Ohlcv]) -> Dict:
        """解析技术指标数据用于图表显示"""
        indicators_data = {}
        
        indicator_results = calculate_indicators(
            ohlcv_list=ohlcv_list, 
            use_indicators=["sma", "rsi", "macd", "boll"]
        )
        
        if indicator_results.sma20:
            indicators_data["sma20"] = indicator_results.sma20.sma
            indicators_data["sma5"] = indicator_results.sma5.sma
        
        if indicator_results.rsi:
            indicators_data["rsi"] = indicator_results.rsi.rsi
        
        if indicator_results.macd:
            indicators_data["macd"] = indicator_results.macd.macd
            indicators_data["signal"] = indicator_results.macd.macdsignal
            indicators_data["histogram"] = indicator_results.macd.macdhist
        
        if indicator_results.boll:
            indicators_data["boll_upper"] = indicator_results.boll.upperband
            indicators_data["boll_middle"] = indicator_results.boll.middleband
            indicators_data["boll_lower"] = indicator_results.boll.lowerband
        
        return indicators_data
    
    def generate_html_report(self) -> str:
        """生成HTML报告"""
        error_msg = "请先调用analyze_stock_market方法获取分析结果"
        assert self._analysis_result is not None, error_msg
    
        # 渲染HTML内容
        html_content = Template(HTML_TEMPLATE).render(
            symbol=self._current_symbol,
            symbol_name=self._current_symbol_name,
            analysis_time=self._analysis_time,
            data_days=self._ohlcv_days,
            indicators_used=self._use_indicators,
            markdown_report=escape_text_for_jinja2_temperate(self._analysis_result),
            raw_ohlcv_data=format_ohlcv_list(self._ohlcv_list) or "",
            raw_indicators_data=self._indicators_result or "",
            raw_patterns_data=format_ohlcv_pattern(self._ohlcv_list) or "",
            ohlcv_data_json=json.dumps(self._build_ohlcv_chart_data(self._ohlcv_list)),
            indicators_data_json=json.dumps(self._build_indicators_char_data(self._ohlcv_list))
        )
        
        return html_content