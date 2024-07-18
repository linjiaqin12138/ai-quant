from datetime import datetime
import numpy as np
from lib.utils.ohlcv import macd_info, boll_info, sar_info
from lib.modules.crypto import crypto


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