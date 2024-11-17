import ccxt
from typing import TypedDict, List, Callable, TypeVar, Any, Dict
from datetime import datetime
from ....config import get_binance_config
from ....logger import logger
from ....model import CryptoOhlcvHistory, TradeTicker, CryptoHistoryFrame, Ohlcv, OrderType, OrderSide, CryptoOrder
from ....utils.time import dt_to_ts, timeframe_to_second, time_length_in_frame, ts_to_dt
from ....utils.list import map_by 
from ..api import ExchangeAPI
from .base import retry_patch


def binance_test_patch(exchange: ccxt.binance) -> ccxt.binance:
    def call_with_test(func):
        def wrapper(*args, **kwargs):
            if kwargs['params']:
                kwargs['params']['test'] = True
            else:
                kwargs['params'] = { 'test': True }
            func(*args, **kwargs)
        return wrapper
    
    for method in dir(exchange):
        func = getattr(exchange, method)
        if callable(func):
            setattr(exchange, method, call_with_test(func))

LongShortAccountInfo = TypedDict('LongShortAccountInfo', {
    "longAccount": float,
    "shortAccount": float,
    "longShortRatio": float,
    "timestamp": datetime
})

LatestFuturesPriceInfo = TypedDict('LatestFuturesPriceInfo', {
    'symbol': str,
    'markPrice': float,
    'indexPrice': float,
    'estimatedSettlePrice': float,
    'lastFundingRate': float,  # 最近更新的资金费率
    'interestRate': float,
    'nextFundingTime': float,
    'time': datetime # 更新时间
})

G = TypeVar("G")
def with_slice(slice_count: int, frame: CryptoHistoryFrame) -> Callable[[G], G]:
    def decorator(function: G) -> G:
        def slice_func(total_start: int, total_count: int) -> List[Dict[str, Any]]:
            data = []
            slice_start = total_start
            while total_count > 0:
                limit = slice_count if total_count > 500 else total_count
                data.extend(function(slice_start, limit))
                total_count -= limit
                slice_start += (limit * timeframe_to_second(frame) * 1000)
            return data
        return slice_func
    return decorator

class BinanceExchange(ExchangeAPI):

    def __init__(self, test_mode: bool = False):
        binance = ccxt.binance(get_binance_config())
        self.binance = retry_patch(binance)
        self.test_mode = test_mode

    def fetch_ticker(self, symbol: str) -> TradeTicker:
        res = self.binance.fetch_ticker(symbol)
        return TradeTicker(last=res['last'])

    def _get_long_short_info_factory(self, api: str, symbol: str, frame: CryptoHistoryFrame, start: datetime, end: datetime = datetime.now()) -> List[LongShortAccountInfo]:
        start_in_ts = dt_to_ts(start)
        total = time_length_in_frame(start, end, frame)

        def datetime_mapper(x: dict):
            x['timestamp'] = ts_to_dt(int(x['timestamp']))
            return x
        
        @with_slice(500, frame)
        def sliced_fetch(start: int, limit: int):
            biance_api_func = getattr(self.binance, api)
            return biance_api_func({
                "symbol": symbol.replace("/", ""),
                "period": frame,
                "limit": limit,
                "startTime": start
            })
        
        return map_by(sliced_fetch(start_in_ts, total), datetime_mapper)
    # https://developers.binance.com/docs/zh-CN/derivatives/usds-margined-futures/market-data/rest-api/Top-Trader-Long-Short-Ratio
    def get_u_base_top_long_short_ratio(self, symbol: str, frame: CryptoHistoryFrame, start: datetime, end: datetime = datetime.now()) -> List[LongShortAccountInfo]:
        return self._get_long_short_info_factory('fapidataGetToplongshortpositionratio', symbol, frame, start, end)
    # https://developers.binance.com/docs/zh-CN/derivatives/usds-margined-futures/market-data/rest-api/Top-Long-Short-Account-Ratio
    def get_u_base_top_long_short_account_ratio(self, symbol: str, frame: CryptoHistoryFrame, start: datetime, end: datetime = datetime.now()) -> List[LongShortAccountInfo]:
        return self._get_long_short_info_factory('fapidataGetToplongshortaccountratio', symbol, frame, start, end)
    # https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Long-Short-Ratio
    def get_u_base_global_long_short_account_ratio(self, symbol: str, frame: CryptoHistoryFrame, start: datetime, end: datetime = datetime.now()) -> List[LongShortAccountInfo]:
        return self._get_long_short_info_factory('fapidataGetGloballongshortaccountratio', symbol, frame, start, end)
    
    def get_latest_futures_price_info(self, symbol: str) -> LatestFuturesPriceInfo:
        rsp = self.binance.fapipublicGetPremiumindex({
            "symbol": symbol.replace("/", "")
        })
        rsp['lastFundingRate'] = float(rsp['lastFundingRate'])
    
        return rsp
    def create_order(self, symbol: str, type: OrderType, side: OrderSide, amount: float, price: float = None) -> CryptoOrder: 
        logger.debug(f'binance createorder: {type} {side} amount: {amount}, price: {price}')
        res = self.binance.create_order(symbol, type, side, amount, price)
        logger.debug('Binance create_order result: ')
        logger.debug(res)
        return CryptoOrder(
            context = res['info'],
            exchange = 'binance',
            id = res['id'],
            timestamp = datetime.fromtimestamp(res['timestamp'] / 1000),
            symbol = res['symbol'],
            type = res['type'],
            side = res['side'],
            price = res['price'],
            _amount= res['amount'],
            _cost = res['cost'],
            fees = list(map(lambda fee: Fee(fee['currency'], fee['cost'], fee.get('rate')), res['fees']))
        )
    
    def fetch_ohlcv(self, symbol: str, frame: CryptoHistoryFrame, start: datetime, end: datetime = datetime.now()) -> CryptoOhlcvHistory:
        start_in_ts = dt_to_ts(start)
        total = time_length_in_frame(start, end, frame)

        @with_slice(500, frame)
        def sliced_fetch(start: int, limit: int):
            return self.binance.fetch_ohlcv(symbol, frame, since=start, limit=limit)
    
        return CryptoOhlcvHistory(
            symbol = symbol,
            frame = frame,
            exchange = 'binance',
            data = map_by(
                sliced_fetch(start_in_ts, total),
                lambda item: Ohlcv(
                    timestamp = datetime.fromtimestamp(item[0] / 1000), 
                    open = item[1], 
                    high = item[2], 
                    low = item[3], 
                    close = item[4], 
                    volume = item[5]
                )
            )
        )
        