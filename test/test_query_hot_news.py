from datetime import datetime
from lib.adapter.hot_news import hot_news, ALL_SUPPORTED_PLATFORMS

def test_query_trend():
    for platform in ALL_SUPPORTED_PLATFORMS:
        res = hot_news.get_hot_news_of_platform(platform)
        assert len(res) > 0
        sample = res[0]
        assert isinstance(sample.news_id, str)
        assert sample.description is None or isinstance(sample.description, str)
        assert isinstance(sample.timestamp, datetime)
        assert isinstance(sample.title, str)
        assert isinstance(sample.url, str)
        assert isinstance(sample.platform, str)
