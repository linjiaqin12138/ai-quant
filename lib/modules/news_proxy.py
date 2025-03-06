from datetime import datetime
from typing import Dict, List, Literal, Optional

from ..model import NewsInfo
from ..logger import logger
from ..utils.list import filter_by, map_by
from ..utils.time import dt_to_ts, ts_to_dt, minutes_ago
from ..adapter.news import news, NewsFetcherApi
from ..adapter.database.news_cache import HotNewsCache
from ..adapter.database.kv_store import KeyValueStore
from ..adapter.database.session import SessionAbstract ,SqlAlchemySession
from ..adapter.lock import CreateLockFactory, create_db_lock, with_lock

class NewsFetchProxy(NewsFetcherApi):

    def __init__(self, news_fetcher: NewsFetcherApi, session: SessionAbstract, api_lock_factory: CreateLockFactory = create_db_lock):
        self.raw_news_fetcher = news_fetcher
        self.session = session
        self.news_cache = HotNewsCache(session)
        self.kv_store = KeyValueStore(session)
        self.lock_factory = api_lock_factory

    def get_news_from(self, platform: Literal['cointime', 'caixin', 'jin10'], start: datetime) -> List[NewsInfo]:
        start_ts = dt_to_ts(start)
        logger.info("需要加锁更新本地新闻缓存")
        @with_lock(self.lock_factory, f'{platform}_query_lock', 1, 300, 300)
        def lock_part():
            with self.session:
                info_key = f'{platform}_news_cache_time_range'
                cache_time_range = self.kv_store.get(info_key)
                if cache_time_range is None or start_ts < cache_time_range['query_start']:
                    if cache_time_range is not None:
                        logger.warning('尽量不要发生这种查询, 将会重新刷新数据库')
                        self.news_cache.delete_news_by_time_range(platform)
                    else:
                        logger.info(f"初始化本地{platform}新闻缓存")

                    news_list = self.raw_news_fetcher.get_news_from(platform, start)
                    map_by(news_list, self.news_cache.add)
                    cache_time_range = {
                        'query_start': start_ts, 
                        'query_end': dt_to_ts(datetime.now()),
                        'start': start_ts, 
                        'end': start_ts
                    }
                    if len(news_list) > 0:
                        cache_time_range.update({
                            'start': dt_to_ts(news_list[0].timestamp), 
                            'end': dt_to_ts(news_list[-1].timestamp) + 1 
                        })
                    self.kv_store.set(info_key, cache_time_range) # [start, end)
                    self.session.commit()
                    return news_list
        
                if cache_time_range['query_start'] <= start_ts and start_ts < cache_time_range['query_end']:
                    logger.info(f"本地{platform}新闻缓存覆盖前一部分范围")
                    news_list = self.news_cache.get_news_by_time_range(platform, start)
                    news_list_by_remote = self.raw_news_fetcher.get_news_from(platform, ts_to_dt(cache_time_range['end']))
                    map_by(news_list_by_remote, self.news_cache.add)
                    news_list.extend(news_list_by_remote)
                    cache_time_range.update({ 'query_end': dt_to_ts(datetime.now()) })
                    if len(news_list_by_remote) > 0:
                        cache_time_range.update({ 'end': dt_to_ts(news_list_by_remote[-1].timestamp) + 1 })
                    self.kv_store.set(info_key, cache_time_range)
                    self.session.commit()
                    return news_list

                if cache_time_range['query_end'] <= start_ts:
                    logger.info(f"本地{platform}新闻缓存没覆盖，从缓存缺失的地方开始查")
                    news_list_by_remote = self.raw_news_fetcher.get_news_from(platform, ts_to_dt(cache_time_range['end']))
                    map_by(news_list_by_remote, lambda n: self.news_cache.add(n))
                    cache_time_range.update({ 'query_end': dt_to_ts(datetime.now()) })
                    if len(news_list_by_remote) > 0:
                        cache_time_range.update({ 'end': dt_to_ts(news_list_by_remote[-1].timestamp) + 1 })
                    self.kv_store.set(info_key, cache_time_range)
                    self.session.commit()
                    return filter_by(news_list_by_remote, lambda n: n.timestamp >= start)

                assert False, "Should not go here"
        return lock_part()

    def get_news_during(self, platform: Literal['cointime', 'caixin', 'jin10'], start: datetime, end: datetime) -> List[NewsInfo]:
        start_ts, end_ts = dt_to_ts(start), dt_to_ts(end)
        assert start_ts < end_ts, "起始时间必须小于结束时间"

        info_key = f'{platform}_news_cache_time_range'

        def is_cache_satisfy(cache_query_range_info: Optional[Dict[str, int]]):
            if cache_query_range_info and cache_query_range_info['query_start'] <= start_ts and end_ts <= cache_query_range_info['query_end']:
                logger.info(f"本地{platform}新闻缓存已覆盖查询范围:)")
                return True
            return False
        
        # 先不拿锁查缓存，缓存不满足要求再拿锁去查接口
        with self.session:
            if is_cache_satisfy(self.kv_store.get(info_key)):
                return self.news_cache.get_news_by_time_range(platform, start, end)

        if platform == 'caixin':
            return filter_by(self.get_news_from(platform, start), lambda n: n.timestamp < end)
        
        logger.info("需要加锁更新本地新闻缓存")
        @with_lock(self.lock_factory, f'{platform}_query_lock', 1, 300, 300)
        def lock_part():
            with self.session:
                # 我们假设数据库中平台新闻的最小时间戳和最大时间戳之间的新闻不存在缺漏
                cache_time_range = self.kv_store.get(info_key)
                # 等拿到锁之后，其它进程可能已经使得缓存满足要求了
                if is_cache_satisfy(cache_time_range):
                    return self.news_cache.get_news_by_time_range(platform, start, end)

                if cache_time_range is None:
                    logger.info(f"初始化本地{platform}新闻缓存")
                    news_list = self.raw_news_fetcher.get_news_during(platform, start, end)
                    map_by(news_list, self.news_cache.add)
                    
                    cache_time_range = {
                        'query_start': start_ts,
                        'query_end': end_ts,
                        'start': start_ts,
                        'end': start_ts + 1
                    }
                    if len(news_list) > 0:
                        cache_time_range.update({
                            'start': dt_to_ts(news_list[0].timestamp), 
                            'end': dt_to_ts(news_list[-1].timestamp) + 1 
                        })
                    self.kv_store.set(info_key, cache_time_range) # [start, end)
                    self.session.commit()
                    return news_list

                if cache_time_range['query_start'] <= start_ts and start_ts < cache_time_range['query_end'] and cache_time_range['query_end'] <= end_ts:
                    logger.info(f"本地{platform}新闻缓存覆盖前一部分范围")
                    news_result = self.news_cache.get_news_by_time_range(platform, start, end)
                    news_list_by_remote = self.raw_news_fetcher.get_news_during(platform, ts_to_dt(cache_time_range['end']), end)
                    map_by(news_list_by_remote, self.news_cache.add)
                    news_result.extend(news_list_by_remote)
                    
                    cache_time_range.update({ 'query_end': end_ts })
                    if len(news_list_by_remote) > 0:
                        cache_time_range.update({ 'end': dt_to_ts(news_list_by_remote[-1].timestamp) + 1 })

                    self.kv_store.set(info_key, cache_time_range) 
                    self.session.commit()
                    return news_result
                
                if start_ts < cache_time_range['query_start'] < end_ts and end_ts < cache_time_range['query_end']:
                    logger.info(f"本地{platform}新闻缓存覆盖后一部分范围")
                    news_result = self.raw_news_fetcher.get_news_during(platform, start, ts_to_dt(cache_time_range['start']))
                    news_list_by_local = self.news_cache.get_news_by_time_range(platform, start, end)
                    map_by(news_result, self.news_cache.add)
                    news_result.extend(news_list_by_local)
                    
                    cache_time_range.update({ 'query_start': start_ts })
                    if len(news_result) > 0:
                        cache_time_range.update({ 'start': dt_to_ts(news_result[0].timestamp) })
                    
                    self.kv_store.set(info_key, cache_time_range) 
                    self.session.commit()
                    return news_result
                
                if start_ts < cache_time_range['query_start'] and cache_time_range['query_end'] <= end_ts:
                    logger.info(f"本地{platform}新闻缓存覆盖中间一部分范围")
                    news_list_by_local = self.news_cache.get_news_by_time_range(platform, start, end)
                    news_result_previous = self.raw_news_fetcher.get_news_during(platform, start, ts_to_dt(cache_time_range['start']))
                    news_result_after = self.raw_news_fetcher.get_news_during(platform, ts_to_dt(cache_time_range['end'] + 1), end)
                    news_by_remote = news_result_previous + news_result_after
                    map_by(news_by_remote, self.news_cache.add)
                    news_result = news_result_previous + news_list_by_local + news_result_after

                    cache_time_range.update({ 'query_start': start_ts, 'query_end': end_ts })
                    if len(news_by_remote) > 0:
                        cache_time_range.update({ 'start': dt_to_ts(news_result[0].timestamp), 'end': dt_to_ts(news_result[-1].timestamp) + 1 })

                    self.kv_store.set(info_key, cache_time_range)
                    self.session.commit()
                    return news_result
                
                missed_start = ts_to_dt(min(cache_time_range['end'], start_ts))
                missed_end = ts_to_dt(max(cache_time_range['start'], end_ts))
                logger.info(f"本地{platform}新闻缓存没有覆盖，补充缺失的范围 {missed_start} - {missed_end}")
                news_result = self.raw_news_fetcher.get_news_during(platform, missed_start, missed_end)
                map_by(news_result, self.news_cache.add)

                cache_time_range.update({
                    'query_start': min(start_ts, cache_time_range['query_start']),
                    'query_end': max(end_ts, cache_time_range['query_end'])
                })
                if len(news_result) > 0:
                    cache_time_range.update({
                        'start': min(dt_to_ts(news_result[0].timestamp), cache_time_range['start']),
                        'end': max(dt_to_ts(news_result[-1].timestamp) + 1, cache_time_range['end'])
                    })
                self.kv_store.set(info_key, cache_time_range)
                self.session.commit()
                return filter_by(news_result, lambda x: x.timestamp < end and x.timestamp >= start)
            
        return lock_part()

    
    def get_current_hot_news(self, platform: str) -> List[NewsInfo]:
        with self.session:
            cache_key = f"{platform}_hot_news_5min"
            news_cache = self.kv_store.get(cache_key)
            
            def news_from_cache(news_obj: dict) -> NewsInfo:
                news_obj['timestamp'] = ts_to_dt(news_obj['timestamp'])
                return NewsInfo(**news_obj)

            def news_to_cache(news_obj: NewsInfo) -> dict:
                temp = news_obj.__dict__
                temp.update({ 'timestamp': dt_to_ts(news_obj.timestamp) })
                return temp

            if news_cache is not None and ts_to_dt(news_cache['timestamp']) > minutes_ago(5):
                logger.debug("Get platform news through local cache")
                return map_by(news_cache['news'], news_from_cache)
            
            news_by_remote = self.raw_news_fetcher.get_current_hot_news(platform)
            self.kv_store.set(cache_key, {
                'timestamp': dt_to_ts(datetime.now()),
                'news': map_by(news_by_remote, news_to_cache)
            })
            self.session.commit()
            return news_by_remote

news_proxy = NewsFetchProxy(news, SqlAlchemySession(), )
