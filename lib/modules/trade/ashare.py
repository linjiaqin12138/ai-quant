from datetime import datetime

from lib.adapter.database import create_transaction
from lib.adapter.exchange.cn_market_exchange import AshareExchange
from lib.model.cn_market import AShareOrder
from lib.model.common import OhlcvHistory, Order, OrderSide, OrderType
from lib.modules.apis_proxy import is_china_business_day
from lib.logger import logger
from lib.utils.string import random_id
from lib.utils.time import time_ago_from
from .api import TradeOperations

class AshareTrade(TradeOperations):

    def __init__(self):
        self.exchange = AshareExchange()
        self.db = create_transaction()

    def is_business_day(self, day: datetime) -> bool:
        return is_china_business_day(day)
        
    def get_current_price(self, symbol: str) -> float:
        return super().get_current_price(symbol)
    
    def get_ohlcv_history(
            self, 
            symbol: str, 
            frame: str, 
            start: datetime = None, 
            end: datetime = datetime.now(), 
            limit: int = None
        ) -> OhlcvHistory:
        logger.debug(f'get_ohlcv_history with {symbol=}, {frame=}, {limit=}, {start=}, {end=}')
        if not limit and not start:
            raise ValueError("Invalid parameters: 'start' must be provided when 'limit' is not set.")
        if start and not end:
            end = datetime.now()
        if limit:
            end = datetime.now()
            start = end
            while limit > 0:
                start = time_ago_from(1, frame, start)
                if self.is_business_day(start):
                    limit -= 1
            return self.exchange.fetch_ohlcv(symbol, frame, start, end)     
        return self.exchange.fetch_ohlcv(symbol, frame, start, end)
    
    def create_order(
            self, 
            symbol: str, 
            type: OrderType, 
            side: OrderSide,
            reason: str, 
            amount: float = None,
            price: float = None, 
            spent: float = None, 
            comment: str = None
        ) -> Order:
        return AShareOrder(
            id=random_id(10),
            timestamp=datetime.now(),
            symbol=symbol,
            type=type,
            side=side,
            price=price,
            _amount=amount,
            _cost = price * amount,
            fees=[]
        )
    
__all__ = [
    'AshareTrade'
]