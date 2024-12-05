from lib.adapter.database.kv_store import KeyValueStore
from lib.adapter.database.session import SqlAlchemySession
from lib.adapter.database.session import default_engine
from fake_modules.fake_db import get_fake_session, fake_kv_store_auto_commit
from concurrent.futures import ThreadPoolExecutor, as_completed

def test_set_and_get_string():
    with get_fake_session() as fake_session:
        kv_store = KeyValueStore(fake_session)
        kv_store.set('value_string_test', 'value')
        assert kv_store.get('value_string_test') == 'value'
        fake_session.commit()

def test_setnx():
    key = 'concurrent_key'
    successful_threads = []

    def try_setnx(thread_id):
        with get_fake_session() as fake_session:
            kv_store = KeyValueStore(fake_session)
            result = kv_store.setnx(key, f'val_{thread_id}')
            if result:
                successful_threads.append(thread_id)
                fake_session.commit()
            return result

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(try_setnx, i) for i in range(10)]
        
        # 等待所有线程完成
        for future in as_completed(futures):
            future.result()

        # 验证只有一个线程成功
        assert len(successful_threads) == 1, f"Expected 1 successful thread, got {len(successful_threads)}"
        print(f"Thread {successful_threads[0]} successfully set the key")