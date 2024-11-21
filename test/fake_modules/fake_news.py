from lib.adapter.news import NewsFetcherApi
from typing import List, Dict, Literal
from datetime import datetime

from lib.model import NewsInfo
from lib.utils.list import filter_by

class FakeNews(NewsFetcherApi):
    def __init__(self):
        self.news_map: Dict[str, List[NewsInfo]] = {}

    def get_current_hot_news(self, platform: str) -> List[NewsInfo]:
        return sorted(self.news_map[platform], lambda n: n.timestamp)
    
    def get_news(self, platform: str, start: datetime, end: datetime) -> List[NewsInfo]:
        return filter_by(self.news_map[platform], lambda n: n.timestamp < end and n.timestamp >= start)
    
    def set_news(self, platform: str, news: List[NewsInfo]):
        """设置指定平台的新闻列表"""
        self.news_map[platform] = news

fakenews = FakeNews()