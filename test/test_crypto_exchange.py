from datetime import datetime, timedelta

from lib.adapter.crypto_exchange.binance import BinanceExchange

def test_can_query_range_from_remote():
    binance = BinanceExchange(True)
    june_30th_11_clock = datetime(2024, 6, 30, 11, 0, 0, 0)
    res = binance.fetch_ohlcv('BTC/USDT', '1h', june_30th_11_clock - timedelta(days=1), june_30th_11_clock)
    assert len(res.data) == 24
    assert res.data[0].timestamp == datetime(2024, 6, 29, 11, 0, 0, 0)
    assert res.data[-1].timestamp == datetime(2024, 6, 30, 10, 0, 0, 0)

    june_30th_11_30_clock = datetime(2024, 6, 30, 11, 30, 0, 0)
    res = binance.fetch_ohlcv('BTC/USDT', '1h', june_30th_11_30_clock - timedelta(days=1), june_30th_11_30_clock)
    assert len(res.data) == 24
    assert res.data[0].timestamp == datetime(2024, 6, 29, 12, 0, 0, 0)
    assert res.data[-1].timestamp == datetime(2024, 6, 30, 11, 0, 0, 0)