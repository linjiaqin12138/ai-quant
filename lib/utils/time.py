import datetime


def unify_ts(ts_in_sec: float, slot_range: int = 60) -> float:
    return float(ts_in_sec - ts_in_sec % slot_range)


# Return in second
def dt_to_float(dt: datetime.datetime) -> float:
    return datetime.datetime.timestamp(dt)


def curr_ts() -> float:
    return dt_to_float(datetime.datetime.now())


def unify_dt(dt: datetime.datetime, slot_range: int = 60) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(unify_ts(dt_to_float(dt), slot_range))
