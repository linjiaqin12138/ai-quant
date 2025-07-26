from datetime import datetime
from typing import List
from curl_cffi import requests as curl_requests
import curl_cffi
from lib.config import API_MAX_RETRY_TIMES
from lib.logger import logger
from lib.utils.list import filter_by, map_by, reverse
from lib.utils.decorators import with_retry
from lib.model.news import NewsInfo
from lib.utils.time import days_ago, ts_to_dt
from lib.utils.string import hash_str

def is_valid_news(news) -> bool:
    is_valid = isinstance(news, dict) and \
        news.get("content") and \
        news.get("publish_time") and \
        news.get("third_url") # 可能没有title
    if not is_valid:
        logger.warning(f"Invalid news format: {news}")
    return is_valid

@with_retry(
    (
        curl_cffi.requests.exceptions.Timeout,
        curl_cffi.requests.exceptions.ConnectionError,
    ),
    API_MAX_RETRY_TIMES,
)
def query_latest_news_with_api(pn: int, rn: int):
    logger.debug(f"Query gushitong news with pn {pn}, rn {rn}")
    url = f"https://finance.pae.baidu.com/selfselect/expressnews?rn={rn}&pn={pn}&tag=&finClientType=pc"
    response = curl_requests.get(url)
    rspBody = response.json()
    # 百度接口返回格式：{{'Result': [news, ...]}}
    news_list = rspBody.get("Result", {}).get("content", {}).get("list", [])
    if not news_list:
        logger.warning("No news found in response")
        return []
    return sorted(
        filter_by(news_list, is_valid_news),
        key=lambda x: int(x["publish_time"]),
        reverse=True,
    )

def get_latest_news_of_gushitong(start: datetime = days_ago(1)) -> List[NewsInfo]:
    """
    获取百度股市通新闻。
    GET https://finance.pae.baidu.com/selfselect/expressnews?rn=50&pn=0&tag=&finClientType=pc
    """
    pn = 0
    rn = 50
    news_list = []
    logger.info(f"Query gushitong news starts from {start.isoformat()}")
    while True:
        news_data = query_latest_news_with_api(pn, rn)
        logger.debug(f"Query gushitong news size: {len(news_data)}")
        if not news_data:
            logger.warning("No news found, returned")
            return reverse(news_list)
        for news in news_data:
            news_time_dt = ts_to_dt(int(news["publish_time"]) * 1000)
            logger.debug(f"{news_time_dt.isoformat()} {news.get('title', '无标题')}, is in range: {news_time_dt >= start}")
            if news_time_dt < start:
                logger.debug(f"Reach the start point {start.isoformat()}, return")
                return reverse(news_list)
            content_list = news.get("content", {}).get("items", [])
            description = ""
            if news.get("important") == "1":
                description += "[重要] "
            for content in content_list:
                description += (content.get("data", "") if content.get("type") == "text" else "")
            if news.get("provider"):
                description += f" 来源：{news['provider']}"
            if news.get("entity"):
                for entity in news['entity']:
                    if entity.get('name') and entity.get('exchange') and entity.get('code') and entity.get('ratio'):
                        # 只添加有name, exchange, code和ratio的entity
                        description += f" [{entity.get('name', '')}({entity.get('exchange', '')}{entity.get('code', '')}): {entity.get('ratio', '')}]"
            if news.get("tag"):
                description += " "
                tags: List[str] = news['tag'].split("$")
                tags = map_by(news['tag'].split("$"), lambda tag: f'#{tag}')
                description += ' '.join(tags)
            

            news_list.append(
                NewsInfo(
                    news_id=hash_str(news.get("title", "") + news["publish_time"]),
                    title=news.get("title", "无标题"),
                    timestamp=news_time_dt,
                    url=news.get("third_url"),
                    description=description,
                    platform="gushitong",
                )
            )
        pn += rn
    # assert False, 'Should not go here'
