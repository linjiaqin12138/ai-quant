from datetime import datetime
import numpy as np
import json

from lib.model.common import Ohlcv
from lib.utils.ohlcv import macd_info, boll_info, sar_info, detect_candle_patterns
from lib.modules.exchange_proxy import crypto

def test_indicators():
    history = crypto.get_ohlcv_history('BTC/USDT', '1d', datetime(2024, 4, 8, 8), datetime(2024, 7, 17, 8))
    result = macd_info(history.data)
    assert result['gold_cross_idxs'] == [57, 95]
    assert result['dead_cross_idxs'] == [53, 61]
    assert np.isnan(result['macd_hist'][32])
    assert result['macd_hist'][33] > 0

    result = boll_info(history.data)
    assert np.isnan(result['lowerband'][18])
    assert result['lowerband'][19] > 0
    assert np.isnan(result['middleband'][18])
    assert result['middleband'][19] > 0
    assert np.isnan(result['upperband'][18])
    assert result['upperband'][19] > 0
    assert result['turn_good_idxs'] == [26, 35, 37, 97]
    
    result = sar_info(history.data)
    assert np.isnan(result['sar'][0])
    assert result['sar'][1] > 0
    assert result['turn_up_idxs'] == [13, 28, 57, 83, 97]

def test_pattern():
    history_data = [
        Ohlcv(timestamp=datetime(2024, 11, 10, 8, 0), open=76677.46, high=81500.0, low=76492.0, close=80370.01, volume=61830.100435), 
        Ohlcv(timestamp=datetime(2024, 11, 11, 8, 0), open=80370.01, high=89530.54, low=80216.01, close=88647.99, volume=82323.665776), 
        Ohlcv(timestamp=datetime(2024, 11, 12, 8, 0), open=88648.0, high=89940.0, low=85072.0, close=87952.01, volume=97299.887911), 
        Ohlcv(timestamp=datetime(2024, 11, 13, 8, 0), open=87952.0, high=93265.64, low=86127.99, close=90375.2, volume=86763.854127), 
        Ohlcv(timestamp=datetime(2024, 11, 14, 8, 0), open=90375.21, high=91790.0, low=86668.21, close=87325.59, volume=56729.51086), 
        Ohlcv(timestamp=datetime(2024, 11, 15, 8, 0), open=87325.59, high=91850.0, low=87073.38, close=91032.07, volume=47927.95068), 
        Ohlcv(timestamp=datetime(2024, 11, 16, 8, 0), open=91032.08, high=91779.66, low=90056.17, close=90586.92, volume=22717.87689), 
        Ohlcv(timestamp=datetime(2024, 11, 17, 8, 0), open=90587.98, high=91449.99, low=88722.0, close=89855.99, volume=23867.55609), 
        Ohlcv(timestamp=datetime(2024, 11, 18, 8, 0), open=89855.98, high=92594.0, low=89376.9, close=90464.08, volume=46545.03448), 
        Ohlcv(timestamp=datetime(2024, 11, 19, 8, 0), open=90464.07, high=93905.51, low=90357.0, close=92310.79, volume=43660.04682)
    ]
    # history_data = cn_market.get_ohlcv_history("603529", '1d', days_ago(365)).data
    results = detect_candle_patterns(history_data)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    assert len(results['last_candle_patterns']) == 1 and results['last_candle_patterns'][0]['name'] == '陷阱形态'
    
    for _, pattern_result in results['pattern_results'].items():
        if pattern_result['is_last_candle_pattern']:
            assert pattern_result['pattern_info']['name'] == '陷阱形态'
        print(f"{pattern_result['pattern_info']['name']}: {pattern_result['pattern_info']['description']}")
        
        for pattern_idx in pattern_result['pattern_idxs']:
            print(f'{history_data[pattern_idx].timestamp.isoformat()}')
            
