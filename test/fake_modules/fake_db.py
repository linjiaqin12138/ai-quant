import os
import tempfile
from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, Engine
from sqlalchemy.pool import StaticPool
from lib.adapter.database.sqlalchemy import metadata_obj
from lib.adapter.database.kv_store import KeyValueStore, KeyValueStoreAbstract, Value
from lib.adapter.database.news_cache import HotNewsCache, HotNewsCacheAbstract
from lib.adapter.database.session import SqlAlchemySession
from lib.model.news import NewsInfo
from lib.logger import logger
from lib.utils.string import random_id

db_str = f"sqlite:///{os.path.join(tempfile.gettempdir(), random_id() + '.sqlite')}"
logger.info(f"Sqlite for test: {db_str}")

def new_engine() -> Engine:
    return create_engine(
        db_str,
        echo=False, 
        connect_args={
            'check_same_thread': False
        },
        poolclass=StaticPool
    )
metadata_obj.create_all(new_engine())

def get_fake_session() -> SqlAlchemySession:
    return SqlAlchemySession(new_engine())

class FakeKvStore(KeyValueStoreAbstract):
    session = get_fake_session()
    kv_store = KeyValueStore(session)
    def set(self, key: str, val: Value):
        with self.session:
            self.kv_store.set(key, val)
            self.session.commit()

    def setnx(self, key: str, val: Value) -> bool:
        with self.session:
            res = self.kv_store.setnx(key, val)
            self.session.commit()
            return res
    
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
    
    def delete_news_by_time_range(self, platform: str, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> int:
       with self.session:
            res = self.delete_news_by_time_range(platform, start_time, end_time)
            self.session.commit()
            return res

    def get_news_by_time_range(self, platform: str, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> list[NewsInfo]:
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