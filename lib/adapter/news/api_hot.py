import json
from typing import Any, Callable, Dict, List, Literal
from datetime import datetime

import requests

from ...logger import logger
from ...config import API_MAX_RETRY_TIMES
from ...model.news import NewsInfo
from ...utils.decorators import with_retry
from ...utils.time import ts_to_dt
from ...utils.list import map_by
from ...utils.string import hash_str

HotNewsPlatform = Literal[
    "baidu",
    "36kr",
    "qq-news",
    "sina-news",
    "sina",
    "zhihu",
    "huxiu",
    "netease-news",
    "toutiao",
]
RspMapper = Callable[[Any], NewsInfo]
ALL_HOT_NEWS_PLATFORMS: List[HotNewsPlatform] = [
    "baidu",
    "36kr",
    "qq-news",
    "sina-news",
    "sina",
    "zhihu",
    "huxiu",
    "netease-news",
    "toutiao",
]
API_ENDPOINT = "https://api-hot.imsyy.top/"


# 异常类定义
class GetHotFailedError(Exception):
    pass


# 辅助函数
def endpoint_of(platform: str) -> str:
    return f"{API_ENDPOINT}{platform}"


# 映射函数
def default_mapper(original_data: dict) -> NewsInfo:
    logger.debug(
        f"News in raw: {json.dumps(original_data, ensure_ascii=False, indent=2)}"
    )
    timestamp = (
        datetime.now()
        if original_data.get("timestamp") is None
        else ts_to_dt(original_data.get("timestamp"))
    )
    news_id = str(original_data.get("id", ""))
    return NewsInfo(
        news_id=news_id,
        title=original_data.get("title"),
        description=original_data.get("desc"),
        timestamp=timestamp,
        url=original_data.get("url"),
        platform=original_data.get("platform"),
    )


def toutiao_mapper(original_data: dict) -> NewsInfo:
    original_data["timestamp"] = None
    return default_mapper(original_data)


def qq_news_mapper(original_data: dict) -> NewsInfo:
    if (
        isinstance(original_data.get("timestamp"), int)
        and original_data.get("timestamp") < 0
    ):
        original_data["timestamp"] = None
    return default_mapper(original_data)


def baidu_mapper(original_data: dict) -> NewsInfo:
    original_data["id"] = hash_str(original_data["title"])[:32]
    return default_mapper(original_data)


SPECIAL_RESPONSE_MAPPER: Dict[HotNewsPlatform, RspMapper] = {
    "baidu": baidu_mapper,
    "toutiao": toutiao_mapper,
    "qq-news": qq_news_mapper,
}


@with_retry((GetHotFailedError,), API_MAX_RETRY_TIMES)
def get_hot_news_of_platform(platform: HotNewsPlatform) -> List[NewsInfo]:
    if platform not in ALL_HOT_NEWS_PLATFORMS:
        logger.error(f"{platform} is not supported")
        return []

    logger.info(f"Getting trend of platform {platform}")

    @with_retry(
        (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.ProxyError,
        ),
        API_MAX_RETRY_TIMES,
    )
    def retryable_part():
        return requests.get(endpoint_of(platform))

    res = retryable_part()
    if not (res.status_code == 200 and res.json()["code"] == 200):
        raise GetHotFailedError(
            f"Failed to get hot news from {platform}, statusCode {res.status_code}, body: {res.content}"
        )

    rsp_body = res.json()
    for news in rsp_body["data"]:
        news["platform"] = platform

    mapper = SPECIAL_RESPONSE_MAPPER.get(platform, default_mapper)
    return map_by(rsp_body["data"], mapper)
