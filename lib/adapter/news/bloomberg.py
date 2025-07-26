from datetime import datetime
from typing import List
from curl_cffi import requests as curl_requests
import json
import curl_cffi

from json_repair import repair_json
from lib.config import API_MAX_RETRY_TIMES, get_http_proxy
from lib.logger import logger
from lib.utils.list import filter_by, map_by, reverse
from lib.utils.decorators import with_retry
from lib.model.news import NewsInfo
from lib.utils.time import days_ago, parse_datetime_string
from lib.utils.string import hash_str

class AreYouRobot(Exception):
    ... 

def is_valid_news(news) -> bool:
    is_valid = isinstance(news, dict) and \
        news.get("headline") and \
        news.get("publishedAt") and \
        news.get("url") and \
        news.get("type") == "article" and \
        news.get("id")
    if not is_valid:
        logger.warning(f"Invalid bloomberg news format: {news}")
    return is_valid

@with_retry(
    (
        curl_cffi.requests.exceptions.Timeout,
        curl_cffi.requests.exceptions.ConnectionError,
        AreYouRobot
    ),
    API_MAX_RETRY_TIMES,
)
def query_latest_news_with_api(page_number: int, limit: int):
    logger.debug(f"Query bloomberg news with page_number {page_number}, limit {limit}")
    url = f"https://www.bloomberg.com/lineup-next/api/stories?pageNumber={page_number}&limit={limit}"
    # proxies = None
    # proxy_url = get_http_proxy()
    # if proxy_url:
    #     proxies = {
    #         'http': proxy_url,
    #         'https': proxy_url,
    #     }
    #     logger.info(f"Using proxy for bloomberg: {proxy_url}")
    # headers = {
    #     'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    #     'Accept': 'application/json, text/plain, */*',
    #     'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    #     'Referer': 'https://www.bloomberg.com/',
    #     'Connection': 'keep-alive',
    # }
    # response = curl_requests.get(url)
    response = curl_requests.get("https://r.jina.ai/" + url) # 反爬奇技淫巧 :)
    # print("https://r.jina.ai/" + url)
    response.raise_for_status()  # 确保请求成功
    if 'Are you a robot?' in response.text:
        raise AreYouRobot("Bloomberg API returned 'Are you a robot?' message, likely due to anti-bot measures.")
    response_json = json.loads(repair_json(response.text))
    news_list = response_json
    if not news_list:
        logger.warning(f"No bloomberg news found in response, raw: {response.text[:200]}")
        return []
    return sorted(
        filter_by(news_list, is_valid_news),
        key=lambda x: x["publishedAt"],
        reverse=True,
    )

def get_latest_news_of_bloomberg(start: datetime = days_ago(1)) -> List[NewsInfo]:
    """
    获取bloomberg新闻。
    GET https://www.bloomberg.com/lineup-next/api/stories?types=ARTICLE%2CFEATURE%2CINTERACTIVE%2CLETTER%2CEXPLAINERS&pageNumber=1&limit=50
    """
    page_number = 1
    limit = 25
    news_list = []
    logger.info(f"Query bloomberg news starts from {start.isoformat()}")
    while True:
        news_data = query_latest_news_with_api(page_number, limit)
        logger.debug(f"Query bloomberg news size: {len(news_data)}")
        if not news_data:
            logger.warning("No bloomberg news found, returned")
            return reverse(news_list)
        for news in news_data:
            news_time_dt = parse_datetime_string(news["publishedAt"])
            logger.debug(f"{news_time_dt.isoformat()} {news.get('headline', '无标题')}, is in range: {news_time_dt >= start}")
            if news_time_dt < start:
                logger.debug(f"Reach the start point {start.isoformat()}, return")
                return reverse(news_list)
            description = news.get("summary", "")
            # if news.get("byline"):
            #     description += f" 作者：{news['byline']}"
            if news.get("brand"):
                description += f" [{news['brand']}]"
            if news.get("label"):
                description += f" [{news['label']}]"
            news_list.append(
                NewsInfo(
                    news_id=news["id"],
                    title=news.get("headline", "无标题"),
                    timestamp=news_time_dt,
                    url="https://www.bloomberg.com" + news.get("url", ""),
                    description=description,
                    platform="bloomberg",
                )
            )
        page_number += 1