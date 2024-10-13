from datetime import datetime
from lib.adapter.database.news_cache import NewsInfo
from fake_modules.fake_db import test_hot_new_cache, fake_session

def test_hot_new_cache_ok():
    with fake_session:
        res = test_hot_new_cache.setnx(NewsInfo(
            news_id = "9f86d081884c7d659a2feaa0c55ad015",
            title = "This is a title",
            description = "This is a test description",
            timestamp=datetime.now(),
            url="https://www.baidu.com",
            platform="test",
            reason="",
            mood=0
        ))
        assert res == 1
        fake_session.commit()
    
    with fake_session:
        res = test_hot_new_cache.setnx(NewsInfo(
            news_id = "9f86d081884c7d659a2feaa0c55ad015",
            title = "This is a duplicate record title",
            description = "This is a duplicate record description",
            timestamp=datetime.now(),
            url="https://www.baidu.com",
            platform="test",
            reason="",
            mood=0
        ))
        assert res == 0
        res = test_hot_new_cache.get("9f86d081884c7d659a2feaa0c55ad015")
        assert res != None
        fake_session.execute("delete from hot_news_cache")
        fake_session.commit()