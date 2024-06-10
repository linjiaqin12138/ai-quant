from datetime import datetime, timedelta

from lib.history import OhlcvHistory, print_timestamps
from lib.utils.logger import logger

def test_can_get_ohlcv_from_remote():
    fetcher = OhlcvHistory('ETH/USDT', '1h')
    current = fetcher.current()
    logger.debug(current)

def test_can_query_range_from_remote_and_second_time_hit_cache():
    fetcher = OhlcvHistory('BTC/USDT', '1h')
    range_data = fetcher.range_query(datetime.now() - timedelta(days = 1), datetime.now())
    assert len(range_data) == 24
    range_data = fetcher.range_query(datetime.now() - timedelta(days = 2), datetime.now() - timedelta(days = 1, hours=2))
    assert len(range_data) == 22
    range_data = fetcher.range_query(datetime.now() - timedelta(days = 3), datetime.now())
    assert len(range_data) == 72
    range_data = fetcher.range_query(datetime.now() - timedelta(days = 1), datetime.now() - timedelta(hours=2))
    assert len(range_data) == 22
    range_data = fetcher.range_query(datetime.now() - timedelta(days = 2), datetime.now() - timedelta(hours=1))
    assert len(range_data) == 47
    range_data = fetcher.range_query(datetime.now() - timedelta(days = 2), datetime.now() - timedelta(hours=1))
    assert len(range_data) == 47
    range_data = fetcher.range_query(datetime.now() - timedelta(days = 100), datetime.now())
    assert len(range_data) == 2400
    range_data = fetcher.range_query(datetime.now() - timedelta(days = 200), datetime.now())
    assert len(range_data) == 4800

    fetcher = OhlcvHistory('BTC/USDT', '1d')
    range_data = fetcher.range_query(datetime.now() - timedelta(days = 1), datetime.now() - timedelta(hours=3))
    assert len(range_data) == 1
    range_data = fetcher.range_query(datetime.now() - timedelta(days = 200), datetime.now())
    assert len(range_data) == 200
    