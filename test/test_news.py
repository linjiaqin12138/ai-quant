from datetime import datetime

import pytest

from lib.logger import logger
from lib.utils.time import hours_ago
from lib.adapter.news import news
from lib.utils.news import render_news_in_markdown_group_by_platform, render_news_in_markdown_group_by_time_for_each_platform

def test_news_adapter_get_news():
    start, end = hours_ago(2), hours_ago(1)
    news_in_range = news.get_news('cointime', start, end)
    logger.debug(news_in_range)
    assert len(news_in_range) > 1
    assert news_in_range[0].timestamp < news_in_range[1].timestamp
    assert news_in_range[0].timestamp >= start and news_in_range[-1].timestamp < end

def test_news_adapter_get_current_hot_news():
    for platform in ['baidu', 'toutiao', 'qq-news', 'sina']:
        hot_news = news.get_current_hot_news(platform)
        assert len(hot_news) > 0
        sample = hot_news[0]
        assert isinstance(sample.news_id, str)
        assert sample.description is None or isinstance(sample.description, str)
        assert isinstance(sample.timestamp, datetime)
        assert isinstance(sample.title, str)
        assert isinstance(sample.url, str)
        assert isinstance(sample.platform, str)


@pytest.mark.skip(reason="Temporarily disabled for devselopment")
def test_group_by_news_by_time():
    cointime_news = news.get_news('cointime', hours_ago(8), hours_ago(0))
    print(len(cointime_news), cointime_news[0].timestamp, cointime_news[-1].timestamp, cointime_news[-1].timestamp - cointime_news[0].timestamp)
    print(render_news_in_markdown_group_by_time_for_each_platform({
        'cointime': cointime_news
    }))

@pytest.mark.skip(reason="Temporarily disabled for devselopment")
def test_group_by_news_by_platform():
    sina_news = news.get_current_hot_news('sina')
    qq_news = news.get_current_hot_news('qq-news')
    
    print(render_news_in_markdown_group_by_platform({ 'sina': sina_news, 'qq-news': qq_news }))