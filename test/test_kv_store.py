from fake_modules.fake_db import test_kv_store, fake_session

def test_set_and_get_string():
    with fake_session:
        test_kv_store.set('value_string_test', 'value')
        assert test_kv_store.get('value_string_test') == 'value'
        fake_session.commit()