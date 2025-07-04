import abc
import inspect
import json
from typing import (
    TypedDict,
    Literal,
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
        "response_format": Optional[Literal["json"]],
        "max_token": Optional[int],
        "api_key": Optional[str],
        "endpoint": Optional[str],
        "tools": Optional[List[Dict[str, Any]]],  # 新增工具定义
    },
)

# 新增工具调用相关的类型定义
ToolCall = TypedDict("ToolCall", {"id": str, "type": str, "function": Dict[str, Any]})

ToolResponse = TypedDict(
    "ToolResponse", {"tool_call_id": str, "role": str, "content": str}
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
        },
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


class LlmAbstract(abc.ABC):
    def __init__(self, model: str, **system_params):
        self.model = model
        self.params: LlmParams = system_params
        self.tools: Dict[str, Callable] = {}  # 存储工具函数

    @abc.abstractmethod
    def ask(self, context: List) -> str:
        raise Exception("Not-Implement")

    @abc.abstractmethod
    def ask_with_tools(
        self, context: List, available_tools: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """支持工具调用的请求方法

        Args:
            context: 对话上下文
            available_tools: 可用工具列表，None表示使用所有工具

        Returns:
            包含content和tool_calls的字典
        """
        raise Exception("Not-Implement")

    def register_tool(self, func: Callable) -> Dict[str, Any]:
        """自动从函数签名注册工具"""
        schema = extract_function_schema(func)
        self.tools[schema["name"]] = func

        tool_def = {"type": "function", "function": schema}

        if "tools" not in self.params or self.params["tools"] is None:
            self.params["tools"] = []
        self.params["tools"].append(tool_def)

        return schema  # 返回schema供调试使用

    def execute_tool(self, tool_call: ToolCall) -> str:
        """执行工具调用"""
        function_name = tool_call["function"]["name"]
        function_args = json.loads(tool_call["function"]["arguments"])

        if function_name in self.tools:
            try:
                result = self.tools[function_name](**function_args)
                return str(result)
            except Exception as e:
                logger.error(f"Error executing tool {function_name}: {str(e)}")
                return f"Error executing tool {function_name}: {str(e)}"
        else:
            return f"Tool {function_name} not found"

    def get_available_tools(
        self, tool_names: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """获取可用工具列表"""
        if not self.params.get("tools"):
            return []

        if tool_names is None:
            return self.params["tools"]

        # 筛选指定的工具
        available_tools = []
        for tool in self.params["tools"]:
            if tool["function"]["name"] in tool_names:
                available_tools.append(tool)

        return available_tools


class Agent:
    def __init__(self, llm: LlmAbstract):
        self.llm = llm
        self.chat_context = []

    def ask(self, question: str, tool_use: Union[bool, List[str]] = False) -> str:
        """发送问题并获取回答

        Args:
            question: 用户问题
            tool_use: 工具使用控制
                     - False: 不使用工具
                     - True: 使用所有可用工具
                     - List[str]: 使用指定名称的工具列表
        """
        self.chat_context.append({"role": "user", "content": question})

        # 确定是否使用工具
        if tool_use is False:
            # 不使用工具
            rsp_message = self.llm.ask(self.chat_context)
            self.chat_context.append({"role": "assistant", "content": rsp_message})
            return rsp_message
        else:
            # 使用工具（tool_use为True或List[str]）
            return self._handle_tool_conversation(tool_use)

    def _handle_tool_conversation(self, tool_use: Union[bool, List[str]]) -> str:
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
                response = self.llm.ask_with_tools(self.chat_context, available_tools)

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
                    tool_result = self.llm.execute_tool(tool_call)
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
                logger.error(f"Error in tool conversation: {str(e)}")
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


__all__ = [
    "LlmAbstract",
    "Agent",
    "extract_function_schema",
    "ToolCall",
    "ToolResponse",
]
