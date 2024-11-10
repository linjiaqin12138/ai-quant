from lib.adapter.news import LatestNewsPlatform, NewsAbstract
from typing import List, Dict, Literal
from datetime import datetime

from lib.model import NewsInfo

class FakeNews(NewsAbstract):
    def __init__(self):
        self.news_map: Dict[LatestNewsPlatform, List[NewsInfo]] = {}

    def set_news(self, platform: LatestNewsPlatform, news: List[NewsInfo]):
        """设置指定平台的新闻列表"""
        self.news_map[platform] = news

    def get_latest_news_of_platform(self, platform: Literal['cointime'], after: datetime = None) -> List[NewsInfo]:
        """获取指定平台的新闻"""
        if platform not in self.news_map:
            return []
        
        news_list = self.news_map[platform]
        if after:
            return [news for news in news_list if news.published_at > after]
        return news_list

    def get_hot_news_of_platform(self, platform: LatestNewsPlatform) -> List[NewsInfo]:
        """获取指定平台的热门新闻"""
        if platform not in self.news_map:
            return []
        return self.news_map[platform]
    
    def get_news_from_platforms(self, platforms: List[LatestNewsPlatform]) -> Dict[LatestNewsPlatform, List[NewsInfo]]:
        """获取多个平台的新闻"""
        return {
            platform: self.news_map.get(platform, [])
            for platform in platforms
        }

fakenews = FakeNews()