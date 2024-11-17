from sqlalchemy import create_engine
from lib.adapter.database.sqlalchemy import metadata_obj
from lib.adapter.database.kv_store import KeyValueStore, KeyValueStoreAbstract, Value
from lib.adapter.database.session import SqlAlchemySession

engine = create_engine("sqlite+pysqlite:///:memory:", echo=False)
metadata_obj.create_all(engine)

fake_session = SqlAlchemySession(engine)

test_kv_store = KeyValueStore(fake_session)

def get_fake_session() -> SqlAlchemySession:
    return SqlAlchemySession(engine)

class FakeKvStore(KeyValueStoreAbstract):
    session = get_fake_session()
    kv_store = KeyValueStore(session)
    def set(self, key: str, val: Value):
        with self.session:
            self.kv_store.set(key, val)
            self.session.commit()
    
    def get(self, key: str) -> Value | None:
        with self.session:
            return self.kv_store.get(key)
    
    def delete(self, key: str):
        with self.session:
            self.kv_store.delete(key)
            self.session.commit()

fake_kv_store_auto_commit = FakeKvStore()