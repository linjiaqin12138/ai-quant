import json
import traceback
from typing import Optional, List, Dict, Any, Callable, Union

from lib.logger import logger
from lib.adapter.llm.interface import LlmAbstract


class Agent:
    def __init__(self, llm: LlmAbstract):
        self.llm = llm
        self.chat_context = []

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
            rsp_message = self.llm.ask(self.chat_context, response_format='json_object' if json_response else None)
            self.chat_context.append({"role": "assistant", "content": rsp_message})
            return rsp_message
        else:
            # 使用工具（tool_use为True或List[str]）
            return self._handle_tool_conversation(tool_use, response_format='json_object' if json_response else None)

    def _handle_tool_conversation(self, tool_use: Union[bool, List[str]], response_format: Optional[str] = None) -> str:
        """处理包含工具调用的对话"""
        iteration = 0
        available_tools = None if tool_use is True else tool_use

        while True:
            iteration += 1

            # 超过5轮时发出警告
            if iteration > 5:
                logger.warning(
                    f"Tool conversation exceeded 5 iterations, current iteration: {iteration}"
                )

            try:
                response = self.llm.ask_with_tools(self.chat_context, available_tools, response_format)

                # 如果没有工具调用，直接返回消息
                if "tool_calls" not in response or not response["tool_calls"]:
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
                    tool_result = self.llm.execute_tool(tool_call)
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

    def register_tool(self, func: Callable) -> Dict[str, Any]:
        """注册工具函数"""
        return self.llm.register_tool(func)

    def set_system_prompt(self, prompt: str):
        self.chat_context = [{"role": "system", "content": prompt}]

    def clear(self):
        if self.chat_context and self.chat_context[0]["role"] == "system":
            self.chat_context = self.chat_context[:1]
        else:
            self.chat_context = []


def get_agent(provider: str, model: str, **params) -> Agent:
    """创建Agent实例的工厂函数

    Args:
        provider: LLM提供商名称
        model: 模型名称
        **params: 其他参数

    Returns:
        Agent实例
    """
    from lib.adapter.llm import get_llm
    llm = get_llm(provider, model, **params)
    return Agent(llm)