from datetime import datetime
from typing import List

from curl_cffi import requests as curl_requests
import curl_cffi

from ...config import API_MAX_RETRY_TIMES
from ...logger import logger
from ...utils.list import filter_by, reverse
from ...utils.decorators import with_retry
from ...model.news import NewsInfo
from ...utils.time import days_ago, ts_to_dt
from ...utils.string import hash_str


def is_valid_news(news) -> bool:
    return isinstance(news, dict) and news.get("title") and news.get("time")


@with_retry(
    (
        curl_cffi.requests.exceptions.Timeout,
        curl_cffi.requests.exceptions.ConnectionError,
    ),
    API_MAX_RETRY_TIMES,
)
def query_latest_news_with_api(p_num: int, p_size: int):
    logger.debug(f"Query caixin news with page {p_num}, size {p_size}")
    response = curl_requests.get(
        f"https://cxdata.caixin.com/api/dataplus/sjtPc/news?pageNum={p_num}&pageSize={p_size}&showLabels=true"
    )
    rspBody = response.json()
    assert rspBody["success"]
    # 从大到小排序， 方便便利第一个刚好小于start的新闻
    return sorted(
        filter_by(rspBody["data"]["data"], is_valid_news),
        key=lambda x: x["time"],
        reverse=True,
    )


def get_latest_news_of_caixin(start: datetime = days_ago(1)) -> List[NewsInfo]:
    """
    获取财新数据平台的新闻。
    GET https://cxdata.caixin.com/api/dataplus/sjtPc/news?pageNum=1&pageSize=10&showLabels=true'
    response:
    {
        'success': True,
        'data': {
            'data': [
                {
                    'title': '快手绩后股价跳水 三季度业绩增速不及二季度',
                    'pic': 'https://img.caixin.com/2024-11-21/173215779712114_145_97.jpg',
                    'time': 1732157892,
                    'url': 'https://database.caixin.com/2024-11-21/102260061.html?cxapp_link=true',
                    'hasVideo': False,
                    'tag': '今日热点',
                    'tagColor': '#6B509B',
                    'labels': [],
                    'summary': '三季报显示，快手未能守住利润逐季度增长的势头',
                    'top': True
                }
                ...
            ]
        }
    }
    """
    page_num = 1
    page_size = 10
    max_page_size = 100
    news_list = []
    logger.info(f"Query caixin news starts from {start.isoformat()}")
    while True:
        news_data = query_latest_news_with_api(page_num, page_size)
        logger.debug(f"Query caixin news size: {len(news_data)}")
        if not news_data:
            logger.warning("No news found, returned")
            return reverse(news_list)

        for news in news_data:
            news_time_dt = ts_to_dt(news["time"] * 1000)
            logger.debug(
                f"{news_time_dt.isoformat()} {news['title']}, is in range: {news_time_dt >= start}, is top: {news.get('top')}"
            )
            # news_time = ts_to_dt(news['time'] * 1000)
            if news_time_dt < start and news["top"] != True:
                logger.debug(f"Reach the start point {start.isoformat()}, return")
                # 按接口要求从小到大排序
                return reverse(news_list)

            if news_time_dt >= start:
                # logger.debug(f"Add a new news {news['title']} {news_time_dt.isoformat()}")
                news_list.append(
                    NewsInfo(
                        news_id=hash_str(news["title"]),
                        title=news["title"],
                        timestamp=ts_to_dt(news["time"] * 1000),
                        url=news["url"],
                        description=news.get("summary"),
                        platform="caixin",
                    )
                )

        page_num += 1
        page_size = min(page_size * 2, max_page_size)

    # assert False, 'Should not go here'
