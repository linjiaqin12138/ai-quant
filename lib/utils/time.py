from typing import Optional
from datetime import datetime, timezone, timedelta
from ..model import CryptoHistoryFrame, CnStockHistoryFrame

def timeframe_to_second(tframe: CryptoHistoryFrame | CnStockHistoryFrame) -> int:
    if tframe == '15m':
        return 15 * 60
    if tframe == '1d':
        return 60 * 60 * 24
    if tframe == '1h':
        return 60 * 60
    raise Exception(f'time range {tframe} not support')

def timeframe_to_ms(tframe) -> int:
    return timeframe_to_second(tframe) * 1000

def round_datetime_in_local_zone(ts: datetime, tframe: CnStockHistoryFrame) -> datetime:
    """
    根据时间周期对datetime进行向下取整，基于本地时区
    
    Args:
        ts (datetime): 需要取整的时间
        tframe (CnStockHistoryFrame): 时间周期 ('1d', '1w', '1M', '1y' 等)
    
    Returns:
        datetime: 取整后的datetime对象
        
    Example:
        ts = '2024-03-15 14:23:45'
        tframe = '1M' -> '2024-03-01 00:00:00'
        tframe = '1y' -> '2024-01-01 00:00:00'
    """
    if tframe == '1d':
        return ts.replace(hour=0, minute=0, second=0, microsecond=0)
    elif tframe == '1w':
        # 获取本周一
        return (ts - timedelta(days=ts.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    elif tframe == '1M':
        # 回到本月第一天
        return ts.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        raise ValueError(f"Unsupported timeframe: {tframe}")

def round_datetime_in_period(ts: datetime, tframe: CryptoHistoryFrame) -> datetime:
    """
    将给定的datetime按照指定的时间周期(timeframe)向下取整，基于UTC时区
    不支持1week, 1month这样的tframe，因为UTC时间戳并不以星期一开始，而且一个月天数不固定
    
    Args:
        ts (datetime): 需要取整的时间
        tframe (CryptoHistoryFrame): 时间周期 (如 '15m', '1h', '1d')
    
    Returns:
        datetime: 取整后的datetime对象
        
    Example:
        如果 ts = '2024-03-15 14:23:45(UTC)' 且 tframe = '15m'
        返回 '2024-03-15 14:15:00(UTC)'
        如果 ts = '2024-11-1 00:00:00(东八区) (UTC时区为2024-10-31 16:00:00) 且 tframe = '1d
        返回 '2024-10-31 00:08:00(东八区) 即为UTC时区的2024-19-31 00:00:00
    """
    return ts_to_dt(dt_to_ts(ts) // timeframe_to_ms(tframe) * timeframe_to_ms(tframe))

def dt_to_ts(ts: datetime) -> int:
    return int(ts.timestamp() * 1000)

def ts_to_dt(ts: int) -> datetime:
    return datetime.fromtimestamp(ts/ 1000)

def time_length_in_frame(start: datetime, end: datetime, frame: CryptoHistoryFrame) -> int:
    return int((dt_to_ts(round_datetime_in_period(end, frame)) - dt_to_ts(round_datetime_in_period(start, frame))) / timeframe_to_second(frame) / 1000)

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

def minutes_ago(minutes: int, zone: Optional[timezone] = None) -> datetime:
    if zone:
        return datetime.now(zone) - timedelta(minutes=minutes)
    return datetime.now() - timedelta(minutes=minutes)
