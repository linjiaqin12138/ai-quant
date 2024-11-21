from datetime import datetime
from sqlalchemy import create_engine
from lib.adapter.database.sqlalchemy import metadata_obj
from lib.adapter.database.kv_store import KeyValueStore, KeyValueStoreAbstract, Value
from lib.adapter.database.news_cache import HotNewsCache, HotNewsCacheAbstract
from lib.adapter.database.session import SqlAlchemySession
from lib.model import NewsInfo

engine = create_engine("sqlite+pysqlite:///:memory:", echo=False)
metadata_obj.create_all(engine)

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

class FakeNewsCache(HotNewsCacheAbstract):
    session = get_fake_session()
    news_cache = HotNewsCache(session)

    def get_news_by_id(self, id: str) -> NewsInfo | None:
        with self.session:
            return self.news_cache(id)
    
    def get_news_by_time_range(self, platform: str, start_time: datetime, end_time: datetime) -> list[NewsInfo]:
        with self.session:
            return self.get_news_by_time_range(platform, start_time, end_time)
        
    def add(self, news: NewsInfo):
        with self.session:
            self.add(news)
            self.session.commit()
    
    def setnx(self, news: NewsInfo) -> int:
        with self.session:
            self.setnx(news)
            self.session.commit()
    
    
fake_kv_store_auto_commit = FakeKvStore()
fake_news_cache_auto_commit = FakeNewsCache()