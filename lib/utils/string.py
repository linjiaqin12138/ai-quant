import random
import string
import json
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


def extract_json_string(s: str) -> Optional[dict]:
    start_index = s.find("{")
    end_index = s.rfind("}")

    if start_index != -1 and end_index != -1:
        return try_parse_json(s[start_index : end_index + 1])
    else:
        return None


def url_encode(s: str) -> str:
    return quote(s, safe="")
