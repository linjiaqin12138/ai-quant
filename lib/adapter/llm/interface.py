import abc
import inspect
import json
from typing import (
    Literal,
    TypedDict,
    Optional,
    List,
    Dict,
    Any,
    Callable,
    Union,
    get_type_hints,
    get_origin,
    get_args,
)

import requests

from lib.utils.object import pretty_output

# 兼容不同Python版本的Annotated导入
try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated

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

def extract_function_schema(func: Callable) -> Dict[str, Any]:
    """从函数签名和文档字符串中提取工具参数schema"""
    signature = inspect.signature(func)
    type_hints = get_type_hints(func, include_extras=True)  # 包含Annotated信息
    docstring = inspect.getdoc(func) or ""

    # 解析文档字符串获取参数描述
    param_descriptions = {}
    if docstring:
        lines = docstring.split("\n")
        current_section = None
        for line in lines:
            stripped_line = line.strip()
            if stripped_line.lower().startswith("args:") or stripped_line.lower().startswith("parameters:"):
                current_section = "params"
                continue
            elif current_section == "params" and stripped_line and ":" in stripped_line:
                # 参数描述行，格式如: param_name: description
                # 处理缩进情况
                if line.startswith("    ") or line.startswith("\t") or not line.startswith(" "):
                    parts = stripped_line.split(":", 1)
                    if len(parts) == 2:
                        param_name = parts[0].strip()
                        description = parts[1].strip()
                        param_descriptions[param_name] = description
            elif current_section == "params" and stripped_line and not stripped_line.startswith(" ") and ":" not in stripped_line:
                # 如果遇到不是参数格式的行，可能已经退出Args部分
                current_section = None

    # 构建参数schema
    properties = {}
    required = []

    for param_name, param in signature.parameters.items():
        if param_name == "self":
            continue

        param_type = type_hints.get(param_name, str)
        
        # 首先尝试从Annotated注解中获取描述
        param_description = None
        
        # 检查是否为Annotated类型
        if get_origin(param_type) is Annotated:
            args = get_args(param_type)
            if len(args) >= 2 and isinstance(args[1], str):
                param_description = args[1]
                # 使用Annotated的第一个参数作为实际类型
                actual_type = args[0]
            else:
                actual_type = param_type
        else:
            actual_type = param_type
        
        # 如果没有从注解获取到描述，则从docstring获取
        if param_description is None:
            param_description = param_descriptions.get(param_name, f"Parameter {param_name}")

        param_schema = _type_to_json_schema(actual_type)
        param_schema["description"] = param_description

        properties[param_name] = param_schema

        # 检查是否为必需参数
        if param.default == inspect.Parameter.empty:
            # 如果没有默认值，进一步检查是否是Optional类型
            if not (get_origin(param_type) is Union and type(None) in get_args(param_type)):
                required.append(param_name)

    # 获取函数描述（文档字符串的第一行）
    description = docstring.split("\n")[0] if docstring else f"Function {func.__name__}"

    return {
        "name": func.__name__,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        }
    }


def _type_to_json_schema(python_type) -> Dict[str, Any]:
    """将Python类型转换为JSON Schema格式"""
    if python_type == str:
        return {"type": "string"}
    elif python_type == int:
        return {"type": "integer"}
    elif python_type == float:
        return {"type": "number"}
    elif python_type == bool:
        return {"type": "boolean"}
    elif python_type == list or str(python_type).startswith("typing.List"):
        return {"type": "array"}
    elif python_type == dict or str(python_type).startswith("typing.Dict"):
        return {"type": "object"}
    elif hasattr(python_type, "__origin__"):
        # 处理泛型类型
        if python_type.__origin__ == list:
            return {"type": "array"}
        elif python_type.__origin__ == dict:
            return {"type": "object"}
        elif python_type.__origin__ == Union:
            # 处理Optional类型
            args = python_type.__args__
            if len(args) == 2 and type(None) in args:
                non_none_type = args[0] if args[1] == type(None) else args[1]
                return _type_to_json_schema(non_none_type)
    else:
        return {"type": "string"}  # 默认为字符串类型

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
        response_format: Optional[Literal['json_object']] = None
    ) -> ChatResponse:
        """统一的聊天接口
        
        Args:
            messages: 消息列表
            tools: 工具定义列表，None表示不使用工具
            tool_choice: 工具选择策略，'auto'表示自动选择工具
            response_format: 响应格式，如'json_object'
            
        Returns:
            ChatResponse: 包含content和tool_calls的响应
        """
        raise NotImplementedError("chat method must be implemented")

    # 为了向后兼容，保留原有方法但标记为过时
    def ask(self, context: List, response_format: Optional[str] = None) -> str:
        """向后兼容的ask方法，已过时，请使用chat方法"""
        logger.warning("ask method is deprecated, please use chat method instead")
        response = self.chat(context, tools=None, response_format=response_format)
        return response.get("content", "")

    def ask_with_tools(
        self, context: List, available_tools: Optional[List[str]] = None, response_format: Optional[str] = None
    ) -> Dict[str, Any]:
        """向后兼容的ask_with_tools方法，已过时，请使用chat方法"""
        logger.warning("ask_with_tools method is deprecated, please use chat method instead")
        # 这里无法直接转换available_tools，因为需要Agent层的工具管理
        response = self.chat(context, tools=None, response_format=response_format)
        return response


__all__ = [
    "LlmAbstract",
    "LlmParams",
    "ToolCall",
    "ToolResponse", 
    "ChatResponse",
    "extract_function_schema",
]
