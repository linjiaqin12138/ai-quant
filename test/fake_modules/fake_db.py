from sqlalchemy import create_engine
from lib.adapter.database.sqlalchemy import metadata_obj
from lib.adapter.database.kv_store import KeyValueStore
from lib.adapter.database.news_cache import HotNewsCache
from lib.adapter.database.session import SqlAlchemySession

engine = create_engine("sqlite+pysqlite:///:memory:", echo=False)
metadata_obj.create_all(engine)

fake_session = SqlAlchemySession(engine)
test_kv_store = KeyValueStore(fake_session)
test_hot_new_cache = HotNewsCache(fake_session)