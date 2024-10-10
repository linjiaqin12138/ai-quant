from typing import Union, TypedDict
import abc

from sqlalchemy import select, insert
from ...model import HotNewsInfo
from ...utils.time import dt_to_ts, ts_to_dt
from .session import SqlAlchemySession
from .sqlalchemy import hot_news_cache

class HotNewsCacheAbstract(abc.ABC):
    @abc.abstractmethod
    def add(self, news: HotNewsInfo):
        raise NotImplementedError
    @abc.abstractmethod
    def setnx(self, news: HotNewsInfo) -> int:
        raise NotImplementedError
    @abc.abstractmethod
    def get(self, id: str) -> Union[HotNewsInfo, None]:
        raise NotImplementedError

class HotNewsCache(HotNewsCacheAbstract):
    def __init__(self, session: SqlAlchemySession):
        self.session = session

    def add(self, news: HotNewsInfo):
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

    def get(self, id: str) -> Union[HotNewsInfo, None]:
        compiled = select(hot_news_cache).where(hot_news_cache.c.news_id == id).compile()
        res = self.session.execute(compiled.string, compiled.params)
        if len(res.rows) > 0:
            return HotNewsInfo(
                news_id=res.rows[0].news_id,
                description=res.rows[0].description,
                title=res.rows[0].title,
                platform=res.rows[0].platform,
                url=res.rows[0].url,
                timestamp=ts_to_dt(res.rows[0].timestamp),
                reason=res.rows[0].reason,
                mood=res.rows[0].mood
            )
        return None
    
    def setnx(self, news: HotNewsInfo) -> int:
        if self.get(news.news_id) is not None:
            return 0
        self.add(news)
        return 1