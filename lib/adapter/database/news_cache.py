from datetime import datetime
from typing import Any, List, Optional, Union

from sqlalchemy import select, insert, delete

from lib.model import NewsInfo
from lib.utils.time import dt_to_ts, ts_to_dt
from lib.utils.list import map_by
from .session import SessionAbstract
from .sqlalchemy import hot_news_cache

class HotNewsCache:
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
    
    def delete_news_by_time_range(self, platform: str, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> int:
        conditions = [hot_news_cache.c.platform == platform]
        
        if start_time is not None:
            conditions.append(hot_news_cache.c.timestamp >= dt_to_ts(start_time))
        
        if end_time is not None:
            conditions.append(hot_news_cache.c.timestamp < dt_to_ts(end_time))
        
        compiled = delete(hot_news_cache).where(*conditions).compile()
        return self.session.execute(compiled.string, compiled.params).row_count

    def get_news_by_time_range(self, platform: str, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> List[NewsInfo]:
        conditions = [hot_news_cache.c.platform == platform]
        
        if start_time is not None:
            conditions.append(hot_news_cache.c.timestamp >= dt_to_ts(start_time))
        
        if end_time is not None:
            conditions.append(hot_news_cache.c.timestamp < dt_to_ts(end_time))

        compiled = select(hot_news_cache).where(*conditions).order_by(hot_news_cache.c.timestamp.asc()).compile()
        res = self.session.execute(compiled.string, compiled.params)
        return map_by(res.rows, self._rows_to_news_info)
    
__all__ = [
    'HotNewsCache'
]