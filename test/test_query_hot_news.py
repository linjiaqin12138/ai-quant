from datetime import datetime
from lib.adapter.hot_news import all_get_trends

def test_query_trend():
    for get_trend_function in all_get_trends:
        res = get_trend_function()
        assert len(res) > 0
        sample = res[0]
        assert isinstance(sample.news_id, str)
        assert sample.description is None or isinstance(sample.description, str)
        assert isinstance(sample.timestamp, datetime)
        assert isinstance(sample.title, str)
        assert isinstance(sample.url, str)
        assert isinstance(sample.platform, str)
