from datetime import datetime
from typing import List, Tuple
from lib.adapter.database import create_transaction, DbTransaction
from lib.adapter.exchange.cn_market_exchange import AshareExchange
from lib.model.cn_market import AShareOrder
from lib.model.common import Ohlcv, Order, OhlcvHistory, OrderSide, OrderType
from lib.modules.apis_proxy import is_china_business_day
from lib.logger import logger
from lib.utils.string import random_id
from lib.utils.time import round_datetime_in_period, time_ago_from
from lib.tools.cache_decorator import use_cache
from lib.tools.range_cache import use_range_cache
from .api import TradeOperations


def get_ohlcv_time_range(ohlcv: OhlcvHistory) -> Tuple[datetime, datetime]:
    """
    Get the time range of the OHLCV data.
    """
    if not ohlcv.data:
        return (datetime.max, datetime.min)
    if len(ohlcv.data) == 1:
        return ohlcv.data[0].timestamp, ohlcv.data[0].timestamp
    return ohlcv.data[0].timestamp, ohlcv.data[-1].timestamp


class AshareTrade(TradeOperations):

    def __init__(self):
        self.exchange = AshareExchange()
        self.db = create_transaction()

    def is_business_day(self, day: datetime) -> bool:
        return is_china_business_day(day)

    def is_business_time(self, time: datetime) -> bool:
        if not self.is_business_day(time):
            return False
        
        # 判断time是否有时区，如果有时区，转换到东八区
        if time.tzinfo is not None:
            time = time.astimezone(datetime.timezone(datetime.timedelta(hours=8)))

        # 判断time是否在东八区时间的9:30到15:00之间
        start_time = time.replace(hour=9, minute=30, second=0, microsecond=0)
        end_time = time.replace(hour=15, minute=0, second=0, microsecond=0)
        if start_time <= time <= end_time:
            return True
        return False
        
    @use_cache(5, use_db_cache=True, serializer=str, deserializer=float)
    def get_current_price(self, symbol: str) -> float:
        return self.exchange.fetch_ticker(symbol).last

    def get_ohlcv_history(
        self,
        symbol: str,
        frame: str,
        start: datetime = None,
        end: datetime = datetime.now(),
        limit: int = None,
    ) -> OhlcvHistory:
        logger.debug(
            f"get_ohlcv_history with {symbol=}, {frame=}, {limit=}, {start=}, {end=}"
        )

        def store_ohlcv_in_cache(db: DbTransaction, data: List[Ohlcv]) -> None:
            db.ohlcv_cache.add(OhlcvHistory(symbol=symbol, frame=frame, data=data))

        def get_ohlcv_by_cache(
            db: DbTransaction, start: datetime, end: datetime
        ) -> List[Ohlcv]:
            return db.ohlcv_cache.range_query(symbol, frame, start, end).data

        @use_range_cache(
            get_data_by_cache=get_ohlcv_by_cache,
            store_data=store_ohlcv_in_cache,
            key_param_names=["symbol", "frame"],
            metadata_key_suffix="::ashare_ohlcv_cache::metadata",
            lock_key_suffix="::ashare_ohlcv_cache::lock",
        )
        def get_ohlcv_by_time_range(
            symbol: str, frame: str, start: datetime, end: datetime
        ) -> List[Ohlcv]:
            return self.exchange.fetch_ohlcv(symbol, frame, start, end).data

        if not limit and not start:
            raise ValueError(
                "Invalid parameters: 'start' must be provided when 'limit' is not set."
            )
        if start and not end:
            end = datetime.now()
        data: List[Ohlcv] = None
        if limit:
            # workaround for limit 50 but query 49
            limit += 1 
            end = datetime.now()
            start = end
            while limit > 0:
                start = time_ago_from(1, frame, start)
                if self.is_business_day(start):
                    limit -= 1
        nomolized_start = round_datetime_in_period(start, frame)
        nomolized_end = round_datetime_in_period(end, frame)
        if nomolized_start == nomolized_end:
            return []

        data = get_ohlcv_by_time_range(symbol, frame, nomolized_start, nomolized_end)
        return OhlcvHistory(symbol=symbol, frame=frame, data=data)

    def create_order(
        self,
        symbol: str,
        type: OrderType,
        side: OrderSide,
        *,
        tags: str,
        amount: float = None,
        price: float = None,
        spent: float = None,
        comment: str = None,
    ) -> Order:
        return AShareOrder(
            id=random_id(10),
            timestamp=datetime.now(),
            symbol=symbol,
            type=type,
            side=side,
            price=price,
            _amount=(
                amount if side == "sell" else spent / self.get_current_price(symbol)
            ),
            _cost=self.get_current_price(symbol) * amount if side == "sell" else spent,
            fees=[],
        )


ashare = AshareTrade()

__all__ = ["AshareTrade", "ashare"]
