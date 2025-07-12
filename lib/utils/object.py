import json
from typing import List

def remove_none(obj: dict) -> dict:
    return {k: v for k, v in obj.items() if v is not None}


def omit_keys(obj: dict, keys: List[str]) -> dict:
    return {k: v for k, v in obj.items() if k not in keys}


def pick_keys(obj: dict, keys: List[str]) -> dict:
    return {k: v for k, v in obj.items() if k in keys}

def pretty_output(obj: dict|list) -> str:
    """
    将字典或列表转换为格式化的字符串输出
    """
    return json.dumps(obj, indent=2, ensure_ascii=False)