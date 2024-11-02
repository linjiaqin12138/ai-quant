from typing import Optional
from datetime import datetime, timezone, timedelta
from ..model import CryptoHistoryFrame

def timeframe_to_second(tframe: CryptoHistoryFrame) -> int:
    if tframe == '15m':
        return 15 * 60
    if tframe == '1d':
        return 60 * 60 * 24
    if tframe == '1h':
        return 60 * 60
    raise Exception(f'time range {tframe} not support')

def timeframe_to_ms(tframe) -> int:
    return timeframe_to_second(tframe) * 1000

def round_datetime(ts: datetime, tframe: CryptoHistoryFrame) -> datetime:
    return ts_to_dt(dt_to_ts(ts) // timeframe_to_ms(tframe) * timeframe_to_ms(tframe))

def dt_to_ts(ts: datetime) -> int:
    return int(ts.timestamp() * 1000)

def ts_to_dt(ts: int) -> datetime:
    return datetime.fromtimestamp(ts/ 1000)

def time_length_in_frame(start: datetime, end: datetime, frame: CryptoHistoryFrame) -> int:
    return int((dt_to_ts(round_datetime(end, frame)) - dt_to_ts(round_datetime(start, frame))) / timeframe_to_second(frame) / 1000)

def get_utc_now_isoformat() -> str:
    return to_utc_isoformat(datetime.now())

def to_utc_isoformat(dt: datetime) -> str:
    utc_dt = dt.astimezone(timezone.utc)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    
def utc_isoformat_to_dt(s: str) -> datetime:
    return datetime.fromisoformat(s)

def days_ago(days: int, zone: Optional[timezone] = None) -> datetime:
    if zone:
        return datetime.now(zone) - timedelta(days=days)
    return datetime.now() - timedelta(days=days)

def hours_ago(hours: int, zone: Optional[timezone] = None) -> datetime:
    if zone:
        return datetime.now(zone) - timedelta(hours=hours)
    return datetime.now() - timedelta(hours=hours)
