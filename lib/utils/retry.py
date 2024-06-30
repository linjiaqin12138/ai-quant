
from typing import TypeVar, Callable, Tuple, Any
import time
from ..logger import logger

G = TypeVar("G")

def with_retry(retry_errors: Tuple[Exception], max_retry_times: int) -> Callable[[G], G]:
    def decorator(function: G) -> G:
        def function_with_retry(*args, **kwargs) -> Any:
            count = 0
            while True:
                try:
                    return function(*args, **kwargs)
                except retry_errors as e:
                    count += 1
                    logger.warn(f"Retry {function} {count} times")
                    time.sleep(2 ** (count - 1))
                    if count >= max_retry_times:
                        raise e

        return function_with_retry
    return decorator