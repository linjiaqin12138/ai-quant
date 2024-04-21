import datetime

def unify_ts(ts_in_sec: int, slot_range: int = 60) -> int:
    return int(ts_in_sec - ts_in_sec % slot_range)
def dt_to_int(dt: datetime.datetime) -> int:
    return datetime.datetime.timestamp(dt)
def curr_ts() -> int:
    return dt_to_int(datetime.datetime.now())
def unify_dt(dt: datetime.datetime, slot_range: int = 60) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(unify_ts(curr_ts(), slot_range))
