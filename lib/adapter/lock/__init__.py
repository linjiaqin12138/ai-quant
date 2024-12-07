from typing import TypeVar, Any
from ...logger import logger
from .api import *
from .database import DbBasedDistributedLock, create_lock as create_db_lock

G = TypeVar("G")
def with_lock(lock_factory: CreateLockFactory, name: str, max_concurrent_access: int, expiration_time: int, timeout: float):
    def decorator(function: G) -> G:
        def function_with_lock(*args, **kwargs) -> Any:
            options = {
                'name': name,
                'max_concurrent_access': max_concurrent_access,
                'expiration_time': expiration_time,
            }
            lock = lock_factory(options)

            lock_id = None
            try:
                lock_id = lock.wait(timeout)
                logger.info(f"Acquired lock id {lock_id}")
                return function(*args, **kwargs)
            finally:
                if lock_id is not None:
                    lock.release(lock_id)

        return function_with_lock
    return decorator