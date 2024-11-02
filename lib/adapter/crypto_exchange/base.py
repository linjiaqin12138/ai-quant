from typing import TypeVar
from dataclasses import dataclass
from datetime import datetime
import abc

import ccxt
import requests

from ...utils.retry import with_retry
from ...model import CryptoOhlcvHistory, CryptoHistoryFrame, CryptoOrderType, CryptoOrderSide, CryptoOrder
from ...config import API_MAX_RETRY_TIMES

retry_decorator = with_retry((ccxt.errors.NetworkError, ccxt.errors.RequestTimeout, requests.exceptions.ConnectTimeout), API_MAX_RETRY_TIMES)
G = TypeVar('G')

SUPPORT_RETRY_METHODS = [
    'fetch_ohlcv',
    'create_order',
    'fetch_ticker',

    # Binance
    'fapidataGetGloballongshortaccountratio',
    'fapidataGetToplongshortaccountratio',
    'fapidataGetToplongshortpositionratio'
]

@dataclass
class CryptoTicker:
    last: float # 最新价格

def retry_patch(exchange: G) -> G:
    for method in SUPPORT_RETRY_METHODS:
        func = getattr(exchange, method)
        if callable(func):
            setattr(exchange, method, retry_decorator(func))
    return exchange

class CryptoExchangeAbstract(abc.ABC):

    @abc.abstractmethod
    def fetch_ticker(self, pair: str) -> CryptoTicker:
        raise NotImplementedError
    @abc.abstractmethod
    def fetch_ohlcv(self, pair: str, frame: CryptoHistoryFrame, start: datetime, end: datetime = datetime.now()) -> CryptoOhlcvHistory:
        raise NotImplementedError
    @abc.abstractmethod
    def create_order(self, pair: str, type: CryptoOrderType, side: CryptoOrderSide, amount: float, price: float = None) -> CryptoOrder: 
        raise NotImplementedError
        