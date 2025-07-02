#!/usr/bin/env python3
"""
Tool Call功能测试示例
演示如何使用自动函数注册和工具调用功能
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Optional, List
from lib.adapter.llm.interface import Agent
from lib.adapter.llm.siliconflow import SiliconFlow


def get_weather(location: str, unit: str = "celsius") -> str:
    """获取指定地点的天气信息

    Args:
        location: 城市名称
        unit: 温度单位，可选celsius或fahrenheit
    """
    # 模拟天气数据
    weather_data = {
        "北京": {"temp": 25, "condition": "晴天"},
        "上海": {"temp": 28, "condition": "多云"},
        "深圳": {"temp": 32, "condition": "小雨"},
        "广州": {"temp": 30, "condition": "晴天"},
    }

    data = weather_data.get(location, {"temp": 20, "condition": "未知"})
    temp_symbol = "°C" if unit == "celsius" else "°F"
    temp = data["temp"] if unit == "celsius" else int(data["temp"] * 9 / 5 + 32)

    return f"{location}的天气：{data['condition']}，温度{temp}{temp_symbol}"


def calculate_sum(a: int, b: int) -> int:
    """计算两个数的和

    Parameters:
        a: 第一个数字
        b: 第二个数字
    """
    return a + b


def search_stock_info(symbol: str, days: Optional[int] = 7) -> str:
    """搜索股票信息

    Args:
        symbol: 股票代码
        days: 查询天数，默认7天
    """
    # 模拟股票数据
    stock_data = {
        "000001": {"name": "平安银行", "price": 12.5, "change": "+0.3%"},
        "600036": {"name": "招商银行", "price": 45.2, "change": "-0.5%"},
        "000858": {"name": "五粮液", "price": 180.6, "change": "+1.2%"},
    }

    data = stock_data.get(symbol, {"name": "未知股票", "price": 0, "change": "0%"})
    return f"股票{symbol}({data['name']})：当前价格{data['price']}元，{days}天涨跌幅{data['change']}"


def get_trade_recommendations(market: str = "A股") -> List[str]:
    """获取交易建议

    Args:
        market: 市场类型，如A股、港股、美股等
    """
    recommendations = {
        "A股": [
            "建议关注新能源板块",
            "科技股可能有反弹机会",
            "金融股估值较低可考虑配置",
        ],
        "港股": [
            "互联网科技股值得关注",
            "地产股风险较高需谨慎",
            "消费股有长期投资价值",
        ],
        "美股": [
            "AI概念股热度持续",
            "传统制造业面临转型压力",
            "生物医药板块具有成长性",
        ],
    }

    return recommendations.get(market, ["暂无该市场的建议"])


def main():
    """主函数：演示tool_call功能"""
    print("=== Tool Call功能测试 ===\n")

    # 创建LLM实例和Agent
    llm = SiliconFlow(model="deepseek-ai/DeepSeek-V3")
    agent = Agent(llm)

    # 设置系统提示
    agent.set_system_prompt(
        """
你是一个智能助手，可以帮助用户获取天气信息、进行数学计算、查询股票信息和提供交易建议。
当用户询问相关问题时，请使用提供的工具来获取准确信息。
"""
    )

    # 注册工具函数
    print("正在注册工具函数...")
    weather_schema = agent.register_tool(get_weather)
    calc_schema = agent.register_tool(calculate_sum)
    stock_schema = agent.register_tool(search_stock_info)
    trade_schema = agent.register_tool(get_trade_recommendations)

    print(f"已注册工具：")
    print(f"- {weather_schema['name']}: {weather_schema['description']}")
    print(f"- {calc_schema['name']}: {calc_schema['description']}")
    print(f"- {stock_schema['name']}: {stock_schema['description']}")
    print(f"- {trade_schema['name']}: {trade_schema['description']}")
    print()

    # 测试用例
    test_cases = [
        {
            "question": "北京今天天气怎么样？",
            "tool_use": True,
            "description": "测试天气查询工具",
        },
        {
            "question": "帮我计算 15 + 27 等于多少？",
            "tool_use": True,
            "description": "测试数学计算工具",
        },
        {
            "question": "查询股票000001的信息",
            "tool_use": ["search_stock_info"],  # 只使用指定工具
            "description": "测试股票查询工具（指定工具）",
        },
        {
            "question": "给我一些A股的交易建议",
            "tool_use": True,
            "description": "测试交易建议工具",
        },
        {
            "question": "你好，请介绍一下你自己",
            "tool_use": False,
            "description": "测试无工具对话",
        },
    ]

    # 执行测试
    for i, test_case in enumerate(test_cases, 1):
        print(f"=== 测试 {i}: {test_case['description']} ===")
        print(f"问题: {test_case['question']}")
        print(f"工具使用: {test_case['tool_use']}")

        try:
            response = agent.ask(test_case["question"], tool_use=test_case["tool_use"])
            print(f"回答: {response}")
        except Exception as e:
            print(f"错误: {str(e)}")

        print("-" * 50)
        agent.clear()  # 清除对话历史

        # 重新设置系统提示
        agent.set_system_prompt(
            """
你是一个智能助手，可以帮助用户获取天气信息、进行数学计算、查询股票信息和提供交易建议。
当用户询问相关问题时，请使用提供的工具来获取准确信息。
"""
        )


if __name__ == "__main__":
    main()
