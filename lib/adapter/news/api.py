import abc
from datetime import datetime
from typing import List, Literal

from ...model.news import NewsInfo
from .cointime import get_news_of_cointime
from .caixin import get_latest_news_of_caixin
from .jin10 import get_news_of_jin10
from .api_hot import HotNewsPlatform, get_hot_news_of_platform, ALL_HOT_NEWS_PLATFORMS


class NewsFetcherApi(abc.ABC):
    # @abc.abstractmethod
    # def get_news_of_symbol_from(self, symbol: str, platform: str, start: datetime, end: datetime) -> List[NewsInfo]:
    #     """获取指定时间开始关于某个个股/加密货币的新闻信息

    #     Args:
    #         platform (str): 新闻平台名称
    #         symbol (str): 股票代码/加密货币名称
    #         start (datetime): 开始时间

    #     Returns:
    #         List[NewsInfo]: 新闻信息列表，按照对应平台新闻发布时间戳从小到大进行排序

    #     Raises:
    #         可能的异常说明（如有）
    #     """

    @abc.abstractmethod
    def get_news_from(self, platform: str, start: datetime) -> List[NewsInfo]:
        """获取指定时间开始到现在的新闻

        Args:
            platform (str): 新闻平台名称
            start (datetime): 开始时间

        Returns:
            List[NewsInfo]: 新闻信息列表，按照对应平台新闻发布时间戳从小到大进行排序

        Raises:
            可能的异常说明（如有）
        """
        pass

    @abc.abstractmethod
    def get_news_during(
        self, platform: str, start: datetime, end: datetime
    ) -> List[NewsInfo]:
        """获取指定时间范围内的新闻信息

        Args:
            platform (str): 新闻平台名称
            start (datetime): 开始时间
            end (datetime): 结束时间

        Returns:
            List[NewsInfo]: 新闻信息列表，按照对应平台新闻发布时间戳从小到大进行排序

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
    def get_news_from(
        self, platform: Literal["caixin", "cointime", "jin10"], start: datetime
    ) -> List[NewsInfo]:
        if platform == "caixin":
            return get_latest_news_of_caixin(start)
        elif platform == "jin10":
            return get_news_of_jin10(start, datetime.now())
        else:
            return get_news_of_cointime(start, datetime.now())

    def get_news_during(
        self,
        platform: Literal["cointime", "jin10"],
        start: datetime,
        end: datetime = datetime.now(),
    ) -> List[NewsInfo]:
        if platform == "jin10":
            return get_news_of_jin10(start, end)
        return get_news_of_cointime(start, end)

    def get_current_hot_news(self, platform: HotNewsPlatform) -> List[NewsInfo]:
        assert platform in ALL_HOT_NEWS_PLATFORMS
        return get_hot_news_of_platform(platform)
