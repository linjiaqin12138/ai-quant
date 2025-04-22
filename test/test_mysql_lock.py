
import os
import tempfile
import threading
import time
import random
import pytest
from lib.adapter.lock.database import DbBasedDistributedLock
from lib.logger import logger

@pytest.fixture
def mysql_lock():
    return DbBasedDistributedLock(**{
        'name': 'test_lock',
        'max_concurrent_access': 2,
        'expiration_time': 300,
        'db_url':  f"sqlite:///{os.path.join(tempfile.gettempdir(), 'quant_test.sqlite')}"
    })

def test_acquire_lock_success_with_max_cocurrency(mysql_lock: DbBasedDistributedLock):
    def target(lock: DbBasedDistributedLock, results, index):
        lock_id = None
        try:
            lock_id = lock.acquire()
            if lock_id:
                results[index] = True
                logger.debug(f"acquire lock {lock_id}")
                time.sleep(random.uniform(1, 2))  # Hold the lock for a moment
            else:
                results[index] = False
                logger.debug('Acquire lock failed')
        except Exception as e:
            logger.error(str(e))
            results[index] = False
        finally:
            if lock_id:
                logger.debug(f"release lock {lock_id}")
                lock.release(lock_id)

    threads = []
    results = [None] * 4  # To store results from each thread
    for i in range(4):
        thread = threading.Thread(target=target, args=(mysql_lock, results, i))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

    assert sum(results) == 2

def test_wait_lock_success(mysql_lock: DbBasedDistributedLock):
    def target(lock: DbBasedDistributedLock, results, index):
        lock_id = None
        try:
            lock_id = lock.wait(100)
            results[index] = True
            logger.debug(f"acquire lock {lock_id}")
            
            time.sleep(random.uniform(1, 2))  # Hold the lock for a moment
        except Exception as e:
            logger.error(str(e))
            results[index] = False
        finally:
            if lock_id:
                print(f"release lock {lock_id}")
                lock.release(lock_id)

    threads = []
    results = [None] * 4  # To store results from each thread
    for i in range(4):
        thread = threading.Thread(target=target, args=(mysql_lock, results, i))
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

    assert sum(results) == 4