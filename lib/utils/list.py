from typing import List, Any, Callable

def filter_by(arr: List[Any], filter: Callable[[Any], bool]) -> List[Any]:
    return [x for x in arr if filter(x)]