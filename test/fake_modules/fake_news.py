import threading
from typing import List, Dict
from datetime import datetime


from lib.model import NewsInfo
from lib.utils.list import filter_by
from lib.adapter.news import NewsFetcherApi

class FakeNews(NewsFetcherApi):
    def __init__(self):
        self.news_map: Dict[str, List[NewsInfo]] = {}
        self.func_call_time: Dict[str, int] = {}
        self._lock = threading.Lock()

    def get_call_times(self, func_name: str) -> int:
        return self.func_call_time.get(func_name, 0)
    
    def _increase_func_call_time(self, func_name: str):
        self._lock.acquire()
        if self.func_call_time.get(func_name):
            self.func_call_time[func_name] = self.func_call_time[func_name] + 1
        else:
            self.func_call_time[func_name] = 1
        self._lock.release()
    def get_news_from(self, platform: str, start: datetime) -> List[NewsInfo]:
        self._increase_func_call_time('get_news_from')
        return filter_by(self.news_map[platform], lambda n: n.timestamp >= start)

    def get_current_hot_news(self, platform: str) -> List[NewsInfo]:
        self._increase_func_call_time('get_current_hot_news')
        return self.news_map[platform]
    
    def get_news_during(self, platform: str, start: datetime, end: datetime) -> List[NewsInfo]:
        self._increase_func_call_time('get_news_during')
        return filter_by(self.news_map[platform], lambda n: n.timestamp < end and n.timestamp >= start)
    
    def set_news(self, platform: str, news: List[NewsInfo]):
        """设置指定平台的新闻列表"""
        for key in self.func_call_time.keys():
            self.func_call_time.update({ key: 0 })

        self.news_map[platform] = news

fakenews = FakeNews()