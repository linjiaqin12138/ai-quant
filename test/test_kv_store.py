import pytest
from lib.adapter.database import create_transaction
from concurrent.futures import ThreadPoolExecutor, as_completed

def test_set_and_get_string():
    with create_transaction() as db:
        db.kv_store.set('value_string_test', 'value')
        assert db.kv_store.get('value_string_test') == 'value'
        db.session.commit()

@pytest.mark.skip(reason="Sqlite模式下不支持并发测试")
def test_setnx():
    key = 'concurrent_key'
    successful_threads = []

    def try_setnx(thread_id):
        with create_transaction() as db:
            result = db.kv_store.setnx(key, f'val_{thread_id}')
            if result:
                successful_threads.append(thread_id)
                db.session.commit()
            return result

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(try_setnx, i) for i in range(10)]
        
        # 等待所有线程完成
        for future in as_completed(futures):
            future.result()

        # 验证只有一个线程成功
        assert len(successful_threads) == 1, f"Expected 1 successful thread, got {len(successful_threads)}"
        print(f"Thread {successful_threads[0]} successfully set the key")