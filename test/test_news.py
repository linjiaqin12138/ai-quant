from datetime import datetime

import pytest

from lib.logger import logger
from lib.utils.time import hours_ago
from lib.adapter.news import news
from lib.utils.news import render_news_in_markdown_group_by_platform, render_news_in_markdown_group_by_time_for_each_platform, render_news_list

def test_news_adapter_get_news_by_range():
    start, end = hours_ago(2), hours_ago(1)
    news_in_range = news.get_news_during('cointime', start, end)
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

def test_news_adapter_get_news_from_time():
    for case in [
        { 'platform': 'caixin', 'from_h': 48 }, 
        { 'platform': 'cointime', 'from_h': 8 }
        ]:
        start = hours_ago(case['from_h'])
        news_in_range = news.get_news_from(case['platform'], start)
        logger.debug('\n' + render_news_list(news_in_range))
        assert len(news_in_range) > 1
        assert news_in_range[0].timestamp < news_in_range[1].timestamp
        assert news_in_range[0].timestamp >= start

@pytest.mark.skip(reason="Temporarily disabled for devselopment")
def test_group_by_news_by_time():
    cases = {
        'jin10': {
            'from_h': 5,
            'to_h': 0
        },
        'cointime': {
            'from_h': 8,
            'to_h': 0
        }
    }
    for platform in cases:
        context = cases[platform]
        context['news_list'] = news.get_news_during(platform, hours_ago(context['from_h']),hours_ago(context['to_h']))
        print(len(context['news_list']), context['news_list'][0].timestamp, context['news_list'][-1].timestamp, context['news_list'][-1].timestamp - context['news_list'][0].timestamp)
    
    # jin10的文本当中有特殊字符，直接print看不到后面的东西，其实没问题
    print(render_news_in_markdown_group_by_time_for_each_platform({
        'jin10': cases['jin10']['news_list'],
        'cointime': cases['cointime']['news_list']
    }))

@pytest.mark.skip(reason="Temporarily disabled for devselopment")
def test_group_by_news_by_platform():
    sina_news = news.get_current_hot_news('sina')
    qq_news = news.get_current_hot_news('qq-news')
    
    print(render_news_in_markdown_group_by_platform({ 'sina': sina_news, 'qq-news': qq_news }))
