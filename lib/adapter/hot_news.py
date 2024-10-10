import abc
from typing import List, Callable, Any, Literal, Dict
from datetime import datetime
import requests

from ..model import HotNewsInfo
from ..config import API_MAX_RETRY_TIMES
from ..logger import logger
from ..utils.time import ts_to_dt
from ..utils.retry import with_retry
from ..utils.string import hash

# 常量和类型定义
NewsPlatform = Literal["baidu", "36kr", "qq-news", "sina-news", "sina", "zhihu", "huxiu", "netease-news", "toutiao"]
RspMapper = Callable[[Any], HotNewsInfo]
ALL_SUPPORTED_PLATFORMS: List[NewsPlatform] = ["baidu", "36kr", "qq-news", "sina-news", "sina", "zhihu", "huxiu", "netease-news", "toutiao"]
API_ENDPOINT = "https://api-hot.efefee.cn/"
# 异常类定义
class GetHotFailedError(Exception):
    pass

# 辅助函数
def endpoint_of(platform: str) -> str:
    return f"{API_ENDPOINT}{platform}"

# 装饰器
retry_decorator = with_retry((GetHotFailedError,), API_MAX_RETRY_TIMES)

# 映射函数
def default_mapper(original_data: dict) -> HotNewsInfo:
    timestamp = datetime.now() if original_data.get("timestamp") is None else ts_to_dt(original_data.get("timestamp"))
    news_id = str(original_data.get("id", ""))
    return HotNewsInfo(
        news_id=news_id,
        title=original_data.get("title"),
        description=original_data.get("desc"),
        timestamp=timestamp,
        url=original_data.get("url"),
        platform=original_data.get("platform"),
        reason=None,
        mood=None
    )

def toutiao_mapper(original_data: dict) -> HotNewsInfo:
    original_data["timestamp"] = None
    return default_mapper(original_data)

def baidu_mapper(original_data: dict) -> HotNewsInfo:
    original_data["id"] = hash(original_data["title"])[:32]
    return default_mapper(original_data)

SPECIAL_RESPONSE_MAPPER: Dict[NewsPlatform, RspMapper] = {
    "baidu": baidu_mapper,
    "toutiao": toutiao_mapper
}

# 主要函数
@retry_decorator
def get_trend_of(platform: NewsPlatform) -> List[HotNewsInfo]:
    if platform not in ALL_SUPPORTED_PLATFORMS:
        logger.error(f"{platform} is not supported")
        return []
    
    logger.info(f"Getting trend of platform {platform}")
    res = requests.get(endpoint_of(platform))
    
    if not (res.status_code == 200 and res.json()["code"] == 200):
        raise GetHotFailedError(f'Failed to get hot news from {platform}, statusCode {res.status_code}, body: {res.content}')
    
    rsp_body = res.json()
    for news in rsp_body["data"]:
        news["platform"] = platform
    
    mapper = SPECIAL_RESPONSE_MAPPER.get(platform, default_mapper)
    return list(map(mapper, rsp_body["data"]))

# 抽象基类
class HotNewsAbstract(abc.ABC):
    @abc.abstractmethod
    def get_hot_news_of_platform(self, platform: NewsPlatform) -> List[HotNewsInfo]:
        pass

    @abc.abstractmethod
    def get_news_from_platforms(self, platforms: List[NewsPlatform]) -> Dict[NewsPlatform, List[HotNewsInfo]]:
        pass

# 具体实现类
class HotNews(HotNewsAbstract):
    def get_hot_news_of_platform(self, platform: NewsPlatform) -> List[HotNewsInfo]:
        return get_trend_of(platform)
    
    def get_news_from_platforms(self, platforms: List[NewsPlatform] = ALL_SUPPORTED_PLATFORMS) -> Dict[NewsPlatform, List[HotNewsInfo]]:
        return {platform: self.get_hot_news_of_platform(platform) for platform in platforms}

hot_news = HotNews()

__all__ = [
    'hot_news',
    'HotNewsAbstract',
    'NewsPlatform',
    'ALL_SUPPORTED_PLATFORMS'
]