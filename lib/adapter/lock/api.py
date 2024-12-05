from abc import ABC, abstractmethod
from typing import Callable, Optional, TypedDict, Any
import time

from ...logger import logger

Options = TypedDict('LockOptions', {
    'name': str, 
    'max_concurrent_access': int, 
    'expiration_time': int
})

class DistributedLock(ABC):
    def __init__(self, **kwargs: Options):
        self.name = kwargs['name']
        self.max_concurrent_access = kwargs['max_concurrent_access']
        self.expiration_time = kwargs['expiration_time']

    def wait(self, timeout: Optional[float]) -> str:
        start_time = time.time()
        while True:
            current_time = time.time()
            if timeout is not None and (current_time - start_time) > timeout:
                raise TimeoutError("Failed to acquire lock within the given timeout.")
            id = self.acquire()
            if id is not None:
                return id
            logger.info(f"Retry acquire lock of {self.name}")
            time.sleep(0.1)

    @abstractmethod
    def acquire(self) -> Optional[str]:
        pass
    
    @abstractmethod
    def release(self) -> bool:
        pass
    
CreateLockFactory = Callable[[Options], DistributedLock]