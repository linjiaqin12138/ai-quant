import json
import traceback
from typing import Optional, List, Dict, Any, Callable, Union

from lib.adapter.llm import get_llm
from lib.logger import logger
from lib.adapter.llm.interface import LlmAbstract, extract_function_schema

class Agent:
    def __init__(self, llm: LlmAbstract):
        self.llm = llm
        self.chat_context = []
        self.tools = {}  # 注册的工具函数
        self.tool_schemas = []  # 工具的schema定义

    def register_tool(self, func: Callable) -> Dict[str, Any]:
        """注册工具函数"""
        tool_schema = extract_function_schema(func)
        self.tools[func.__name__] = func
        self.tool_schemas.append({
            "type": "function",
            "function": tool_schema
        })
        logger.debug(f"Tool registered: {func.__name__}")
        return tool_schema

    def execute_tool(self, tool_call: Dict[str, Any]) -> str:
        """执行工具调用"""
        function_name = tool_call["function"]["name"]
        arguments = tool_call["function"]["arguments"]
        
        if function_name not in self.tools:
            return f"Error: Tool '{function_name}' not found"
        
        try:
            # 解析参数
            if isinstance(arguments, str):
                args = json.loads(arguments)
            else:
                args = arguments
            
            # 执行工具函数
            result = self.tools[function_name](**args)
            
            # 确保返回字符串
            if isinstance(result, str):
                return result
            else:
                return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error executing tool {function_name}: {str(e)}")
            return f"Error executing tool {function_name}: {str(e)}"

    def ask(self, question: str, tool_use: Union[bool, List[str]] = False, json_response: Optional[bool] = False) -> str:
        """发送问题并获取回答

        Args:
            question: 用户问题
            tool_use: 工具使用控制
                     - False: 不使用工具
                     - True: 使用所有可用工具
                     - List[str]: 使用指定名称的工具列表
            json_response: 是否返回JSON格式的响应（仅在支持时有效）
        """
        self.chat_context.append({"role": "user", "content": question})

        # 确定是否使用工具
        if tool_use is False:
            # 不使用工具
            response = self.llm.chat(
                self.chat_context, 
                tools=None, 
                response_format='json_object' if json_response else None
            )
            content = response.get("content", "")
            self.chat_context.append({"role": "assistant", "content": content})
            return content
        else:
            # 使用工具（tool_use为True或List[str]）
            return self._handle_tool_conversation(tool_use, response_format='json_object' if json_response else None)

    def _handle_tool_conversation(self, tool_use: Union[bool, List[str]], response_format: Optional[str] = None) -> str:
        """处理包含工具调用的对话"""
        iteration = 0
        
        # 准备工具定义
        if tool_use is True:
            # 使用所有工具
            available_tools = self.tool_schemas
        elif isinstance(tool_use, list):
            # 使用指定的工具
            available_tools = [
                schema for schema in self.tool_schemas 
                if schema['function']['name'] in tool_use
            ]
        else:
            available_tools = []

        while True:
            iteration += 1

            # 超过5轮时发出警告
            if iteration > 5:
                logger.warning(
                    f"Tool conversation exceeded 5 iterations, current iteration: {iteration}"
                )

            try:
                response = self.llm.chat(self.chat_context, tools=available_tools, response_format=response_format)

                # 如果没有工具调用，直接返回消息
                if not response.get("tool_calls"):
                    content = response.get("content", "")
                    self.chat_context.append({"role": "assistant", "content": content})
                    return content

                # 添加助手的工具调用消息
                self.chat_context.append(
                    {
                        "role": "assistant",
                        "content": response.get("content", ""),
                        "tool_calls": response["tool_calls"],
                    }
                )

                # 执行所有工具调用
                for tool_call in response["tool_calls"]:
                    logger.info(f"Executing tool call... {tool_call['function']['name']}")
                    logger.debug(f"Executing tool call: {tool_call['function']['name']} with params: {tool_call['function']['arguments']}")
                    tool_result = self.execute_tool(tool_call)
                    logger.debug(f"Executed tool call: {tool_call['function']['name']} with result: {tool_result}")
                    self.chat_context.append(
                        {
                            "tool_call_id": tool_call["id"],
                            "role": "tool",
                            "content": tool_result,
                        }
                    )

                # 如果只有工具调用没有文本内容，继续下一轮
                if not response.get("content"):
                    continue
                else:
                    return response["content"]

            except Exception as e:
                logger.error(f"Error in tool conversation: {str(e)} {traceback.format_exc()}")
                return f"Error occurred during tool conversation: {str(e)}"

    def set_system_prompt(self, prompt: str):
        self.chat_context = [{"role": "system", "content": prompt}]

    def clear(self):
        if self.chat_context and self.chat_context[0]["role"] == "system":
            self.chat_context = self.chat_context[:1]
        else:
            self.chat_context = []


def get_agent(provider: Optional[str] = 'paoluz', model: Optional[str] = 'gpt-4o-mini', llm: Optional[LlmAbstract] = None, **params) -> Agent:
    """创建Agent实例的工厂函数

    Args:
        provider: 可选的LLLM提供商名称
        model: 可选的模型名称
        llm: 可选的LLM实例
        **params: 其他参数

    Returns:
        Agent实例
    """
    if llm is None:
        llm = get_llm(provider, model, **params)
    return Agent(llm)