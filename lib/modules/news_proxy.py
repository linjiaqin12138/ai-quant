from datetime import datetime
from typing import Callable, List

from ..model import NewsInfo
from ..logger import logger
from ..utils.list import map_by
from ..utils.time import dt_to_ts, ts_to_dt, minutes_ago
from ..adapter.news import news, NewsFetcherApi
from ..adapter.database.news_cache import HotNewsCache
from ..adapter.database.kv_store import KeyValueStore
from ..adapter.database.session import SessionAbstract ,SqlAlchemySession

class NewsFetchProxy(NewsFetcherApi):

    def __init__(self, news_fetcher: NewsFetcherApi, session: SessionAbstract):
        self.raw_news_fetcher = news_fetcher
        self.session = session
        self.news_cache = HotNewsCache(session)
        self.kv_store = KeyValueStore(session)

    def get_news(self, platform: str, start: datetime, end: datetime) -> List[NewsInfo]:
        with self.session:
            # 这样其实有Bug，cache查出来的可能是start - end中间某段时间的新闻，start - 第一个被cache的时间会miss掉后端查询
            # 暂时不会那样用，不管了
            news_result = self.news_cache.get_news_by_time_range(platform, start, end)
            start_time = news_result[-1].timestamp if len(news_result) > 0 else start
            fresh_news = self.raw_news_fetcher.get_news(platform, start_time, end)
            map_by(fresh_news, lambda news: self.news_cache.add(news))
            news_result.extend(fresh_news)
            if len(fresh_news) > 0:
                self.session.commit()
            return news_result
    
    def get_current_hot_news(self, platform: str) -> List[NewsInfo]:
        with self.session:
            cache_key = f"{platform}_hot_news_5min"
            news_cache = self.kv_store.get(cache_key)
            
            def news_from_cache(news_obj: dict) -> NewsInfo:
                news_obj['timestamp'] = ts_to_dt(news_obj['timestamp'])
                return NewsInfo(**news_obj)

            def news_to_cache(news_obj: NewsInfo) -> dict:
                temp = news_obj.__dict__
                temp.update({ 'timestamp': dt_to_ts(news_obj.timestamp) })
                return temp

            if news_cache is not None and ts_to_dt(news_cache['timestamp']) > minutes_ago(5):
                logger.debug("Get platform news through local cache")
                return map_by(news_cache['news'], news_from_cache)
            
            news_by_remote = self.raw_news_fetcher.get_current_hot_news(platform)
            self.kv_store.set(cache_key, {
                'timestamp': dt_to_ts(datetime.now()),
                'news': map_by(news_by_remote, news_to_cache)
            })
            self.session.commit()
            return news_by_remote

news_proxy = NewsFetchProxy(news, SqlAlchemySession())
