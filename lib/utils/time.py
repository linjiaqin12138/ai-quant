from typing import Optional
from datetime import datetime, timezone, timedelta
import re
from ..model import CryptoHistoryFrame, CnStockHistoryFrame


def parse_datetime_string(date_string: str) -> Optional[datetime]:
    """
    解析时间字符串为datetime对象
    支持多种常见的时间格式

    Args:
        date_string: 时间字符串

    Returns:
        datetime对象，解析失败返回None

    Example:
        parse_datetime_string("2024-03-15T14:23:45Z") -> datetime(2024, 3, 15, 14, 23, 45)
        parse_datetime_string("2024-03-15 14:23:45") -> datetime(2024, 3, 15, 14, 23, 45)
        parse_datetime_string("Mar 15, 2024") -> datetime(2024, 3, 15, 0, 0, 0)
    """
    if not date_string:
        return None

    # 清理字符串
    date_string = date_string.strip()

    # 常见的时间格式模式
    patterns = [
        # ISO 8601 格式
        (
            r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?(?:Z|[+-]\d{2}:\d{2})?",
            lambda m: datetime(
                int(m.group(1)),
                int(m.group(2)),
                int(m.group(3)),
                int(m.group(4)),
                int(m.group(5)),
                int(m.group(6)),
            ),
        ),
        # 标准格式: 2024-03-15 14:23:45
        (
            r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})",
            lambda m: datetime(
                int(m.group(1)),
                int(m.group(2)),
                int(m.group(3)),
                int(m.group(4)),
                int(m.group(5)),
                int(m.group(6)),
            ),
        ),
        # 日期格式: 2024-03-15
        (
            r"(\d{4})-(\d{2})-(\d{2})$",
            lambda m: datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))),
        ),
        # 美式格式: Mar 15, 2024 或 March 15, 2024
        (
            r"(\w+)\s+(\d{1,2}),?\s+(\d{4})",
            lambda m: _parse_month_day_year(
                m.group(1), int(m.group(2)), int(m.group(3))
            ),
        ),
        # 时间戳格式: 1234567890 (10位) 或 1234567890123 (13位)
        (r"^(\d{10})$", lambda m: datetime.fromtimestamp(int(m.group(1)))),
        (r"^(\d{13})$", lambda m: datetime.fromtimestamp(int(m.group(1)) / 1000)),
        # 简单格式: 03/15/2024 或 15/03/2024
        (
            r"(\d{1,2})/(\d{1,2})/(\d{4})",
            lambda m: datetime(
                int(m.group(3)), int(m.group(1)), int(m.group(2))
            ),
        ),
    ]

    for pattern, parser in patterns:
        match = re.search(pattern, date_string, re.IGNORECASE)
        if match:
            try:
                return parser(match)
            except (ValueError, AttributeError):
                continue
    
    # 匹配 '3 days ago', '1 day ago', '1 hour ago', '15 minutes ago' 等
    match = re.match(r"(\d+)\s+(day|hour|minute)s?\s+ago", date_string, re.IGNORECASE)
    if match:
        num = int(match.group(1))
        unit = match.group(2).lower()
        if unit == 'day':
            return days_ago(num)
        elif unit == 'hour':
            return hours_ago(num)
        elif unit == 'minute':
            return minutes_ago(num)

    return None


def _parse_month_day_year(month_str: str, day: int, year: int) -> datetime:
    """
    解析月份字符串为数字
    """
    month_names = {
        "jan": 1,
        "january": 1,
        "feb": 2,
        "february": 2,
        "mar": 3,
        "march": 3,
        "apr": 4,
        "april": 4,
        "may": 5,
        "jun": 6,
        "june": 6,
        "jul": 7,
        "july": 7,
        "aug": 8,
        "august": 8,
        "sep": 9,
        "september": 9,
        "oct": 10,
        "october": 10,
        "nov": 11,
        "november": 11,
        "dec": 12,
        "december": 12,
    }

    month_num = month_names.get(month_str.lower())
    if month_num is None:
        raise ValueError(f"Unknown month: {month_str}")

    return datetime(year, month_num, day)


def timeframe_to_second(tframe: str) -> int:
    if tframe == "15m":
        return 15 * 60
    if tframe == "1d":
        return 60 * 60 * 24
    if tframe == "1h":
        return 60 * 60
    if tframe == "1s":
        return 1
    raise Exception(f"time range {tframe} not support")


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
    if tframe == "1d":
        return ts.replace(hour=0, minute=0, second=0, microsecond=0)
    elif tframe == "1w":
        # 获取本周一
        return (ts - timedelta(days=ts.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    elif tframe == "1M":
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
    return datetime.fromtimestamp(ts / 1000)


def time_length_in_frame(
    start: datetime, end: datetime, frame: CryptoHistoryFrame
) -> int:
    return int(
        (
            dt_to_ts(round_datetime_in_period(end, frame))
            - dt_to_ts(round_datetime_in_period(start, frame))
        )
        / timeframe_to_second(frame)
        / 1000
    )


def get_utc_now_isoformat() -> str:
    return to_utc_isoformat(datetime.now())


def to_utc_isoformat(dt: datetime) -> str:
    utc_dt = dt.astimezone(timezone.utc)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def utc_isoformat_to_dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def time_ago_from(
    unit: int, frame: str, ago_from: datetime = datetime.now()
) -> datetime:
    return ago_from - unit * timedelta(seconds=timeframe_to_second(frame))


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
