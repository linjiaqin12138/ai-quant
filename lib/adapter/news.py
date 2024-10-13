import abc
import json
from typing import List, Callable, Any, Literal, Dict, Optional
from datetime import datetime, timezone
import requests

from ..model import NewsInfo
from ..config import API_MAX_RETRY_TIMES, get_http_proxy
from ..logger import logger
from ..utils.time import get_utc_now_isoformat, hours_ago, ts_to_dt, utc_isoformat_to_dt
from ..utils.retry import with_retry
from ..utils.string import hash, url_encode

# 常量和类型定义
HotNewsPlatform = Literal["baidu", "36kr", "qq-news", "sina-news", "sina", "zhihu", "huxiu", "netease-news", "toutiao"]
LatestNewsPlatform = Literal["cointime"]
RspMapper = Callable[[Any], NewsInfo]
ALL_SUPPORTED_PLATFORMS: List[HotNewsPlatform | LatestNewsPlatform] = ["cointime", "baidu", "36kr", "qq-news", "sina-news", "sina", "zhihu", "huxiu", "netease-news", "toutiao", "cointime"]
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
def default_mapper(original_data: dict) -> NewsInfo:
    logger.debug(f"News in raw: {json.dumps(original_data, ensure_ascii=False, indent=2)}")
    timestamp = datetime.now() if original_data.get("timestamp") is None else ts_to_dt(original_data.get("timestamp"))
    news_id = str(original_data.get("id", ""))
    return NewsInfo(
        news_id=news_id,
        title=original_data.get("title"),
        description=original_data.get("desc"),
        timestamp=timestamp,
        url=original_data.get("url"),
        platform=original_data.get("platform"),
        reason=None,
        mood=None
    )

def toutiao_mapper(original_data: dict) -> NewsInfo:
    original_data["timestamp"] = None
    return default_mapper(original_data)

def qq_news_mapper(original_data: dict) -> NewsInfo:
    if isinstance(original_data.get("timestamp"), int) and original_data.get("timestamp") < 0:
        original_data["timestamp"] = None
    return default_mapper(original_data)

def baidu_mapper(original_data: dict) -> NewsInfo:
    original_data["id"] = hash(original_data["title"])[:32]
    return default_mapper(original_data)

SPECIAL_RESPONSE_MAPPER: Dict[HotNewsPlatform, RspMapper] = {
    "baidu": baidu_mapper,
    "toutiao": toutiao_mapper,
    'qq-news': qq_news_mapper
}

def get_news_of_cointime(after: Optional[datetime] = None) -> List[NewsInfo]:
    """
    获取Cointime平台的新闻。

    Args:
        after (datetime, optional): 如果提供，只返回该时间之后的新闻。默认为None。

    Returns:
        List[HotNewsInfo]: 包含HotNewsInfo对象的列表，每个对象代表一条新闻。

    Description:
        此函数从Cointime API获取新闻，并将其转换为HotNewsInfo对象。
        它使用分页机制来获取所有可用的新闻，直到没有更多新闻或达到指定的时间限制。
    """
    result = []
    now = get_utc_now_isoformat()
    last_timestamp = now

    while True:
        @with_retry((requests.exceptions.RequestException), API_MAX_RETRY_TIMES)
        def retryable_part():
            """
            可重试的API请求部分。
            
            Returns:
                dict: API响应的数据部分。
            
            Raises:
                requests.exceptions.RequestException: 如果请求失败。
            """
            url = f"https://cn.cointime.ai/api/column-items/more?column_id=111&datetime={url_encode(last_timestamp)}&take=20&order=desc"
            res = requests.get(url, proxies={ 'all': get_http_proxy() })
            res.raise_for_status()
            rsp_body = res.json()
            assert rsp_body["code"] == 0
            return rsp_body["data"]

        news = retryable_part()
        
        if not news:
            break

        for n in news:
            news_timestamp = utc_isoformat_to_dt(n["publishedAt"])
            # 如果新闻早于指定时间或不是今天的新闻，则停止获取
            if after:
                if news_timestamp < after:
                    return result
            else:
                if news_timestamp < hours_ago(hours=24, zone=timezone.utc):
                    return result

            result.append(NewsInfo(
                news_id=n['itemId'],
                title=n['title'],
                description=n['description'],
                timestamp=news_timestamp,
                url=n['uri'],
                platform="cointime",
                reason=None,
                mood=None
            ))

        # 更新时间戳以获取下一页的新闻
        last_timestamp = news[-1]["publishedAt"]

    return result

# 主要函数
@retry_decorator
def get_trend_of_cn_platform(platform: HotNewsPlatform) -> List[NewsInfo]:
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
class NewsAbstract(abc.ABC):
    @abc.abstractmethod
    def get_latest_news_of_platform(self, platform: LatestNewsPlatform, after: datetime = None) -> List[NewsInfo]:
        pass

    @abc.abstractmethod
    def get_hot_news_of_platform(self, platform: HotNewsPlatform) -> List[NewsInfo]:
        pass

    @abc.abstractmethod
    def get_news_from_platforms(self, platforms: List[HotNewsPlatform]) -> Dict[HotNewsPlatform, List[NewsInfo]]:
        pass

# 具体实现类
class NewsAdapter(NewsAbstract):

    def get_latest_news_of_platform(self, platform: LatestNewsPlatform, after: datetime = None) -> List[NewsInfo]:
        if platform == 'cointime':
            return get_news_of_cointime(after)
        # Should not go here
        return []
    def get_hot_news_of_platform(self, platform: HotNewsPlatform) -> List[NewsInfo]:
        return get_trend_of_cn_platform(platform)
    
    def get_news_from_platforms(self, platforms: List[HotNewsPlatform] = ALL_SUPPORTED_PLATFORMS) -> Dict[HotNewsPlatform, List[NewsInfo]]:
        return {platform: self.get_hot_news_of_platform(platform) for platform in platforms}

news = NewsAdapter()

__all__ = [
    'news',
    'NewsAbstract',
    'HotNewsPlatform',
    'LatestNewsPlatform',
    'ALL_SUPPORTED_PLATFORMS'
]