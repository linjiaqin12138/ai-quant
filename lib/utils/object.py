from typing import List

def remove_none(obj: dict)->dict:
    return {k: v for k, v in obj.items() if v is not None}

def omit_keys(obj: dict, keys: List[str]) -> dict:
    return {k: v for k, v in obj.items() if k not in keys}

def pick_keys(obj: dict, keys: List[str]) -> dict:
    return {k: v for k, v in obj.items() if k in keys}