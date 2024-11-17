import pytest
from datetime import datetime
from lib.adapter.news import news, ALL_HOT_NEWS_PLATFORMS

@pytest.mark.skip(reason="Temporarily disabled for development")
def test_query_trend():
    for platform in ALL_HOT_NEWS_PLATFORMS:
        res = news.get_hot_news_of_platform(platform)
        assert len(res) > 0
        sample = res[0]
        assert isinstance(sample.news_id, str)
        assert sample.description is None or isinstance(sample.description, str)
        assert isinstance(sample.timestamp, datetime)
        assert isinstance(sample.title, str)
        assert isinstance(sample.url, str)
        assert isinstance(sample.platform, str)
