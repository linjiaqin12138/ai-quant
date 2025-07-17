from typing import Any, Dict, Optional, TypedDict
from lib.modules.trade.ashare import ashare
from lib.modules.trade.crypto import crypto

def get_ohlcv_history(symbol: str, limit=int, frame = '1d'):
    """
    获取指定symbol和时间范围的历史K线数据
    """
    if symbol.endswith('USDT'):
        return crypto.get_ohlcv_history(symbol, frame, limit=limit).data
    else:
        return ashare.get_ohlcv_history(symbol, frame, limit=limit).data
    
