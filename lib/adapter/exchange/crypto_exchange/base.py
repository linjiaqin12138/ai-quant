from typing import TypeVar

import ccxt
import requests

from ....utils.decorators import with_retry
from ....config import API_MAX_RETRY_TIMES

retry_decorator = with_retry((ccxt.errors.NetworkError, ccxt.errors.RequestTimeout, requests.ConnectionError), API_MAX_RETRY_TIMES)
G = TypeVar('G')

SUPPORT_RETRY_METHODS = [
    'fetch_ohlcv',
    'create_order',
    'fetch_ticker',

    # Binance
    'fapidataGetGloballongshortaccountratio',
    'fapidataGetToplongshortaccountratio',
    'fapidataGetToplongshortpositionratio',
    'fapipublicGetPremiumindex'
]

def retry_patch(exchange: G) -> G:
    for method in SUPPORT_RETRY_METHODS:
        func = getattr(exchange, method)
        if callable(func):
            setattr(exchange, method, retry_decorator(func))
    return exchange
