import abc
from typing import (
    Literal,
    TypedDict,
    Optional,
    List,
    Dict,
    Any,
)

import requests

from lib.utils.object import pretty_output
from lib.logger import logger

LlmParams = TypedDict(
    "LlmParams",
    {
        "temperature": Optional[float],
        "top_p": Optional[float],
        "frequency_penalty": Optional[float],
        "presence_penalty": Optional[float],
        "max_token": Optional[int],
        "api_key": Optional[str],
        "endpoint": Optional[str],
    },
)

# 工具调用相关的类型定义
ToolCall = TypedDict("ToolCall", {"id": str, "type": str, "function": Dict[str, Any]})
ToolCallFunctionDef = TypedDict(
    "ToolCallFunctionDef",
    {
        "name": str,
        "description": str,
        "parameters": Dict[str, Any], # JSON Schema Object
        'strict': bool
    },
)
ToolCallReq = TypedDict(
    "ToolCallReq",
    {
        "type": Literal['function'],
        "function": ToolCallFunctionDef,
    },
)
ToolResponse = TypedDict(
    "ToolResponse", {"tool_call_id": str, "role": str, "content": str}
)

# 聊天响应类型定义
ChatResponse = TypedDict(
    "ChatResponse", 
    {
        "content": Optional[str],
        "tool_calls": Optional[List[ToolCall]],
    }
)

def debug_req(method: str, endpoint: str, path: str, headers: dict, body_json: dict):
    """Debug request content for logging."""
    logger.debug(f"Request URL: {method.upper()} {endpoint}{path}")
    logger.debug(f"Request Header: {pretty_output(headers)}")
    logger.debug(f"Request JSON: {pretty_output(body_json)}")


def debug_rsp(rsp: requests.Response):
    """Debug response content for logging."""
    # logger.debug(f"Response Status Code: {rsp.status_code}")
    logger.debug(f"Response Header: {pretty_output(dict(rsp.headers))}")
    try:
        logger.debug(f"Response JSON: {pretty_output(rsp.json())}")
    except requests.exceptions.JSONDecodeError:
        logger.debug(f"Response Text: {rsp.text}")

class LlmAbstract(abc.ABC):
    """LLM抽象基类，专注于不同provider的聊天接口适配"""
    provider: str # 提供商名称, 子类hardcode

    def __init__(self, model: str, **system_params):
        self.model = model
        self.params: LlmParams = system_params

    @abc.abstractmethod
    def chat(
        self, 
        messages: List[Dict[str, Any]], 
        tools: Optional[List[ToolCallReq]] = None,
        tool_choice: Literal['auto', 'required', 'none'] = None,
        response_format: Optional[Literal['json_object']] = None,
        stream: bool = False  # 新增参数，控制是否流式输出
    ) -> ChatResponse:
        """
        统一的聊天接口
        
        Args:
            messages: 消息列表
            tools: 工具定义列表，None表示不使用工具
            tool_choice: 工具选择策略，'auto'表示自动选择工具
            response_format: 响应格式，如'json_object'
            stream: 是否流式输出（仅部分实现支持）
        Returns:
            ChatResponse: 包含content和tool_calls的响应
        """
        raise NotImplementedError("chat method must be implemented")


__all__ = [
    "LlmAbstract",
    "LlmParams",
    "ToolCall",
    "ToolResponse", 
    "ChatResponse",
    "extract_function_schema",
]
