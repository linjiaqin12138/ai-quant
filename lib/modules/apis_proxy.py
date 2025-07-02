from typing import Dict, List
from datetime import datetime

from lib.adapter.database import create_transaction
from lib.adapter.apis import get_china_holiday

global_china_holiday_cache_by_year: Dict[str, List[str]] = {}


def is_china_business_day(day: datetime) -> bool:
    if day.weekday() >= 5:
        return False

    year_str = day.strftime("%Y")
    day_str = day.strftime("%Y-%m-%d")
    if year_str in global_china_holiday_cache_by_year:
        return day_str not in global_china_holiday_cache_by_year[year_str]

    with create_transaction() as db:
        cache_key = f"{year_str}_china_holiday"
        holiday_list = db.kv_store.get(f"{year_str}_china_holiday")
        if holiday_list is None:
            holiday_list = get_china_holiday(year_str)
            db.kv_store.set(cache_key, holiday_list)
            db.commit()
        global_china_holiday_cache_by_year[year_str] = holiday_list
        return day_str not in holiday_list


def is_china_business_time(time: datetime) -> bool:
    if time.hour < 9 or (time.hour == 9 and time.minute < 30):
        return False

    if time.hour > 15 or (time.hour == 15 and time.minute > 0):
        return False

    if not is_china_business_day(time):
        return False

    return True


__all__ = ["is_china_business_day", "is_china_business_time"]
