from datetime import datetime, timedelta
import threading
import unittest.mock
from unittest.mock import call

from lib.model.common import Ohlcv, OhlcvHistory
from lib.adapter.database import create_transaction
from lib.modules.trade import CryptoTrade

def test_only_call_once_when_parallel_call():
    # 创建一个共享的 mock exchange 对象
    mock_exchange = unittest.mock.Mock()
    
    # 配置 mock exchange 对象的 fetch_ohlcv 方法
    def fetch_ohlcv_side_effect(symbol, frame, start, end, *args, **kwargs):
        # 创建一些测试数据作为返回值
        data = []
        current = start
        while current < end:
            data.append(Ohlcv(
                timestamp=current,
                open=100, high=110, low=90, close=105, volume=1
            ))
            current += timedelta(hours=1) if frame == '1h' else timedelta(minutes=1)
        # 返回数据列表，而不是 OhlcvHistory 对象
        return OhlcvHistory(symbol=symbol, frame=frame, data=data)
    
    mock_exchange.fetch_ohlcv = unittest.mock.Mock(side_effect=fetch_ohlcv_side_effect)
    
    def fetch_data():
        # 使用共享的 mock exchange 对象
        crypto_module = CryptoTrade(exchange=mock_exchange)
        crypto_module.get_ohlcv_history(
            'BTC/USDT', '1h', 
            datetime.now() - timedelta(days=1), datetime.now()
        )

    # Create two threads
    thread1 = threading.Thread(target=fetch_data)
    thread2 = threading.Thread(target=fetch_data)

    # Start both threads
    thread2.start()
    thread2.join()
    
    thread1.start()
    # Wait for both threads to finish
    thread1.join()
    
    # 验证 fetch_ohlcv 只被调用了一次
    assert mock_exchange.fetch_ohlcv.call_count == 1
    
    # 清理数据库
    with create_transaction() as db:
        db.session.execute('DELETE FROM crypto_ohlcv_cache_1h')
        db.commit()

def generate_mock_ohlcv_data(start_dt: datetime, end_dt: datetime, frame: str = '1h') -> OhlcvHistory:
    """辅助函数：根据时间范围生成模拟 OHLCV 数据"""
    data = []
    current_dt = start_dt
    delta = timedelta(hours=1) if frame == '1h' else timedelta(minutes=1)

    # 确保时间戳是对齐的时间单位
    current_dt = current_dt.replace(minute=0, second=0, microsecond=0) if frame == '1h' else current_dt.replace(second=0, microsecond=0)
    
    while current_dt < end_dt:
        data.append(Ohlcv(
            timestamp=current_dt,
            open=100, high=110, low=90, close=105, volume=1
        ))
        current_dt += delta
    return OhlcvHistory(symbol='BTC/USDT', frame=frame, data=data)

def test_can_query_range_from_remote_and_second_time_hit_cache():
    # 创建 mock exchange 对象
    mock_exchange = unittest.mock.Mock()
    
    # 配置 mock_exchange.fetch_ohlcv 的行为
    def fetch_ohlcv_side_effect(symbol, frame, start, end, *args, **kwargs):
        return generate_mock_ohlcv_data(start, end, frame)
    
    mock_exchange.fetch_ohlcv = unittest.mock.Mock(side_effect=fetch_ohlcv_side_effect)
    
    # 创建 CryptoTrade 实例，直接传入 mock_exchange
    crypto = CryptoTrade(
        exchange=mock_exchange
    )
    
    june_30th_11_clock = datetime(2024, 6, 30, 11, 56, 40, 290935)
    
    # 第一次查询会去后端
    result = crypto.get_ohlcv_history(
        'BTC/USDT', '1h', 
        june_30th_11_clock - timedelta(days=1), june_30th_11_clock
    )
    
    assert len(result.data) == 24
    assert mock_exchange.fetch_ohlcv.call_count == 1
    mock_exchange.fetch_ohlcv.assert_called_once_with(
        'BTC/USDT', '1h', 
        datetime(2024, 6, 29, 11, 0, 0, 0),
        datetime(2024, 6, 30, 11, 0, 0, 0)
    )
    
    # 重置 mock 对象记录
    mock_exchange.fetch_ohlcv.reset_mock()
    
    # 第二次相同的查询会命中缓存不会去后端
    result = crypto.get_ohlcv_history(
        'BTC/USDT', '1h', 
        june_30th_11_clock - timedelta(days=1), june_30th_11_clock
    )
    
    assert len(result.data) == 24
    assert mock_exchange.fetch_ohlcv.call_count == 0
    
    # 查询的范围数据库能找到所有记录，不会去后端
    result = crypto.get_ohlcv_history(
        'BTC/USDT', '1h', 
        june_30th_11_clock - timedelta(hours=20), june_30th_11_clock - timedelta(hours=10)
    )
    
    assert len(result.data) == 10
    assert mock_exchange.fetch_ohlcv.call_count == 0
    
    # 重置 mock 对象记录
    mock_exchange.fetch_ohlcv.reset_mock()
    
    # 查询的范围在数据库中能找到后面一半连续数据，只向后端前半部分数据
    result = crypto.get_ohlcv_history(
        'BTC/USDT', '1h', 
        june_30th_11_clock - timedelta(days=2), june_30th_11_clock
    )
    
    assert len(result.data) == 48
    mock_exchange.fetch_ohlcv.assert_called_once_with(
        'BTC/USDT', '1h', 
        datetime(2024, 6, 28, 11, 0, 0, 0),
        datetime(2024, 6, 29, 11, 0, 0, 0)
    )
    assert mock_exchange.fetch_ohlcv.call_count == 1
    
    # 数据在数据库中分散成碎片，分多次查询缺失的部分
    mock_exchange.fetch_ohlcv.reset_mock()
    
    result = crypto.get_ohlcv_history(
        'BTC/USDT', '1h', 
        june_30th_11_clock - timedelta(days=4), june_30th_11_clock - timedelta(days=3)
    )
    
    assert len(result.data) == 24
    mock_exchange.fetch_ohlcv.assert_called_once_with(
        'BTC/USDT', '1h', 
        datetime(2024, 6, 26, 11, 0, 0, 0),
        datetime(2024, 6, 27, 11, 0, 0, 0)
    )
    
    mock_exchange.fetch_ohlcv.reset_mock()
    
    result = crypto.get_ohlcv_history(
        'BTC/USDT', '1h', 
        june_30th_11_clock - timedelta(days=5), june_30th_11_clock - timedelta(days=4, hours=23)
    )
    
    assert len(result.data) == 1
    mock_exchange.fetch_ohlcv.assert_called_once_with(
        'BTC/USDT', '1h', 
        datetime(2024, 6, 25, 11, 0, 0, 0),
        datetime(2024, 6, 25, 12, 0, 0, 0)
    )
    
    mock_exchange.fetch_ohlcv.reset_mock()
    
    result = crypto.get_ohlcv_history(
        'BTC/USDT', '1h', 
        june_30th_11_clock - timedelta(days=6), june_30th_11_clock + timedelta(hours=4)
    )
    
    assert len(result.data) == 6 * 24 + 4
    
    # 检查所有调用，但不关心顺序
    expected_calls = [
        call('BTC/USDT', '1h', datetime(2024, 6, 24, 11, 0, 0, 0), datetime(2024, 6, 25, 11, 0, 0, 0)),
        call('BTC/USDT', '1h', datetime(2024, 6, 25, 12, 0, 0, 0), datetime(2024, 6, 26, 11, 0, 0, 0)),
        call('BTC/USDT', '1h', datetime(2024, 6, 27, 11, 0, 0, 0), datetime(2024, 6, 28, 11, 0, 0, 0)),
        call('BTC/USDT', '1h', datetime(2024, 6, 30, 11, 0, 0, 0), datetime(2024, 6, 30, 15, 0, 0, 0))
    ]
    mock_exchange.fetch_ohlcv.assert_has_calls(expected_calls, any_order=True)
    assert mock_exchange.fetch_ohlcv.call_count == 4
    
    # 清理数据库
    with create_transaction() as db:
        result = db.session.execute('DELETE FROM crypto_ohlcv_cache_1h')
        assert result.row_count == 6 * 24 + 4
        db.session.commit()

