from typing import Dict, List
from datetime import datetime

from curl_cffi import requests as curl_requests
import curl_cffi

from ...logger import logger
from ...config import API_MAX_RETRY_TIMES
from ...utils.time import days_ago
from ...utils.list import filter_by, map_by
from ...utils.decorators import with_retry
from ...model.news import NewsInfo


def get_news_of_jin10(start: datetime = days_ago(1), end: datetime = datetime.now()) -> List[NewsInfo]:
    @with_retry((curl_cffi.requests.exceptions.Timeout, curl_cffi.requests.exceptions.ConnectionError), API_MAX_RETRY_TIMES)
    def retryable_part(max_time: datetime) -> List[Dict]:
        url = f'https://flash-api.jin10.com/get_flash_list?max_time={max_time.strftime("%Y-%m-%d+%H:%M:%S")}'
        headers = { 
            'x-app-id': 'bVBF4FyRTn5NJF5n',
            'x-version': '1.0.0'
        }
        res = curl_requests.get(url, headers=headers)
        res.raise_for_status()
        return res.json().get('data', [])

    def map_to_news_info(item: Dict) -> NewsInfo:
        item_data = item.get('data', {})
        if not item_data.get('title') and item_data.get('content', '').startswith('【'):
            item_data['title'] = item_data['content'].split('】')[0][1:]
            item_data['content'] = item_data['content'][len(item_data['title'])+2:]
        return NewsInfo(
            news_id=item.get('id'),
            title=item_data.get('title') or '',
            description=item_data.get('content') or '',
            url=item_data.get('source_link') or item_data.get('link') or item_data.get('pic') or '',
            timestamp=datetime.strptime(item.get('time'), '%Y-%m-%d %H:%M:%S'),
            platform='jin10',
        )
    result = []
    while True:
        logger.debug(f'Getting news from jin10 from {end}')
        rsp_data_list = retryable_part(end)
        news_info_list = map_by(rsp_data_list, map_to_news_info)
        news_info_list.sort(key=lambda x: x.timestamp)
        filtered_news_info_list = filter_by(news_info_list, lambda x: x.timestamp >= start and x.title or x.description)
        map_by(filtered_news_info_list, lambda x: logger.debug(f'{x.timestamp}: {x.title or x.description}'))
        result.extend(filtered_news_info_list)
        if news_info_list[0].timestamp < start:
            break
        end = news_info_list[0].timestamp
    result.sort(key=lambda x: x.timestamp)
    return result