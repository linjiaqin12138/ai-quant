from datetime import datetime, timedelta

from lib.adapter.exchange.crypto_exchange.binance import BinanceExchange
from lib.adapter.exchange.cn_market_exchange import CnMarketExchange

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

def test_cn_market_exchange():
    cn_market = CnMarketExchange()
    stock_symbol = '515060'
    res = cn_market.fetch_ohlcv(symbol=stock_symbol, frame='1d', start=datetime(2024, 11, 1), end=datetime(2024, 11, 18, 1))
    assert len(res.data) == 11

    try:
        res = cn_market.fetch_ohlcv(symbol=stock_symbol, frame='1d', start=datetime(2024, 11, 1), end = datetime(2024, 11, 1))
        assert False, "Should not reach here"
    except ValueError as err:
        assert str(err) == '结束时间(2024-11-01 00:00:00)必须大于开始时间(2024-11-01 00:00:00)'
    
    res = cn_market.fetch_ohlcv(symbol=stock_symbol, frame='1d', start=datetime(2024, 11, 1), end = datetime(2024, 11, 4)) #中间两天是周末
    assert len(res.data) == 1
    res = cn_market.fetch_ohlcv(symbol=stock_symbol, frame='1d', start=datetime(2024, 11, 2), end = datetime(2024, 11, 3))
    assert len(res.data) == 0

    res = cn_market.fetch_ohlcv(symbol=stock_symbol, frame='1M', start=datetime(2024, 2, 1), end = datetime(2024, 4, 15))
    assert len(res.data) == 2
    assert res.data[0].timestamp.month == 2 and res.data[0].timestamp.day == 1 
    assert res.data[1].timestamp.month == 3 and res.data[1].timestamp.day == 1 

    etf_symbol = '515060'
    # 测试日线数据
    res = cn_market.fetch_ohlcv(symbol=etf_symbol, frame='1d', start=datetime(2024, 3, 1), end=datetime(2024, 3, 8))
    assert len(res.data) == 5  # 3月1日到3月8日之间应该有5个交易日
    
    # 测试周线数据
    res = cn_market.fetch_ohlcv(symbol=etf_symbol, frame='1w', start=datetime(2024, 2, 1), end=datetime(2024, 3, 15))
    assert len(res.data) == 5  # 这个时间范围内应该有5个完整的交易周
    assert res.data[0].timestamp.weekday() == 0  # 确保周线数据是从周一开始的
    

def test_cn_market_exchange_ticker():
    cn_market = CnMarketExchange()
    res = cn_market.fetch_ticker(symbol='002415')
    assert type(res.last) is float

    cn_market = CnMarketExchange()
    res = cn_market.fetch_ticker(symbol='515060')
    assert type(res.last) is float
    