import inspect
from typing import Annotated, Any, Callable, Dict, Union, get_args, get_origin, get_type_hints
# 兼容不同Python版本的Annotated导入
try:
    from typing import Annotated
except ImportError:
    from typing_extensions import Annotated


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
        return {
            "type": "array",
            "items": _type_to_json_schema(get_args(python_type)[0]) if get_args(python_type) else {}
        }
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