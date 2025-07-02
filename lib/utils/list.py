from typing import List, Any, Dict, Callable, TypeVar

T = TypeVar("T")
U = TypeVar("U")


def filter_by(arr: List[T], filter: Callable[[T], bool]) -> List[T]:
    return [x for x in arr if filter(x)]


def map_by(arr: List[T], mapper: Callable[[T], U]) -> List[U]:
    return [mapper(x) for x in arr]


def group_by(arr: List[T], grouper: Callable[[T], str]) -> Dict[str, List[T]]:
    result: Dict[str, List[T]] = {}
    for item in arr:
        key = grouper(item)
        if key not in result:
            result[key] = []
        result[key].append(item)
    return result


def reverse(arr: List[T]) -> List[T]:
    return list(reversed(arr))


def random_pick(arr: List[T]) -> T:
    pass
