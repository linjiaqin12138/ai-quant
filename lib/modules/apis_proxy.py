from typing import Dict, List
from datetime import datetime

from adapter.database.session import SqlAlchemySession
from adapter.database.kv_store import KeyValueStore
from adapter.apis import get_china_holiday

global_china_holiday_cache_by_year: Dict[str, List[str]] = {}
def is_china_business_day(day: datetime) -> bool:
    year_str = day.strftime('%Y')
    day_str = day.strftime('%Y-%m-%d')
    if year_str in global_china_holiday_cache_by_year:
        return day_str not in global_china_holiday_cache_by_year[year_str]

    with SqlAlchemySession() as sess:
        kv_store = KeyValueStore(session=sess)
        cache_key = f'{year_str}_china_holiday'
        holiday_list = kv_store.get(f'{year_str}_china_holiday')
        if holiday_list is None:
            holiday_list = get_china_holiday(year_str)
            kv_store.set(cache_key, holiday_list)
            sess.commit()
        global_china_holiday_cache_by_year[year_str] = holiday_list
        return day_str not in holiday_list
    
__all__ = [
    'is_china_business_day'
]