from datetime import datetime, timedelta
from typing import Dict, List, Literal, Optional

from lib.model import NewsInfo
from lib.logger import logger
from lib.utils.list import filter_by, map_by
from lib.utils.time import dt_to_ts, ts_to_dt
from lib.adapter.news import news, NewsFetcherApi
from lib.adapter.database import create_transaction
from lib.adapter.lock import with_lock
from lib.tools.cache_decorator import use_cache


class NewsFetchProxy(NewsFetcherApi):
    def __init__(self, news_fetcher: NewsFetcherApi = news):
        self.news_fetcher = news_fetcher

    def get_news_from(
        self, platform: Literal["cointime", "caixin", "jin10", "gushitong"], start: datetime
    ) -> List[NewsInfo]:
        start_ts = dt_to_ts(start)
        logger.info("需要加锁更新本地新闻缓存")

        @with_lock(
            f"{platform}_query_lock",
            max_concurrent_access=1,
            expiration_time=300,
            timeout=300,
        )
        def lock_part():
            with create_transaction() as db:
                info_key = f"{platform}_news_cache_time_range"
                cache_time_range = db.kv_store.get(info_key)
                if (
                    cache_time_range is None
                    or start_ts < cache_time_range["query_start"]
                ):
                    if cache_time_range is not None:
                        logger.warning("尽量不要发生这种查询, 将会重新刷新数据库")
                        db.news_cache.delete_news_by_time_range(platform)
                    else:
                        logger.info(f"初始化本地{platform}新闻缓存")

                    news_list = self.news_fetcher.get_news_from(platform, start)
                    map_by(news_list, db.news_cache.add)
                    cache_time_range = {
                        "query_start": start_ts,
                        "query_end": dt_to_ts(datetime.now()),
                        "start": start_ts,
                        "end": start_ts,
                    }
                    if len(news_list) > 0:
                        cache_time_range.update(
                            {
                                "start": dt_to_ts(news_list[0].timestamp),
                                "end": dt_to_ts(news_list[-1].timestamp) + 1,
                            }
                        )
                    db.kv_store.set(info_key, cache_time_range)  # [start, end)
                    db.commit()
                    return news_list

                # 缓存消息新鲜度5分钟内的不要发起查询
                if (
                    cache_time_range["query_start"] <= start_ts
                    and start_ts < cache_time_range["query_end"]
                    and datetime.now() - ts_to_dt(cache_time_range["query_end"]) < timedelta(minutes=5)
                ):
                    logger.info(f"本地{platform}新闻缓存覆盖查询范围")
                    return db.news_cache.get_news_by_time_range(platform, start)

                if (
                    cache_time_range["query_start"] <= start_ts
                    and start_ts < cache_time_range["query_end"]
                ):
                    logger.info(f"本地{platform}新闻缓存覆盖前一部分范围")
                    news_list = db.news_cache.get_news_by_time_range(platform, start)
                    news_list_by_remote = self.news_fetcher.get_news_from(
                        platform, ts_to_dt(cache_time_range["end"])
                    )
                    map_by(news_list_by_remote, db.news_cache.add)
                    news_list.extend(news_list_by_remote)
                    cache_time_range.update({"query_end": dt_to_ts(datetime.now())})
                    if len(news_list_by_remote) > 0:
                        cache_time_range.update(
                            {"end": dt_to_ts(news_list_by_remote[-1].timestamp) + 1}
                        )
                    db.kv_store.set(info_key, cache_time_range)
                    db.commit()
                    return news_list

                if cache_time_range["query_end"] <= start_ts:
                    logger.info(f"本地{platform}新闻缓存没覆盖，从缓存缺失的地方开始查")
                    news_list_by_remote = self.news_fetcher.get_news_from(
                        platform, ts_to_dt(cache_time_range["end"])
                    )
                    map_by(news_list_by_remote, lambda n: db.news_cache.add(n))
                    cache_time_range.update({"query_end": dt_to_ts(datetime.now())})
                    if len(news_list_by_remote) > 0:
                        cache_time_range.update(
                            {"end": dt_to_ts(news_list_by_remote[-1].timestamp) + 1}
                        )
                    db.kv_store.set(info_key, cache_time_range)
                    db.commit()
                    return filter_by(
                        news_list_by_remote, lambda n: n.timestamp >= start
                    )

                assert False, "Should not go here"

        return lock_part()

    def get_news_during(
        self,
        platform: Literal["cointime", "caixin", "jin10"],
        start: datetime,
        end: datetime,
    ) -> List[NewsInfo]:
        start_ts, end_ts = dt_to_ts(start), dt_to_ts(end)
        assert start_ts < end_ts, "起始时间必须小于结束时间"

        info_key = f"{platform}_news_cache_time_range"

        def is_cache_satisfy(cache_query_range_info: Optional[Dict[str, int]]):
            if (
                cache_query_range_info
                and cache_query_range_info["query_start"] <= start_ts
                and end_ts <= cache_query_range_info["query_end"]
            ):
                logger.info(f"本地{platform}新闻缓存已覆盖查询范围:)")
                return True
            return False

        # 先不拿锁查缓存，缓存不满足要求再拿锁去查接口
        with create_transaction() as db:
            if is_cache_satisfy(db.kv_store.get(info_key)):
                return db.news_cache.get_news_by_time_range(platform, start, end)

        if platform == "caixin":
            return filter_by(
                self.get_news_from(platform, start), lambda n: n.timestamp < end
            )

        logger.info("需要加锁更新本地新闻缓存")

        @with_lock(
            f"{platform}_query_lock",
            max_concurrent_access=1,
            expiration_time=300,
            timeout=300,
        )
        def lock_part():
            with create_transaction() as db:
                # 我们假设数据库中平台新闻的最小时间戳和最大时间戳之间的新闻不存在缺漏
                cache_time_range = db.kv_store.get(info_key)
                # 等拿到锁之后，其它进程可能已经使得缓存满足要求了
                if is_cache_satisfy(cache_time_range):
                    return db.news_cache.get_news_by_time_range(platform, start, end)

                if cache_time_range is None:
                    logger.info(f"初始化本地{platform}新闻缓存")
                    news_list = self.news_fetcher.get_news_during(platform, start, end)
                    map_by(news_list, db.news_cache.add)

                    cache_time_range = {
                        "query_start": start_ts,
                        "query_end": end_ts,
                        "start": start_ts,
                        "end": start_ts + 1,
                    }
                    if len(news_list) > 0:
                        cache_time_range.update(
                            {
                                "start": dt_to_ts(news_list[0].timestamp),
                                "end": dt_to_ts(news_list[-1].timestamp) + 1,
                            }
                        )
                    db.kv_store.set(info_key, cache_time_range)  # [start, end)
                    db.commit()
                    return news_list

                if (
                    cache_time_range["query_start"] <= start_ts
                    and start_ts < cache_time_range["query_end"]
                    and cache_time_range["query_end"] <= end_ts
                ):
                    logger.info(f"本地{platform}新闻缓存覆盖前一部分范围")
                    news_result = db.news_cache.get_news_by_time_range(
                        platform, start, end
                    )
                    news_list_by_remote = self.news_fetcher.get_news_during(
                        platform, ts_to_dt(cache_time_range["end"]), end
                    )
                    map_by(news_list_by_remote, db.news_cache.add)
                    news_result.extend(news_list_by_remote)

                    cache_time_range.update({"query_end": end_ts})
                    if len(news_list_by_remote) > 0:
                        cache_time_range.update(
                            {"end": dt_to_ts(news_list_by_remote[-1].timestamp) + 1}
                        )

                    db.kv_store.set(info_key, cache_time_range)
                    db.commit()
                    return news_result

                if (
                    start_ts < cache_time_range["query_start"] < end_ts
                    and end_ts < cache_time_range["query_end"]
                ):
                    logger.info(f"本地{platform}新闻缓存覆盖后一部分范围")
                    news_result = self.news_fetcher.get_news_during(
                        platform, start, ts_to_dt(cache_time_range["start"])
                    )
                    news_list_by_local = db.news_cache.get_news_by_time_range(
                        platform, start, end
                    )
                    map_by(news_result, db.news_cache.add)
                    news_result.extend(news_list_by_local)

                    cache_time_range.update({"query_start": start_ts})
                    if len(news_result) > 0:
                        cache_time_range.update(
                            {"start": dt_to_ts(news_result[0].timestamp)}
                        )

                    db.kv_store.set(info_key, cache_time_range)
                    db.commit()
                    return news_result

                if (
                    start_ts < cache_time_range["query_start"]
                    and cache_time_range["query_end"] <= end_ts
                ):
                    logger.info(f"本地{platform}新闻缓存覆盖中间一部分范围")
                    news_list_by_local = db.news_cache.get_news_by_time_range(
                        platform, start, end
                    )
                    news_result_previous = self.news_fetcher.get_news_during(
                        platform, start, ts_to_dt(cache_time_range["start"])
                    )
                    news_result_after = self.news_fetcher.get_news_during(
                        platform, ts_to_dt(cache_time_range["end"] + 1), end
                    )
                    news_by_remote = news_result_previous + news_result_after
                    map_by(news_by_remote, db.news_cache.add)
                    news_result = (
                        news_result_previous + news_list_by_local + news_result_after
                    )

                    cache_time_range.update(
                        {"query_start": start_ts, "query_end": end_ts}
                    )
                    if len(news_by_remote) > 0:
                        cache_time_range.update(
                            {
                                "start": dt_to_ts(news_result[0].timestamp),
                                "end": dt_to_ts(news_result[-1].timestamp) + 1,
                            }
                        )

                    db.kv_store.set(info_key, cache_time_range)
                    db.commit()
                    return news_result

                missed_start = ts_to_dt(min(cache_time_range["end"], start_ts))
                missed_end = ts_to_dt(max(cache_time_range["start"], end_ts))
                logger.info(
                    f"本地{platform}新闻缓存没有覆盖，补充缺失的范围 {missed_start} - {missed_end}"
                )
                news_result = self.news_fetcher.get_news_during(
                    platform, missed_start, missed_end
                )
                map_by(news_result, db.news_cache.add)

                cache_time_range.update(
                    {
                        "query_start": min(start_ts, cache_time_range["query_start"]),
                        "query_end": max(end_ts, cache_time_range["query_end"]),
                    }
                )
                if len(news_result) > 0:
                    cache_time_range.update(
                        {
                            "start": min(
                                dt_to_ts(news_result[0].timestamp),
                                cache_time_range["start"],
                            ),
                            "end": max(
                                dt_to_ts(news_result[-1].timestamp) + 1,
                                cache_time_range["end"],
                            ),
                        }
                    )
                db.kv_store.set(info_key, cache_time_range)
                db.commit()
                return filter_by(
                    news_result, lambda x: x.timestamp < end and x.timestamp >= start
                )

        return lock_part()

    @use_cache(
        300,
        use_db_cache=True,
        serializer=lambda l: [x.to_dict() for x in l],
        deserializer=lambda l: [NewsInfo.from_dict(x) for x in l],
    )
    def get_current_hot_news(self, platform: str) -> List[NewsInfo]:
        return self.news_fetcher.get_current_hot_news(platform)


news_proxy = NewsFetchProxy()
