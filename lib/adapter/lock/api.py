import random
from abc import ABC, abstractmethod
from typing import Callable, Optional, TypedDict
import time

from ...logger import logger

Options = TypedDict(
    "LockOptions", {"name": str, "max_concurrent_access": int, "expiration_time": int}
)


class AcquireLockFailed(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class DistributedLock(ABC):
    def __init__(self, **kwargs: Options):
        self.name = kwargs["name"]
        self.max_concurrent_access = kwargs["max_concurrent_access"]
        self.expiration_time = kwargs["expiration_time"]

    @abstractmethod
    def available(self) -> bool:
        pass

    def wait(self, timeout: Optional[float]) -> str:
        start_time = time.time()
        max_sleep_time = 0.1  # Start with 0.1 second

        def wait_for_a_while():
            nonlocal max_sleep_time  # 访问外部函数的变量，且需要修改它
            wait_time = random.uniform(0, max_sleep_time)
            logger.info(f"Wait for {wait_time} seconds")
            max_sleep_time = min(max_sleep_time * 2, 1)
            time.sleep(wait_time)

        while True:
            current_time = time.time()
            if timeout is not None and (current_time - start_time) > timeout:
                raise TimeoutError("Failed to acquire lock within the given timeout.")

            if not self.available():
                logger.info(f"{self.name} is not available")
                wait_for_a_while()
                continue

            try:
                return self.acquire()
            except AcquireLockFailed:
                logger.info(f"Retry acquire lock of {self.name}")
                wait_for_a_while()

    @abstractmethod
    def acquire(self) -> str:
        pass

    @abstractmethod
    def release(self) -> bool:
        pass


CreateLockFactory = Callable[[Options], DistributedLock]
