import json
import traceback
from typing import Optional, List, Dict, Any, Callable, TypedDict, Union

from lib.utils.function import extract_function_schema
from lib.adapter.llm import get_llm
from lib.logger import logger
from lib.adapter.llm.interface import LlmAbstract
import inspect

ToolResult = TypedDict(
    'ToolResult',
    {
        "tool_name": str,
        "parameters": Dict[str, Any],
        "success": bool,
        "content": str,
        "error_message": Optional[str]
    }
)

class Agent:
    def __init__(self, llm: LlmAbstract):
        self.llm = llm
        self.chat_context = []
        self.tools = {}  # 注册的工具函数
        self.tool_schemas = []  # 工具的schema定义
        self.tool_call_results: List[ToolResult] = []

    def register_tool(self, func: Callable):
        """注册工具函数"""
        # 检查函数返回值类型
        sig = inspect.signature(func)
        return_annotation = sig.return_annotation
        
        if return_annotation != inspect.Signature.empty:
            if return_annotation not in [str, dict]:
                logger.warning(f"Tool '{func.__name__}' return type is {return_annotation}, expected str or dict. "
                              f"The result will be converted to string in execute_tool method.")
        else:
            logger.warning(f"Tool '{func.__name__}' has no return type annotation, "
                          f"please ensure it returns a string or dict, or the result will be converted to string.")
        
        self.tools[func.__name__] = func
        self.tool_schemas.append({
            "type": "function",
            "function": extract_function_schema(func)
        })
        logger.debug(f"Tool registered: {func.__name__}")

    def execute_tool(self, tool_call: Dict[str, Any]) -> str:
        """执行工具调用"""
        function_name = tool_call["function"]["name"]
        arguments = tool_call["function"]["arguments"]
        tool_call_result: ToolResult = {
            "tool_name": function_name,
            "parameters": arguments,
            "success": False,
            "content": "",
            "error_message": None
        }
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
            if not isinstance(result, str):
                if not isinstance(result, (dict, list)):
                    logger.warning(f"Tool '{function_name}' returned a non-string type: {type(result)}, converting to string.")
                result = json.dumps(result, ensure_ascii=False)
            
            tool_call_result.update({
                "success": True,
                "content": result
            })
            return result
        except Exception as e:
            logger.error(f"Error executing tool {function_name}: {str(e)}")
            tool_call_result["error_message"] = str(e)
            return f"Error executing tool {function_name}: {str(e)}"
        finally:
            self.tool_call_results.append(tool_call_result)

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
                response_format='json_object' if json_response else None,
                stream=False
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
                response = self.llm.chat(self.chat_context, tools=available_tools, response_format=response_format, stream=False)

                # 如果没有工具调用，直接返回消息
                if not response.get("tool_calls"):
                    content = response.get("content", "").strip()
                    reasoning_content = response.get("reasoning_content", "").strip()
                    if not content and not reasoning_content:
                        logger.warning("Received empty response content, continuing to next iteration.")
                        continue
                    if reasoning_content:
                        self.chat_context.append({"role": "assistant", "content": reasoning_content})
                        continue
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

                continue
                # 如果只有工具调用没有文本内容，继续下一轮
                # if not response.get("content") or not response["content"].strip():
                #     continue

                # if 
                # else:
                #     return response["content"]

            except Exception as e:
                logger.error(f"Error in tool conversation: {str(e)} {traceback.format_exc()}")
                return f"Error occurred during tool conversation: {str(e)}"

    def set_system_prompt(self, prompt: str):
        self.chat_context = [{"role": "system", "content": prompt}]

    def clear_context(self):
        if self.chat_context and self.chat_context[0]["role"] == "system":
            self.chat_context = self.chat_context[:1]
        else:
            self.chat_context = []
        self.tool_call_results.clear()


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