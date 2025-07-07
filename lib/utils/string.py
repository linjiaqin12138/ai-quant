import random
import string
import json
import re
from hashlib import sha256
from typing import Optional
from urllib.parse import quote


def random_id(length: int = 10) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def hash_str(input_string: str) -> str:
    hash_object = sha256(input_string.encode())
    hash_hex = hash_object.hexdigest()
    return hash_hex


def try_parse_json(s: str) -> Optional[dict]:
    try:
        return json.loads(s)
    except:
        return None


def has_json_features(s: str) -> bool:
    """
    检查字符串是否包含JSON特征字符
    
    Args:
        s: 要检查的字符串
        
    Returns:
        如果包含JSON特征字符返回True，否则返回False
    """
    # 检查是否包含JSON的基本特征字符
    json_chars = ['{', '}', '[', ']', '":', '":"', '"', ',']
    return any(char in s for char in json_chars)


def extract_json_string(s: str) -> Optional[dict | list]:
    """
    从字符串中提取JSON对象或数组
    使用更智能的方法来处理嵌套的括号和引号
    注意：这是一个无副作用的工具函数，不会调用外部API
    """
    start_index = s.find("{")
    end_index = s.rfind("}")

    if start_index != -1 and end_index != -1:
        try_json_parse = try_parse_json(s[start_index : end_index + 1])
        if try_json_parse is not None:
            return try_json_parse 
    
    start_index = s.find("[")
    end_index = s.rfind("]")

    if start_index != -1 and end_index != -1:
        return try_parse_json(s[start_index : end_index + 1])
    
    return None


def url_encode(s: str) -> str:
    return quote(s, safe="")
