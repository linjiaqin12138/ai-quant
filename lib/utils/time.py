from datetime import datetime
from ..model import CryptoHistoryFrame

def timeframe_to_second(tframe: CryptoHistoryFrame) -> int:
    if tframe == '15m':
        return 15 * 60
    if tframe == '1d':
        return 60 * 60 * 24
    if tframe == '1h':
        return 60 * 60
    raise Exception(f'time range {tframe} not support')

def round_datetime(ts: datetime, tframe: CryptoHistoryFrame) -> datetime:
    if tframe == '1d':
        return ts.replace(hour=0, minute=0, second=0, microsecond=0)
    if tframe == '1h':
        return ts.replace(minute=0, second=0, microsecond=0)
    if tframe == '15m':
        return ts.replace(minute=ts.minute // 15 * 15, second=0, microsecond=0)
    raise Exception(f'time range {tframe} not support')

def dt_to_ts(ts: datetime) -> int:
    return int(ts.timestamp() * 1000)

def time_length_in_frame(start: datetime, end: datetime, frame: CryptoHistoryFrame) -> int:
    return int((dt_to_ts(round_datetime(end, frame)) - dt_to_ts(round_datetime(start, frame))) / timeframe_to_second(frame) / 1000)