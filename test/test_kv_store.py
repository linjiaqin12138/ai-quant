from lib.adapter.database.kv_store import KeyValueStore
from lib.adapter.database.session import SqlAlchemySession
from fake_modules.fake_db import engine


def test_set_and_get_string():
    with SqlAlchemySession(engine) as fake_session:
        kv_store = KeyValueStore(fake_session)
        kv_store.set('value_string_test', 'value')
        assert kv_store.get('value_string_test') == 'value'
        fake_session.commit()