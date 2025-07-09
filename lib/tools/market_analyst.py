#!/usr/bin/env python3
"""
智能市场分析工具
使用Agent自主选择工具进行技术分析，生成HTML报告
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional, Annotated
from dataclasses import dataclass
from textwrap import dedent
import traceback

from jinja2 import Template
from lib.model import Ohlcv
from lib.modules.trade import ashare, crypto
from lib.tools.ashare_stock import get_ashare_stock_info
from lib.tools.market_master import (
    format_ohlcv_list, 
    format_indicators, 
    format_ohlcv_pattern
)
from lib.utils.indicators import calculate_indicators
from lib.adapter.llm import get_agent
from lib.logger import logger

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
            max-width: 1400px;
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
                <span class="info-value">{{ stock_name }}</span>
            </div>
            <div class="info-item">
                <span class="info-label">市场:</span>
                <span class="info-value">{{ market_type }}</span>
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
            <p>报告生成时间: {{ current_time }}</p>
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
        const markdownContent = `{{ escaped_analysis_content }}`;
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
            
            const smaData = alignIndicatorData(indicatorsData.sma || [], dates.length);
            const bollUpperData = alignIndicatorData(indicatorsData.boll_upper || [], dates.length);
            const bollMiddleData = alignIndicatorData(indicatorsData.boll_middle || [], dates.length);
            const bollLowerData = alignIndicatorData(indicatorsData.boll_lower || [], dates.length);
            
            const option = {
                title: { text: '{{ symbol }} K线图', left: 'center' },
                tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
                legend: {
                    data: ['K线', 'SMA', '布林上轨', '布林中轨', '布林下轨', '成交量'],
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
                        name: 'SMA', type: 'line', data: smaData, smooth: true,
                        lineStyle: { opacity: 0.8, color: '#3498db', width: 2 },
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

class MarketAnalyst:
    """智能市场分析师"""
    
    def __init__(self, provider: str = "paoluz", model: str = "deepseek-v3", ohlcv_days: int = 50):
        """
        初始化市场分析师
        
        Args:
            provider: LLM提供商
            model: 使用的模型
            ohlcv_days: 获取OHLCV数据的天数
        """
        self.provider = provider
        self.model = model
        self.ohlcv_days = ohlcv_days
        self.current_symbol = ""
        
        # 创建Agent
        self.agent = get_agent(provider, model, temperature=0.2)
        self._register_tools()
        self._set_system_prompt()
    
    def _get_ohlcv_history(self, symbol: str) -> List[Ohlcv]:
        """获取OHLCV历史数据"""
        market_type = "crypto" if "USDT" in symbol.upper() else "ashare"
        
        if market_type == "crypto":
            history = crypto.get_ohlcv_history(symbol, "1d", limit=self.ohlcv_days)
        else:
            history = ashare.get_ohlcv_history(symbol, "1d", limit=self.ohlcv_days)
        
        return history.data[-self.ohlcv_days:]
    
    def get_ohlcv_data(
        self,
        symbol: str,
        days: Annotated[int, "获取多少天的数据，默认30天"] = 30
    ) -> str:
        """获取股票或加密货币的OHLCV数据"""
        try:
            ohlcv_list = self._get_ohlcv_history(symbol)
            if not ohlcv_list:
                return f"❌ 无法获取{symbol}的OHLCV数据"
            
            formatted_data = format_ohlcv_list(ohlcv_list[-days:])
            logger.info(f"成功获取{symbol}的{len(ohlcv_list)}天OHLCV数据")
            return formatted_data
            
        except Exception as e:
            logger.error(f"获取OHLCV数据失败: {e}")
            return f"❌ 获取{symbol}的OHLCV数据失败: {str(e)}"

    def calculate_technical_indicators(
        self,
        indicators: Annotated[str, "技术指标列表，用逗号分隔，可选：sma,rsi,boll,macd,stoch,atr,vwma"] = "sma,rsi,boll,macd",
        max_length: Annotated[int, "返回最近多少个数据点，默认20"] = 20
    ) -> str:
        """计算技术指标"""
        try:
            if not self.current_symbol:
                return "❌ 请先调用get_ohlcv_data获取数据"
            
            ohlcv_list = self._get_ohlcv_history(self.current_symbol)
            if not ohlcv_list:
                return f"❌ 无法获取{self.current_symbol}的历史数据"
            
            indicator_list = [ind.strip() for ind in indicators.split(",")]
            result = format_indicators(ohlcv_list, indicator_list, max_length)
            logger.info(f"成功计算{self.current_symbol}的技术指标: {indicator_list}")
            return result
            
        except Exception as e:
            logger.error(f"计算技术指标失败: {e}")
            return f"❌ 计算技术指标失败: {str(e)}"

    def detect_candlestick_patterns(self) -> str:
        """检测K线形态"""
        try:
            if not self.current_symbol:
                return "❌ 请先调用get_ohlcv_data获取数据"
            
            ohlcv_list = self._get_ohlcv_history(self.current_symbol)
            if not ohlcv_list or len(ohlcv_list) < 5:
                return f"❌ 数据不足，无法检测K线形态（需要至少5个数据点）"
            
            patterns = format_ohlcv_pattern(ohlcv_list)
            if patterns:
                logger.info(f"成功检测{self.current_symbol}的K线形态")
                return patterns
            else:
                return f"📊 {self.current_symbol}未检测到明显的K线形态"
                
        except Exception as e:
            logger.error(f"检测K线形态失败: {e}")
            return f"❌ 检测K线形态失败: {str(e)}"

    def get_stock_basic_info(self, symbol: str) -> str:
        """获取股票基本信息"""
        try:
            self.current_symbol = symbol
            
            if "USDT" in symbol.upper():
                info = {
                    "symbol": symbol,
                    "name": symbol.replace("USDT", "").replace("/", ""),
                    "type": "加密货币",
                    "market": "crypto",
                    "description": f"{symbol}是一个加密货币交易对"
                }
            else:
                stock_info = get_ashare_stock_info(symbol)
                info = {
                    "symbol": symbol,
                    "name": stock_info.get("stock_name", "未知"),
                    "type": stock_info.get("stock_type", "股票"),
                    "business": stock_info.get("stock_business", "未知"),
                    "market": "ashare",
                    "description": f"{stock_info.get('stock_name', symbol)}是一只A股股票，属于{stock_info.get('stock_business', '未知')}行业"
                }
            
            result = f"📈 {info['name']}({symbol}) 基本信息:\n"
            result += f"• 类型: {info['type']}\n"
            result += f"• 市场: {info['market']}\n"
            if 'business' in info:
                result += f"• 行业: {info['business']}\n"
            result += f"• 描述: {info['description']}"
            
            logger.info(f"成功获取{symbol}的基本信息")
            return result
            
        except Exception as e:
            logger.error(f"获取股票基本信息失败: {e}")
            return f"❌ 获取{symbol}基本信息失败: {str(e)}"
    
    def _register_tools(self):
        """注册分析工具"""
        self.agent.register_tool(self.get_stock_basic_info)
        self.agent.register_tool(self.get_ohlcv_data)
        self.agent.register_tool(self.calculate_technical_indicators)
        self.agent.register_tool(self.detect_candlestick_patterns)
        logger.info("已注册4个分析工具")
    
    def _set_system_prompt(self):
        """设置系统提示"""
        system_prompt = dedent("""
        你是一位经验丰富的技术分析专家，擅长分析股票和加密货币市场。你的任务是根据用户的请求，自主选择合适的工具进行深入的技术分析。
        
        ## 可用工具说明
        
        1. **get_stock_basic_info(symbol)**: 获取股票或加密货币的基本信息
        2. **get_ohlcv_data(symbol, days)**: 获取OHLCV历史数据
        3. **calculate_technical_indicators(indicators, max_length)**: 计算技术指标
        4. **detect_candlestick_patterns()**: 检测K线形态
        
        ## ⚠️ 数据量要求 - 重要说明
        
        **不同技术指标对历史数据的要求不同，为确保所有技术指标都能准确计算，强烈建议获取至少40天以上的OHLCV数据：**
        
        ### 各指标最低数据要求：
        - **SMA(5日)**: 最少5天数据
        - **SMA(20日)**: 最少20天数据  
        - **RSI**: 最少15天数据
        - **布林带(BOLL)**: 最少20天数据
        - **MACD**: 最少36天数据 ⭐ (计算复杂度最高，需要26日EMA+12日EMA+9日信号线)
        - **随机指标(STOCH/KDJ)**: 最少19天数据
        - **ATR**: 最少15天数据
        - **VWMA**: 最少20天数据 (成交量加权移动平均线)
        
        **推荐策略**: 为确保所有指标都能准确计算，建议调用get_ohlcv_data时设置days参数为40-50天。
        
        ## 分析原则
        
        1. **数据充足性**: 首先确保获取足够的历史数据（强烈建议40-50天）来支持所有技术指标的准确计算
        2. **循序渐进**: 先获取基本信息，再获取充足的价格数据，然后选择合适的技术指标
        3. **工具选择**: 根据市场情况和分析目标，选择最相关的指标组合（建议4-6个指标）
        4. **综合分析**: 结合价格走势、技术指标和K线形态进行综合判断
        5. **风险评估**: 务必评估当前市场风险，给出明确的风险提示
        
        ## 输出要求
        
        1. 提供详细的技术分析报告，包含：
           - 趋势分析（短期、中期、长期）
           - 关键支撑和阻力位
           - 技术指标解读
           - K线形态分析（如果检测到）
           - 市场情绪评估
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
        """)
        
        self.agent.set_system_prompt(system_prompt)
    
    def analyze_stock_market(self, symbol: str, user_request: str = None) -> Dict[str, Any]:
        """
        分析股票市场并生成完整报告
        
        Args:
            symbol: 股票代码或加密货币交易对
            user_request: 用户的具体分析需求
        
        Returns:
            完整的分析结果
        """
        result = {
            "symbol": symbol,
            "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "success": False
        }
        
        try:
            logger.info(f"开始分析{symbol}，用户需求：{user_request or '全面技术分析'}")
            
            # 获取基本信息
            if "USDT" in symbol.upper():
                result["stock_name"] = symbol.replace("USDT", "").replace("/", "")
                result["market_type"] = "加密货币"
            else:
                stock_info = get_ashare_stock_info(symbol)
                result["stock_name"] = stock_info.get("stock_name", "未知")
                result["market_type"] = "A股"
                result["stock_info"] = stock_info
            
            # 获取历史数据
            ohlcv_list = self._get_ohlcv_history(symbol)
            if not ohlcv_list:
                raise Exception("无法获取历史数据")
            
            # 准备原始数据
            result["raw_ohlcv_data"] = format_ohlcv_list(ohlcv_list)
            result["raw_indicators_data"] = format_indicators(ohlcv_list, ["sma", "rsi", "macd", "boll"], 20)
            result["raw_patterns_data"] = format_ohlcv_pattern(ohlcv_list) or ""
            
            # 准备图表数据
            result["ohlcv_data"] = self._prepare_chart_data(ohlcv_list)
            result["indicators_data"] = self._parse_indicators_for_chart(ohlcv_list)
            
            # AI分析
            request = f"请对{symbol}进行技术分析。用户需求：{user_request}" if user_request else f"请对{symbol}进行全面的技术分析，包括趋势分析、技术指标分析、K线形态分析，并给出交易建议。"
            
            analysis_result = self.agent.ask(request, tool_use=True)
            result["analysis_result"] = analysis_result
            
            result["success"] = True
            logger.info(f"分析完成：{symbol}")
            
        except Exception as e:
            logger.error(f"分析失败：{e}")
            logger.debug(f"错误详情：{traceback.format_exc()}")
            result["error"] = str(e)
        
        return result
    
    def _prepare_chart_data(self, ohlcv_list: List[Ohlcv]) -> List[Dict]:
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
    
    def _parse_indicators_for_chart(self, ohlcv_list: List[Ohlcv]) -> Dict:
        """解析技术指标数据用于图表显示"""
        indicators_data = {}
        
        try:
            indicator_results = calculate_indicators(
                ohlcv_list=ohlcv_list, 
                use_indicators=["sma", "rsi", "macd", "boll"]
            )
            
            if indicator_results.sma20:
                indicators_data["sma"] = indicator_results.sma20.sma
            
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
            
        except Exception as e:
            logger.error(f"解析技术指标失败: {e}")
        
        return indicators_data
    
    def generate_html_report(self, analysis_result: Dict[str, Any]) -> str:
        """生成HTML报告"""
        if not analysis_result["success"]:
            return f"<html><body><h1>分析失败</h1><p>{analysis_result.get('error', '未知错误')}</p></body></html>"
        
        # 转义markdown内容
        markdown_content = analysis_result["analysis_result"]
        escaped_content = markdown_content.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
        
        # 渲染HTML内容
        html_content = Template(HTML_TEMPLATE).render(
            symbol=analysis_result["symbol"],
            stock_name=analysis_result["stock_name"],
            market_type=analysis_result["market_type"],
            analysis_time=analysis_result["analysis_time"],
            data_days=self.ohlcv_days,
            indicators_used="SMA, RSI, MACD, 布林带",
            escaped_analysis_content=escaped_content,
            raw_ohlcv_data=analysis_result["raw_ohlcv_data"],
            raw_indicators_data=analysis_result["raw_indicators_data"],
            raw_patterns_data=analysis_result["raw_patterns_data"],
            ohlcv_data_json=json.dumps(analysis_result["ohlcv_data"]),
            indicators_data_json=json.dumps(analysis_result["indicators_data"]),
            current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        return html_content
    
    def save_html_report(self, analysis_result: Dict[str, Any], output_file: str = None) -> str:
        """保存HTML报告"""
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            clean_symbol = analysis_result["symbol"].replace("/", "")
            output_file = f"smart_market_analysis_{clean_symbol}_{timestamp}.html"
        
        html_content = self.generate_html_report(analysis_result)
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        logger.info(f"HTML报告已保存到: {output_file}")
        return output_file