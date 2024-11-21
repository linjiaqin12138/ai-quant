import abc
from datetime import datetime
from typing import List, Literal

from ...model.news import NewsInfo
from .cointime import get_news_of_cointime
from .api_hot import HotNewsPlatform, get_hot_news_of_platform, ALL_HOT_NEWS_PLATFORMS

class NewsFetcherApi(abc.ABC):
    @abc.abstractmethod
    def get_news(self, platform: str, start: datetime, end: datetime) -> List[NewsInfo]:
        """获取指定时间范围内的新闻信息

        Args:
            platform (str): 新闻平台名称
            start (datetime): 开始时间
            end (datetime): 结束时间
abc
        Returns:
            List[NewsInfo]: 新闻信息列表，按照新闻发布时间戳从小到大进行排序

        Raises:
            可能的异常说明（如有）
        """
        pass
    
    @abc.abstractmethod
    def get_current_hot_news(self, platform: str) -> List[NewsInfo]:
        """获取当前热门新闻

        Args:
            platform (str): 新闻平台名称

        Returns:
            List[NewsInfo]: 热门新闻信息列表, 按照平台的热度从高到低进行排序

        Raises:
            可能的异常说明（如有）
        """
        pass


# 具体实现类
class NewsFetcher(NewsFetcherApi):
    def get_news(self, platform: Literal['cointime'], start: datetime, end: datetime = datetime.now()) -> List[NewsInfo]:
        return get_news_of_cointime(start, end)

    def get_current_hot_news(self, platform: HotNewsPlatform) -> List[NewsInfo]:
        assert platform in ALL_HOT_NEWS_PLATFORMS
        return get_hot_news_of_platform(platform)