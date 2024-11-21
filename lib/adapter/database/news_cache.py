from datetime import datetime
from typing import Any, List, Union
import abc

from sqlalchemy import select, insert

from ...model import NewsInfo
from ...utils.time import dt_to_ts, ts_to_dt
from ...utils.list import map_by
from .session import SessionAbstract
from .sqlalchemy import hot_news_cache

class HotNewsCacheAbstract(abc.ABC):
    @abc.abstractmethod
    def add(self, news: NewsInfo):
        raise NotImplementedError
    @abc.abstractmethod
    def setnx(self, news: NewsInfo) -> int:
        raise NotImplementedError
    @abc.abstractmethod
    def get_news_by_id(self, id: str) -> Union[NewsInfo, None]:
        raise NotImplementedError
    @abc.abstractmethod
    def get_news_by_time_range(self, platform: str, start_time: datetime, end_time: datetime) -> list[NewsInfo]:
        """根据时间范围和平台获取新闻列表
        
        Args:
            start_time: 开始时间戳
            end_time: 结束时间戳
            platform: 平台名称
            
        Returns:
            按时间戳升序排序的新闻列表
        """
        raise NotImplementedError

class HotNewsCache(HotNewsCacheAbstract):
    def __init__(self, session: SessionAbstract):
        self.session = session

    def _rows_to_news_info(self, row: Any) -> NewsInfo:
        return NewsInfo(
            news_id=row.news_id,
            description=row.description,
            title=row.title,
            platform=row.platform,
            url=row.url,
            timestamp=ts_to_dt(row.timestamp),
            reason=row.reason,
            mood=row.mood
        )

    def add(self, news: NewsInfo):
        compiled = insert(hot_news_cache).values(
            news_id = news.news_id,
            title = news.title,
            description = news.description,
            timestamp = dt_to_ts(news.timestamp),
            url = news.url,
            platform = news.platform,
            reason = news.reason,
            mood = news.mood
        ).compile()
        self.session.execute(compiled.string, compiled.params)

    def get_news_by_id(self, id: str) -> Union[NewsInfo, None]:
        compiled = select(hot_news_cache).where(hot_news_cache.c.news_id == id).compile()
        res = self.session.execute(compiled.string, compiled.params)
        return self._rows_to_news_info(res.rows[0]) if len(res.rows) > 0 else None
    
    def setnx(self, news: NewsInfo) -> int:
        if self.get_news_by_id(news.news_id) is not None:
            return 0
        self.add(news)
        return 1
    
    def get_news_by_time_range(self, platform: str, start_time: datetime, end_time: datetime) -> List[NewsInfo]:
        compiled = select(hot_news_cache).where(
            hot_news_cache.c.timestamp >= dt_to_ts(start_time),
            hot_news_cache.c.timestamp < dt_to_ts(end_time),
            hot_news_cache.c.platform == platform
        ).order_by(hot_news_cache.c.timestamp.asc()).compile()
        
        res = self.session.execute(compiled.string, compiled.params)
        return map_by(res.rows, self._rows_to_news_info)