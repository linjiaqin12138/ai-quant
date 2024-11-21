from datetime import datetime
from typing import List

from curl_cffi import requests as curl_requests
import curl_cffi

from ...config import API_MAX_RETRY_TIMES, get_http_proxy
from ...utils.retry import with_retry
from ...model.news import NewsInfo
from ...utils.time import days_ago, dt_to_ts, to_utc_isoformat, ts_to_dt, utc_isoformat_to_dt
from ...utils.string import url_encode

def get_news_of_cointime(start: datetime = days_ago(1), end: datetime = datetime.now()) -> List[NewsInfo]:
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
    last_timestamp = to_utc_isoformat(end)

    @with_retry((curl_cffi.requests.exceptions.Timeout, curl_cffi.requests.exceptions.ConnectionError), API_MAX_RETRY_TIMES)
    def retryable_part():
        """
        可重试的API请求部分。
        
        Returns:
            dict: API响应的数据部分。
        
        Raises:
            requests.exceptions.RequestException: 如果请求失败。
        """
        # curl 'https://cn.cointime.ai/api/column-items/more?column_id=111&datetime=2024-10-14T08%3A11%3A09.663Z&take=20&order=desc' \
        #     -H 'accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7' \
        #     -H 'accept-language: zh,zh-CN;q=0.9,en-US;q=0.8,en;q=0.7' \
        #     -H 'cache-control: max-age=0' \
        #     -H 'cookie: COINTIME-WEBSITE-XSRF-TOKEN=eyJpdiI6IkJvV2lteTlkN0IrK1BtdmtPTHpLS0E9PSIsInZhbHVlIjoiQ1NKWXBDYkZJL0w1RERqQ3cvVEtjOXBuY3NpZkxQQzFsN1B5Y05UNnUvRUI1NkxnOW9FVnh0UWp0RC82bWNpTkhRb1lRbzFiRDRzKytsNUpjenF4U1FaUmg1Z0JWSTRPby9zZzNYOS9CdXM4S2hXeWh5dWZoSUtiSmNmUGxCS1giLCJtYWMiOiI5OGU4ZGVjYzU2YTc2ZDM4OTQ4OGE1NTU5YWNiMjZkM2E5M2RkN2YyNTFkNzA3NzNiODJjZjUwYzE1OGIxNGNlIiwidGFnIjoiIn0%3D; cointime_website_session=eyJpdiI6IlA5Y2dEbEZOMjl1WlIzTW5oc1VDUEE9PSIsInZhbHVlIjoiNnlFR3hWV01RUmRuUTJOdzVGOGZLVFAreG5BQzNTNlhONDNNT2F0U0hJUXg5cnZRWHR2L1ZZVXh6aC9lcjdxbjh4elpkMmVjNDdtbFdVZUxLN0QyVUViL0t5VnlKVXlYUE5TTDMrZndnKy9mNlU4NWlaVEpiVUlkdERMUXpqUEgiLCJtYWMiOiJjNzBmM2FiODA3MjQ2ZjNhNWE5MTU4MDRkYjM5ZGU3Y2MxZWFjNzFiM2Y4MWVmYmQ2NjE2NGFkNzAzYmE4NTYyIiwidGFnIjoiIn0%3D' \
        #     -H 'priority: u=0, i' \
        #     -H 'sec-ch-ua: "Microsoft Edge";v="129", "Not=A?Brand";v="8", "Chromium";v="129"' \
        #     -H 'sec-ch-ua-mobile: ?0' \
        #     -H 'sec-ch-ua-platform: "Windows"' \
        #     -H 'sec-fetch-dest: document' \
        #     -H 'sec-fetch-mode: navigate' \
        #     -H 'sec-fetch-site: none' \
        #     -H 'sec-fetch-user: ?1' \
        #     -H 'upgrade-insecure-requests: 1' \
        #     -H 'user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0'
        
        

        url = f"https://cn.cointime.ai/api/column-items/more?column_id=111&datetime={url_encode(last_timestamp)}&take=20&order=desc"
        headers = { 
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0'
        }
        res = curl_requests.get(url, headers=headers, proxies={ 'http': get_http_proxy(), 'https': get_http_proxy() })
        res.raise_for_status()
        rsp_body = res.json()
        assert rsp_body["code"] == 0, str(rsp_body)
        return rsp_body["data"]
    
    while True:
        news = retryable_part()
        # print(len(news))
        # map_by(news, lambda x: print(x['publishedAt'], ts_to_dt(dt_to_ts(utc_isoformat_to_dt(x["publishedAt"]))).strftime("%Y-%m-%dT%H:%M:%S.%f")))
        if not news:
            break

        for n in news:
            news_timestamp = utc_isoformat_to_dt(n["publishedAt"])
            # 如果新闻早于指定时间则停止获取，转化为时间戳比较来避免时区问题（输入的start没时区但是news_timestamp有而且是utc)
            if dt_to_ts(news_timestamp) < dt_to_ts(start):
                return sorted(result, key=lambda x: x.timestamp)

            result.append(NewsInfo(
                news_id=n['itemId'],
                title=n['title'],
                description=n['description'],
                timestamp=ts_to_dt(dt_to_ts(news_timestamp)), # 变成本地时区的时间
                url=f"https://cn.cointime.ai{n['uri']}",
                platform="cointime",
                reason=None,
                mood=None
            ))

        # 更新时间戳以获取下一页的新闻
        last_timestamp = news[-1]["publishedAt"]

    #return sorted(result, key=lambda x: x.timestamp)