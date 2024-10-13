from typing import List, Any, Callable, TypeVar

def filter_by(arr: List[Any], filter: Callable[[Any], bool]) -> List[Any]:
    return [x for x in arr if filter(x)]

T = TypeVar('T')
U = TypeVar('U')
def map_by(arr: List[T], mapper: Callable[[T], U]) -> List[U]:
    return [mapper(x) for x in arr]
