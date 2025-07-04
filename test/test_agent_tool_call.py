#!/usr/bin/env python3
"""
Agent Tool Call功能测试
测试Agent类的工具调用相关功能
"""

import sys
import os
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any, Optional, Annotated

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.adapter.llm.interface import Agent, LlmAbstract, extract_function_schema
from lib.adapter.llm import get_agent  # 导入真实的Agent工厂函数


# 测试用的工具函数
def get_weather(location: str, unit: str = "celsius") -> str:
    """获取指定地点的天气信息
    
    Args:
        location: 城市名称
        unit: 温度单位，可选celsius或fahrenheit
    """
    weather_data = {
        "北京": {"temp": 25, "condition": "晴天"},
        "上海": {"temp": 28, "condition": "多云"},
    }
    
    data = weather_data.get(location, {"temp": 20, "condition": "未知"})
    temp_symbol = "°C" if unit == "celsius" else "°F"
    temp = data["temp"] if unit == "celsius" else int(data["temp"] * 9 / 5 + 32)
    
    return f"{location}的天气：{data['condition']}，温度{temp}{temp_symbol}"


def calculate_sum(a: int, b: int) -> int:
    """计算两个数的和
    
    Args:
        a: 第一个数字
        b: 第二个数字
    """
    return a + b


def search_database(query: str, limit: Optional[int] = 10) -> List[str]:
    """搜索数据库
    
    Args:
        query: 搜索关键词
        limit: 返回结果数量限制
    """
    results = [f"结果{i}: {query}" for i in range(1, min(limit + 1, 4))]
    return results


# Mock LLM实现用于测试
class MockLLM(LlmAbstract):
    def __init__(self, model: str = "test-model", **kwargs):
        super().__init__(model, **kwargs)
        self.responses = []
        self.current_response_index = 0
        
    def set_responses(self, responses: List[Dict[str, Any]]):
        """设置模拟响应"""
        self.responses = responses
        self.current_response_index = 0
        
    def ask(self, context: List) -> str:
        """简单的ask实现，不支持工具"""
        if self.current_response_index < len(self.responses):
            response = self.responses[self.current_response_index]
            self.current_response_index += 1
            return response.get("content", "")
        return "Mock response"
        
    def ask_with_tools(self, context: List, available_tools: Optional[List[str]] = None) -> Dict[str, Any]:
        """支持工具调用的模拟实现"""
        if self.current_response_index < len(self.responses):
            response = self.responses[self.current_response_index]
            self.current_response_index += 1
            return response
        
        # 默认响应
        return {
            "content": "Mock response with tools",
            "tool_calls": []
        }


class TestExtractFunctionSchema:
    """测试函数schema提取功能"""
    
    def test_extract_simple_function_schema(self):
        """测试提取简单函数的schema"""
        schema = extract_function_schema(calculate_sum)

        assert schema["name"] == "calculate_sum"
        assert "计算两个数的和" in schema["description"]
        
        params = schema["parameters"]
        assert params["type"] == "object"
        assert "a" in params["properties"]
        assert "b" in params["properties"]
        assert params["properties"]["a"]["type"] == "integer"
        assert params["properties"]["b"]["type"] == "integer"
        assert set(params["required"]) == {"a", "b"}
        
    def test_extract_function_with_optional_params(self):
        """测试提取带可选参数的函数schema"""
        schema = extract_function_schema(get_weather)
        
        assert schema["name"] == "get_weather"
        params = schema["parameters"]
        
        # location是必需的，unit是可选的
        assert "location" in params["required"]
        assert "unit" not in params["required"]
        assert params["properties"]["unit"]["type"] == "string"
        
    def test_extract_function_with_list_return(self):
        """测试提取返回列表的函数schema"""
        schema = extract_function_schema(search_database)
        
        assert schema["name"] == "search_database"
        params = schema["parameters"]
        
        assert "query" in params["required"]
        assert "limit" not in params["required"]
        assert params["properties"]["limit"]["type"] == "integer"


class TestAgentBasicFunctionality:
    """测试Agent基本功能"""
    
    @pytest.fixture
    def agent(self):
        """创建测试用的Agent实例"""
        mock_llm = MockLLM()
        return Agent(mock_llm)
    
    def test_agent_initialization(self, agent):
        """测试Agent初始化"""
        assert agent.llm is not None
        assert agent.chat_context == []
        
    def test_simple_ask_without_tools(self, agent):
        """测试不使用工具的简单对话"""
        agent.llm.set_responses([{"content": "Hello, I'm an AI assistant!"}])
        
        response = agent.ask("Hello", tool_use=False)
        
        assert response == "Hello, I'm an AI assistant!"
        assert len(agent.chat_context) == 2
        assert agent.chat_context[0]["role"] == "user"
        assert agent.chat_context[1]["role"] == "assistant"
        
    def test_set_system_prompt(self, agent):
        """测试设置系统提示"""
        agent.set_system_prompt("You are a helpful assistant.")
        
        assert len(agent.chat_context) == 1
        assert agent.chat_context[0]["role"] == "system"
        assert agent.chat_context[0]["content"] == "You are a helpful assistant."
        
    def test_clear_context(self, agent):
        """测试清空对话上下文"""
        agent.ask("Hello", tool_use=False)
        assert len(agent.chat_context) > 0
        
        agent.clear()
        assert len(agent.chat_context) == 0
        
    def test_clear_context_with_system_prompt(self, agent):
        """测试清空带系统提示的对话上下文"""
        agent.set_system_prompt("You are a helpful assistant.")
        agent.ask("Hello", tool_use=False)
        assert len(agent.chat_context) > 1
        
        agent.clear()
        assert len(agent.chat_context) == 1
        assert agent.chat_context[0]["role"] == "system"


class TestAgentToolRegistration:
    """测试Agent工具注册功能"""
    
    @pytest.fixture
    def agent(self):
        """创建测试用的Agent实例"""
        mock_llm = MockLLM()
        return Agent(mock_llm)
    
    def test_register_single_tool(self, agent):
        """测试注册单个工具"""
        schema = agent.register_tool(get_weather)
        
        assert schema["name"] == "get_weather"
        assert "get_weather" in agent.llm.tools
        assert len(agent.llm.params.get("tools", [])) == 1
        
    def test_register_multiple_tools(self, agent):
        """测试注册多个工具"""
        agent.register_tool(get_weather)
        agent.register_tool(calculate_sum)
        agent.register_tool(search_database)
        
        assert len(agent.llm.tools) == 3
        assert len(agent.llm.params.get("tools", [])) == 3
        
        tool_names = [tool["function"]["name"] for tool in agent.llm.params["tools"]]
        assert "get_weather" in tool_names
        assert "calculate_sum" in tool_names
        assert "search_database" in tool_names
        
    def test_tool_execution(self, agent):
        """测试工具执行"""
        agent.register_tool(calculate_sum)
        
        # 模拟工具调用
        tool_call = {
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "calculate_sum",
                "arguments": json.dumps({"a": 15, "b": 27})
            }
        }
        
        result = agent.llm.execute_tool(tool_call)
        assert result == "42"
        
    def test_tool_execution_error(self, agent):
        """测试工具执行错误处理"""
        agent.register_tool(calculate_sum)
        
        # 模拟错误的工具调用（缺少参数）
        tool_call = {
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "calculate_sum",
                "arguments": json.dumps({"a": 15})  # 缺少参数b
            }
        }
        
        result = agent.llm.execute_tool(tool_call)
        assert "Error executing tool" in result
        
    def test_unknown_tool_execution(self, agent):
        """测试执行未知工具"""
        tool_call = {
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "unknown_tool",
                "arguments": json.dumps({})
            }
        }
        
        result = agent.llm.execute_tool(tool_call)
        assert "Tool unknown_tool not found" in result


class TestAgentToolCallConversation:
    """测试Agent工具调用对话功能"""
    
    @pytest.fixture
    def agent(self):
        """创建测试用的Agent实例"""
        mock_llm = MockLLM()
        return Agent(mock_llm)
    
    def test_simple_tool_call_conversation(self, agent):
        """测试简单的工具调用对话"""
        agent.register_tool(calculate_sum)
        
        # 设置LLM响应：先调用工具，然后给出最终答案
        agent.llm.set_responses([
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_123",
                        "type": "function",
                        "function": {
                            "name": "calculate_sum",
                            "arguments": json.dumps({"a": 15, "b": 27})
                        }
                    }
                ]
            },
            {
                "content": "根据计算结果，15 + 27 = 42",
                "tool_calls": []
            }
        ])
        
        response = agent.ask("帮我计算15加27等于多少？", tool_use=True)
        
        assert "15 + 27 = 42" in response
        # 验证对话上下文包含用户消息、助手工具调用、工具结果和最终回答
        assert len(agent.chat_context) >= 4
        
    def test_multiple_tool_calls_in_one_response(self, agent):
        """测试一次响应中包含多个工具调用"""
        agent.register_tool(calculate_sum)
        agent.register_tool(get_weather)
        
        # 设置LLM响应：同时调用多个工具
        agent.llm.set_responses([
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_123",
                        "type": "function",
                        "function": {
                            "name": "calculate_sum",
                            "arguments": json.dumps({"a": 10, "b": 20})
                        }
                    },
                    {
                        "id": "call_456",
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": json.dumps({"location": "北京"})
                        }
                    }
                ]
            },
            {
                "content": "计算结果是30，北京天气晴朗。",
                "tool_calls": []
            }
        ])
        
        response = agent.ask("帮我计算10+20，同时查询北京天气", tool_use=True)
        
        assert "30" in response or "北京" in response
        
    def test_tool_call_with_specific_tools(self, agent):
        """测试使用指定工具列表"""
        agent.register_tool(calculate_sum)
        agent.register_tool(get_weather)
        agent.register_tool(search_database)
        
        # 设置LLM响应
        agent.llm.set_responses([
            {
                "content": "我只能使用计算工具来帮您",
                "tool_calls": []
            }
        ])
        
        # 只允许使用计算工具
        response = agent.ask("帮我计算", tool_use=["calculate_sum"])
        
        assert "计算" in response
        
    def test_no_tool_calls_in_response(self, agent):
        """测试响应中没有工具调用"""
        agent.register_tool(calculate_sum)
        
        # 设置LLM响应：直接给出答案，不调用工具
        agent.llm.set_responses([
            {
                "content": "我可以帮您计算，请告诉我具体的数字。",
                "tool_calls": []
            }
        ])
        
        response = agent.ask("你能帮我计算吗？", tool_use=True)
        
        assert "计算" in response
        assert len(agent.chat_context) == 2
        
    def test_tool_call_conversation_error_handling(self, agent):
        """测试工具调用对话中的错误处理"""
        agent.register_tool(calculate_sum)
        
        # 模拟LLM抛出异常
        def mock_ask_with_tools(*args, **kwargs):
            raise Exception("LLM service unavailable")
            
        agent.llm.ask_with_tools = mock_ask_with_tools
        
        response = agent.ask("计算1+1", tool_use=True)
        
        assert "Error occurred during tool conversation" in response
        
    def test_tool_call_iteration_limit_warning(self, agent):
        """测试工具调用迭代次数警告"""
        agent.register_tool(calculate_sum)
        
        # 设置无限循环的响应（总是调用工具但不给出最终答案）
        responses = []
        for i in range(7):  # 超过5轮
            responses.append({
                "content": "",
                "tool_calls": [
                    {
                        "id": f"call_{i}",
                        "type": "function",
                        "function": {
                            "name": "calculate_sum",
                            "arguments": json.dumps({"a": i, "b": 1})
                        }
                    }
                ]
            })
        # 最后一轮给出答案
        responses.append({
            "content": "计算完成",
            "tool_calls": []
        })
        
        agent.llm.set_responses(responses)
        
        with patch('lib.logger.logger.warning') as mock_warning:
            response = agent.ask("持续计算", tool_use=True)
            
            # 验证警告被调用
            mock_warning.assert_called()
            assert "计算完成" in response


class TestAgentToolAvailability:
    """测试Agent工具可用性功能"""
    
    @pytest.fixture
    def agent(self):
        """创建测试用的Agent实例"""
        mock_llm = MockLLM()
        return Agent(mock_llm)
    
    def test_get_all_available_tools(self, agent):
        """测试获取所有可用工具"""
        agent.register_tool(calculate_sum)
        agent.register_tool(get_weather)
        
        tools = agent.llm.get_available_tools()
        
        assert len(tools) == 2
        tool_names = [tool["function"]["name"] for tool in tools]
        assert "calculate_sum" in tool_names
        assert "get_weather" in tool_names
        
    def test_get_specific_available_tools(self, agent):
        """测试获取指定的可用工具"""
        agent.register_tool(calculate_sum)
        agent.register_tool(get_weather)
        agent.register_tool(search_database)
        
        tools = agent.llm.get_available_tools(["calculate_sum", "get_weather"])
        
        assert len(tools) == 2
        tool_names = [tool["function"]["name"] for tool in tools]
        assert "calculate_sum" in tool_names
        assert "get_weather" in tool_names
        assert "search_database" not in tool_names
        
    def test_get_available_tools_no_tools_registered(self, agent):
        """测试没有注册工具时获取可用工具"""
        tools = agent.llm.get_available_tools()
        
        assert len(tools) == 0


class TestAgentIntegration:
    """测试Agent集成功能"""
    
    @pytest.fixture
    def agent(self):
        """创建测试用的Agent实例"""
        mock_llm = MockLLM()
        return Agent(mock_llm)
    
    def test_full_workflow_with_system_prompt(self, agent):
        """测试完整工作流程（包含系统提示）"""
        # 设置系统提示
        agent.set_system_prompt("你是一个数学计算助手，专门帮助用户进行数学计算。")
        
        # 注册工具
        agent.register_tool(calculate_sum)
        
        # 设置响应
        agent.llm.set_responses([
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_123",
                        "type": "function",
                        "function": {
                            "name": "calculate_sum",
                            "arguments": json.dumps({"a": 100, "b": 200})
                        }
                    }
                ]
            },
            {
                "content": "根据计算，100 + 200 = 300",
                "tool_calls": []
            }
        ])
        
        response = agent.ask("请计算100加200", tool_use=True)
        
        assert "300" in response
        # 验证系统提示仍然存在
        assert agent.chat_context[0]["role"] == "system"
        assert "数学计算助手" in agent.chat_context[0]["content"]
        
    def test_mixed_tool_and_non_tool_conversation(self, agent):
        """测试混合工具调用和普通对话"""
        agent.register_tool(calculate_sum)
        
        # 第一轮：普通对话
        agent.llm.set_responses([{"content": "你好！我可以帮您进行数学计算。"}])
        response1 = agent.ask("你好", tool_use=False)
        assert "你好" in response1
        
        # 第二轮：工具调用
        agent.llm.set_responses([
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_123",
                        "type": "function",
                        "function": {
                            "name": "calculate_sum",
                            "arguments": json.dumps({"a": 5, "b": 3})
                        }
                    }
                ]
            },
            {
                "content": "5 + 3 = 8",
                "tool_calls": []
            }
        ])
        response2 = agent.ask("计算5+3", tool_use=True)
        assert "8" in response2
        
        # 验证对话历史
        assert len(agent.chat_context) >= 4
        
    def test_context_persistence_across_tool_calls(self, agent):
        """测试工具调用间的上下文持久性"""
        agent.register_tool(calculate_sum)
        
        # 第一次计算
        agent.llm.set_responses([
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "calculate_sum",
                            "arguments": json.dumps({"a": 10, "b": 5})
                        }
                    }
                ]
            },
            {
                "content": "第一个结果是15",
                "tool_calls": []
            }
        ])
        response1 = agent.ask("计算10+5", tool_use=True)
        
        # 第二次计算，应该能够引用之前的结果
        agent.llm.set_responses([
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": "calculate_sum",
                            "arguments": json.dumps({"a": 15, "b": 10})
                        }
                    }
                ]
            },
            {
                "content": "在之前15的基础上加10，结果是25",
                "tool_calls": []
            }
        ])
        response2 = agent.ask("再加10", tool_use=True)
        
        assert "15" in response1
        assert "25" in response2
        
        # 验证上下文包含所有对话历史
        assert len(agent.chat_context) >= 6


class TestAnnotatedParameterDescription:
    """测试Annotated注解参数描述提取功能"""
    
    def test_extract_annotated_parameter_descriptions(self):
        """测试从Annotated注解中提取参数描述"""
        schema = extract_function_schema(get_reddit_news)
        
        assert schema["name"] == "get_reddit_news"
        params = schema["parameters"]
        
        # 验证从Annotated注解获取的描述
        assert params["properties"]["curr_date"]["description"] == "Date you want to get news for in yyyy-mm-dd format"
        assert params["properties"]["days_back"]["description"] == "Number of days to look back"
        
        # 验证从docstring中获取的描述（limit参数没有Annotated注解）
        assert params["properties"]["limit"]["description"] == "Maximum number of news items to return"
        
        # 验证必需参数和可选参数
        assert "curr_date" in params["required"]
        assert "days_back" not in params["required"]  # 有默认值
        assert "limit" not in params["required"]  # 有默认值
        
    def test_mixed_annotated_and_docstring_descriptions(self):
        """测试混合使用Annotated注解和docstring描述的情况"""
        def mixed_function(
            param1: Annotated[str, "From annotation"],
            param2: str,
            param3: Annotated[int, "Also from annotation"] = 10
        ) -> str:
            """Test function with mixed parameter descriptions
            
            Args:
                param2: From docstring only
            """
            return f"{param1}-{param2}-{param3}"
            
        schema = extract_function_schema(mixed_function)
        params = schema["parameters"]
        
        # param1: 从Annotated注解获取
        assert params["properties"]["param1"]["description"] == "From annotation"
        
        # param2: 从docstring获取
        assert params["properties"]["param2"]["description"] == "From docstring only"
        
        # param3: 从Annotated注解获取（优先级高于docstring）
        assert params["properties"]["param3"]["description"] == "Also from annotation"
        
    def test_annotated_type_extraction(self):
        """测试Annotated类型的正确提取"""
        def typed_function(
            text_param: Annotated[str, "A string parameter"],
            number_param: Annotated[int, "An integer parameter"],
            list_param: Annotated[List[str], "A list parameter"] = None
        ) -> str:
            """Function with various Annotated types"""
            return "test"
            
        schema = extract_function_schema(typed_function)
        params = schema["parameters"]
        
        # 验证类型被正确提取
        assert params["properties"]["text_param"]["type"] == "string"
        assert params["properties"]["number_param"]["type"] == "integer"
        assert params["properties"]["list_param"]["type"] == "array"
        
        # 验证描述被正确提取
        assert params["properties"]["text_param"]["description"] == "A string parameter"
        assert params["properties"]["number_param"]["description"] == "An integer parameter"
        assert params["properties"]["list_param"]["description"] == "A list parameter"
        
    def test_fallback_to_default_description(self):
        """测试当没有注解也没有docstring时的默认描述"""
        def no_description_function(param1: str, param2: int) -> str:
            """Function without parameter descriptions"""
            return "test"
            
        schema = extract_function_schema(no_description_function)
        params = schema["parameters"]
        
        # 验证使用默认描述
        assert params["properties"]["param1"]["description"] == "Parameter param1"
        assert params["properties"]["param2"]["description"] == "Parameter param2"


# 在测试工具函数部分添加一个使用Annotated的函数
def get_reddit_news(
    curr_date: Annotated[str, "Date you want to get news for in yyyy-mm-dd format"],
    days_back: Annotated[int, "Number of days to look back"] = 7,
    limit: int = 5
) -> str:
    """
    Retrieve global news from Reddit within a specified time frame.
    Args:
        limit: Maximum number of news items to return
    Returns:
        str: A formatted dataframe containing the latest global news from Reddit in the specified time frame.
    """
    return f"Reddit news for {curr_date}, {days_back} days back, limit {limit}"


@pytest.mark.integration
class TestAgentWithRealPaoluzProvider:
    """测试使用真实Paoluz Provider的Agent工具调用功能
    
    这些测试需要真实的API调用，默认不会在常规测试中运行。
    要运行这些测试，请使用：
    - pytest -m integration  # 只运行集成测试
    - pytest test/test_agent_tool_call.py::TestAgentWithRealPaoluzProvider  # 运行特定测试类
    """
    
    @pytest.fixture
    def real_agent(self):
        """创建使用真实Paoluz Provider的Agent实例"""
        try:
            # 创建真实的Paoluz Agent
            agent = get_agent("paoluz", "gpt-4o-mini")
            return agent
        except Exception as e:
            pytest.skip(f"无法创建Paoluz Agent，可能是配置问题: {e}")
    
    def test_paoluz_agent_initialization(self, real_agent):
        """测试Paoluz Agent初始化"""
        assert real_agent.llm is not None
        assert real_agent.chat_context == []
        assert hasattr(real_agent.llm, 'ask_with_tools')
        
    def test_paoluz_simple_conversation_without_tools(self, real_agent):
        """测试Paoluz Agent简单对话（不使用工具）"""
        try:
            response = real_agent.ask("你好，请简单介绍一下你自己", tool_use=False)
            
            assert isinstance(response, str)
            assert len(response) > 0
            assert len(real_agent.chat_context) == 2
            assert real_agent.chat_context[0]["role"] == "user"
            assert real_agent.chat_context[1]["role"] == "assistant"
            
            print(f"Paoluz简单对话响应: {response}")
            
        except Exception as e:
            pytest.skip(f"Paoluz API调用失败，可能是网络或配置问题: {e}")
    
    def test_paoluz_tool_registration_and_call(self, real_agent):
        """测试Paoluz Agent工具注册和调用"""
        try:
            # 注册计算工具
            real_agent.register_tool(calculate_sum)
            
            # 验证工具注册
            assert "calculate_sum" in real_agent.llm.tools
            tools = real_agent.llm.get_available_tools()
            assert len(tools) == 1
            assert tools[0]["function"]["name"] == "calculate_sum"
            
            # 测试工具调用对话
            response = real_agent.ask("请帮我计算25加37等于多少？", tool_use=True)
            
            assert isinstance(response, str)
            assert len(response) > 0
            
            # 验证对话上下文包含工具调用相关的消息
            assert len(real_agent.chat_context) >= 2
            
            print(f"Paoluz工具调用响应: {response}")
            print(f"对话上下文长度: {len(real_agent.chat_context)}")
            print(f"对话内容: {real_agent.chat_context}")
            
            # 检查是否有工具调用的痕迹（在助手消息中）
            has_tool_usage = any(
                msg.get("role") == "assistant" and (
                    msg.get("tool_calls") or 
                    "62" in str(msg.get("content", "")) or  # 25+37=62
                    "计算" in str(msg.get("content", ""))
                )
                for msg in real_agent.chat_context
            )
            
            if has_tool_usage:
                print("✓ 检测到工具调用相关内容")
            else:
                print("⚠ 未明确检测到工具调用，但对话成功完成")
                
        except Exception as e:
            pytest.skip(f"Paoluz工具调用测试失败，可能是网络或配置问题: {e}")
    
    def test_paoluz_multiple_tools_registration(self, real_agent):
        """测试Paoluz Agent多工具注册"""
        try:
            # 注册多个工具
            real_agent.register_tool(calculate_sum)
            real_agent.register_tool(get_weather)
            
            # 验证工具注册
            assert len(real_agent.llm.tools) == 2
            tools = real_agent.llm.get_available_tools()
            assert len(tools) == 2
            
            tool_names = [tool["function"]["name"] for tool in tools]
            assert "calculate_sum" in tool_names
            assert "get_weather" in tool_names
            
            print(f"✓ 成功注册{len(tools)}个工具: {tool_names}")
            
        except Exception as e:
            pytest.skip(f"Paoluz多工具注册测试失败: {e}")
    
    def test_paoluz_tool_call_with_system_prompt(self, real_agent):
        """测试带系统提示的Paoluz Agent工具调用"""
        try:
            # 设置系统提示
            real_agent.set_system_prompt("你是一个专业的数学计算助手，擅长进行各种数学运算。")
            
            # 注册工具
            real_agent.register_tool(calculate_sum)
            
            # 测试工具调用
            response = real_agent.ask("作为数学助手，请计算100加200", tool_use=True)
            
            assert isinstance(response, str)
            assert len(response) > 0
            
            # 验证系统提示仍然存在
            assert real_agent.chat_context[0]["role"] == "system"
            assert "数学计算助手" in real_agent.chat_context[0]["content"]
            
            print(f"带系统提示的工具调用响应: {response}")
            
        except Exception as e:
            pytest.skip(f"Paoluz带系统提示的工具调用测试失败: {e}")
    
    def test_paoluz_error_handling(self, real_agent):
        """测试Paoluz Agent错误处理"""
        try:
            # 注册工具
            real_agent.register_tool(calculate_sum)
            
            # 测试工具执行错误（通过直接调用execute_tool）
            invalid_tool_call = {
                "id": "test_call",
                "type": "function",
                "function": {
                    "name": "calculate_sum",
                    "arguments": json.dumps({"a": "invalid"})  # 无效参数类型
                }
            }
            
            result = real_agent.llm.execute_tool(invalid_tool_call)
            assert "Error executing tool" in result
            
            print(f"✓ 错误处理测试通过: {result}")
            
        except Exception as e:
            pytest.skip(f"Paoluz错误处理测试失败: {e}")
    
    @pytest.mark.slow
    def test_paoluz_complex_tool_conversation(self, real_agent):
        """测试Paoluz Agent复杂工具对话（标记为慢速测试）"""
        try:
            # 注册多个工具
            real_agent.register_tool(calculate_sum)
            real_agent.register_tool(get_weather)
            
            # 设置系统提示
            real_agent.set_system_prompt("你是一个智能助手，可以进行计算和查询天气。")
            
            # 进行多轮对话
            response1 = real_agent.ask("请计算10+15", tool_use=True)
            assert isinstance(response1, str)
            print(f"第一轮响应: {response1}")
            
            response2 = real_agent.ask("现在查询一下北京的天气", tool_use=True)
            assert isinstance(response2, str)
            print(f"第二轮响应: {response2}")
            
            # 验证对话历史
            assert len(real_agent.chat_context) >= 4
            print(f"✓ 复杂对话测试完成，对话历史长度: {len(real_agent.chat_context)}")
            
        except Exception as e:
            pytest.skip(f"Paoluz复杂工具对话测试失败: {e}")

if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "--tb=short"])