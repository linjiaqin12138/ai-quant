from typing import List, Any
from datetime import datetime, timedelta
from sqlalchemy import create_engine

from lib.adapter.exchange.api import ExchangeAPI
from lib.adapter.exchange.crypto_exchange.binance import BinanceExchange
from lib.adapter.database.session import SqlAlchemySession
from lib.model import CryptoOhlcvHistory, Ohlcv, TradeTicker
from lib.modules.crypto import CryptoOperationModule, ModuleDependency
from lib.adapter.database.sqlalchemy import metadata_obj
from lib.utils.time import timeframe_to_second
from lib.logger import logger

class FakeExchange(ExchangeAPI):
    called_log = { 
        'fetch_ohlcv': {
            'times': 0,
            'params': []
        }
    }

    def clear_log(self):
        self.called_log['fetch_ohlcv']['times'] = 0
        self.called_log['fetch_ohlcv']['params'] = []
    
    def called_times(self, function_name: str):
        return self.called_log[function_name]['times']

    def called_with(self, function_name: str, params_list: List[List[Any]]) -> bool:
        if self.called_log[function_name]['times'] != len(params_list):
            return False
        for idx in range(len(params_list)):
            if len(params_list[idx]) != len(self.called_log[function_name]['params'][idx]):
                return False
            for param_idx in range(len(params_list[idx])):
                if params_list[idx][param_idx] != self.called_log[function_name]['params'][idx][param_idx]:
                    return False
        return True

    def fetch_ticker(self, symbol: str) -> TradeTicker:
        return super().fetch_ticker(symbol)

    def create_order():
        pass

    def fetch_ohlcv(self, symbol, frame, start, end) -> CryptoOhlcvHistory:
        self.called_log['fetch_ohlcv']['times'] += 1
        self.called_log['fetch_ohlcv']['params'].append([
            symbol, frame, start, end
        ])
        logger.debug(f'call fetch_ohlcv with params {symbol}, {frame}, {start}, {end}')
        data_count = int((end - start) / timedelta(seconds=timeframe_to_second(frame)))
        data = []
        for i in range(data_count):
            data.append(
                Ohlcv(
                    timestamp = start + timedelta(seconds=timeframe_to_second(frame) * i),
                    open = 0,
                    high = 0,
                    low = 0,
                    close = 0,
                    volume = 0
                )
            )
        
        return CryptoOhlcvHistory(
            symbol = symbol, 
            frame = frame, 
            exchange = 'fake', 
            data = data
        )

def test_can_query_range_from_remote_and_second_time_hit_cache():
    # fetcher = OhlcvHistory('BTC/USDT', '1h')
    engine = create_engine("sqlite+pysqlite:///:memory:", echo=False)
    metadata_obj.create_all(engine)
    fake_excahnge = FakeExchange()
    session = SqlAlchemySession(engine)
    dependency = ModuleDependency(
        session = session,
        exchange = fake_excahnge,
    )
    crypto_module = CryptoOperationModule(dependency)
    june_30th_11_clock = datetime(2024, 6, 30, 11, 56, 40, 290935)
    # 第一次查询会命中缓存不会去后端
    result = crypto_module.get_ohlcv_history(
        'BTC/USDT', '1h', 
        june_30th_11_clock - timedelta(days = 1), june_30th_11_clock
    )
    assert len(result.data) == 24
    assert fake_excahnge.called_times('fetch_ohlcv') == 1
    assert fake_excahnge.called_with('fetch_ohlcv', [
        [
            'BTC/USDT', '1h', 
            datetime(2024, 6, 29, 11, 0, 0, 0),
            datetime(2024, 6, 30, 11, 0, 0, 0)
        ]
    ])
    fake_excahnge.clear_log()

    # 第二次相同的查询会命中缓存不会去后端
    result = crypto_module.get_ohlcv_history(
        'BTC/USDT', '1h', 
        june_30th_11_clock - timedelta(days = 1), june_30th_11_clock
    )
    assert len(result.data) == 24
    assert fake_excahnge.called_times('fetch_ohlcv') == 0
    # 查询的范围数据库能找到所有记录，不会去后端
    result = crypto_module.get_ohlcv_history(
        'BTC/USDT', '1h', 
        june_30th_11_clock - timedelta(hours = 20), june_30th_11_clock - timedelta(hours = 10)
    )
    assert len(result.data) == 10
    assert fake_excahnge.called_times('fetch_ohlcv') == 0

    fake_excahnge.clear_log()
    # 查询的范围在数据库中能找到后面一半连续数据，只向后端前半部分数据
    result = crypto_module.get_ohlcv_history(
        'BTC/USDT', '1h', 
        june_30th_11_clock - timedelta(days = 2), june_30th_11_clock
    )
    assert len(result.data) == 48
    assert fake_excahnge.called_with('fetch_ohlcv', [
        [
            'BTC/USDT', '1h', 
            datetime(2024, 6, 28, 11, 0, 0, 0),
            datetime(2024, 6, 29, 11, 0, 0, 0)
        ]
    ])
    assert fake_excahnge.called_times('fetch_ohlcv') == 1

    # 数据在数据库中分散成碎片，分多次查询缺失的部分
    fake_excahnge.clear_log()
    result = crypto_module.get_ohlcv_history(
        'BTC/USDT', '1h', 
        june_30th_11_clock - timedelta(days = 4), june_30th_11_clock - timedelta(days = 3)
    )
    assert len(result.data) == 24
    assert fake_excahnge.called_with('fetch_ohlcv', [
        [
            'BTC/USDT', '1h', 
            datetime(2024, 6, 26, 11, 0, 0, 0),
            datetime(2024, 6, 27, 11, 0, 0, 0)
        ],
    ])
    fake_excahnge.clear_log()
    result = crypto_module.get_ohlcv_history(
        'BTC/USDT', '1h', 
        june_30th_11_clock - timedelta(days = 5), june_30th_11_clock - timedelta(days = 4, hours=23)
    )
    assert len(result.data) == 1
    assert fake_excahnge.called_with('fetch_ohlcv', [
        [
            'BTC/USDT', '1h', 
            datetime(2024, 6, 25, 11, 0, 0, 0),
            datetime(2024, 6, 25, 12, 0, 0, 0)
        ],
    ])
    fake_excahnge.clear_log()
    result = crypto_module.get_ohlcv_history(
        'BTC/USDT', '1h', 
        june_30th_11_clock - timedelta(days = 6), june_30th_11_clock + timedelta(hours = 4)
    )
    assert len(result.data) == 6 * 24 + 4
    assert fake_excahnge.called_with('fetch_ohlcv', [
        [
            'BTC/USDT', '1h', 
            datetime(2024, 6, 24, 11, 0, 0, 0),
            datetime(2024, 6, 25, 11, 0, 0, 0)
        ],
        [
            'BTC/USDT', '1h', 
            datetime(2024, 6, 25, 12, 0, 0, 0),
            datetime(2024, 6, 26, 11, 0, 0, 0)
        ],
        [
            'BTC/USDT', '1h', 
            datetime(2024, 6, 27, 11, 0, 0, 0),
            datetime(2024, 6, 28, 11, 0, 0, 0)
        ],
        [
            'BTC/USDT', '1h', 
            datetime(2024, 6, 30, 11, 0, 0, 0),
            datetime(2024, 6, 30, 15, 0, 0, 0)
        ]
    ])
    
    with session:
        result = session.execute('DELETE FROM crypto_ohlcv_cache_1h')
        assert result.row_count == 6 * 24 + 4
        fake_excahnge.clear_log()
        session.commit()
    
    # test with real module
    dependency.exchange = BinanceExchange()
    result = crypto_module.get_ohlcv_history(
        'BTC/USDT', '1h', 
        june_30th_11_clock - timedelta(days = 21), june_30th_11_clock
    )
    assert len(result.data) == 21 * 24
    assert result.data[0].timestamp == datetime(2024, 6, 9, 11, 0, 0, 0)
    assert result.data[-1].timestamp == datetime(2024, 6, 30, 10, 0, 0, 0)