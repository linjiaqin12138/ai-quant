from datetime import datetime, timedelta
from typing import List

from lib.adapter.database import create_transaction
from lib.adapter.exchange import ExchangeAPI, BinanceExchange
from lib.adapter.lock import with_lock
from lib.model import (
    OrderSide,
    OrderType,
    CryptoHistoryFrame,
    CryptoOhlcvHistory,
    CryptoOrder,
)
from lib.utils.time import (
    round_datetime_in_period,
    time_ago_from,
    time_length_in_frame,
    timeframe_to_second,
)
from lib.logger import logger

from .api import TradeOperations


def get_missed_time_ranges(
    timerange: List[datetime], start: datetime, end: datetime, frame: CryptoHistoryFrame
) -> List[List[datetime]]:
    """
    Find missing time intervals between a given timerange and specified start/end dates.
    This function identifies and returns the time ranges that are missing from the provided
    timerange list, within the specified start and end times for a given timeframe.
    Parameters:
        timerange (List[datetime]): A list of datetime objects representing available time points.
        start (datetime): The starting datetime for the desired range.
        end (datetime): The ending datetime for the desired range.
        frame (CryptoHistoryFrame): The timeframe enum specifying the interval between data points.
    Returns:
        List[List[datetime]]: A list of missing time ranges, where each range is represented
                             as a list of two datetime objects [range_start, range_end].
    Example:
        If timerange is [dt1, dt2, dt5, dt6] and we want all points between start=dt0 and end=dt8
        with 1-hour intervals, the function will return [[dt0, dt1], [dt3, dt5], [dt7, dt8]].
    """
    result = []
    interval = timeframe_to_second(frame)
    rounded_start = round_datetime_in_period(start, frame)
    rounded_end = round_datetime_in_period(end, frame)

    if rounded_start < timerange[0]:
        result.append([rounded_start, timerange[0]])

    while len(timerange) > 0:
        while len(timerange) > 1 and (
            timerange[0] + timedelta(seconds=interval) == timerange[1]
        ):
            timerange.pop(0)
        if len(timerange) > 1:
            result.append([timerange[0] + timedelta(seconds=interval), timerange[1]])
        elif timerange[0] + timedelta(seconds=interval) < rounded_end:
            result.append([timerange[0] + timedelta(seconds=interval), rounded_end])
        timerange.pop(0)

    return result


class CryptoTrade(TradeOperations):
    def __init__(self, exchange: ExchangeAPI = BinanceExchange()):
        self.exchange = exchange

    def is_business_day(self, _: datetime) -> bool:
        return True
    
    def is_business_time(self, time: datetime) -> bool:
        return True

    def get_current_price(self, symbol: str) -> float:
        return self.exchange.fetch_ticker(symbol).last

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
    ) -> CryptoOrder:
        logger.debug(
            f"createorder: {type} {side} {tags} amount: {amount}, price: {price}, spent: {spent}, comment: {comment}"
        )
        with create_transaction() as db:
            order = None
            if type == "limit" and amount and price:
                order = self.exchange.create_order(symbol, type, side, amount, price)
            elif type == "market" and amount:
                order = self.exchange.create_order(symbol, type, side, amount)
            elif type == "market" and spent:
                if side == "buy":
                    amount = spent / self.get_current_price(symbol)
                else:
                    amount = spent
                order = self.exchange.create_order(symbol, type, side, amount)
            else:
                raise Exception(
                    f"Unsupported parameters value: {type}, {side}, {amount}, {price}, {spent}"
                )
            db.trade_log.add(order, tags, comment)
            db.commit()
            return order

    def get_ohlcv_history(
        self,
        symbol: str,
        frame: CryptoHistoryFrame,
        start: datetime = None,
        end: datetime = datetime.now(),
        limit: int = None,
    ) -> CryptoOhlcvHistory:
        logger.debug(
            f"get_ohlcv_history with {symbol=}, {frame=}, {limit=}, {start=}, {end=}"
        )
        if not limit and not start:
            raise ValueError(
                "Invalid parameters: 'start' must be provided when 'limit' is not set."
            )

        expected_data_length = (
            limit if limit else time_length_in_frame(start, end, frame)
        )
        nomolized_start = (
            round_datetime_in_period(time_ago_from(limit, frame), frame)
            if limit
            else round_datetime_in_period(start, frame)
        )
        nomolized_end = (
            round_datetime_in_period(datetime.now(), frame)
            if limit
            else round_datetime_in_period(end, frame)
        )

        def is_cache_satisfy(cache_result: CryptoOhlcvHistory):
            if len(cache_result.data) == expected_data_length:
                logger.debug("local database found all required data, return directly.")
                return True
            return False

        def query_from_cache() -> CryptoOhlcvHistory:
            cache_result = db.ohlcv_cache.range_query(
                symbol, frame, nomolized_start, nomolized_end
            )
            logger.debug(f"Found {len(cache_result.data)} records locally")
            return cache_result

        with create_transaction() as db:
            cache_result = query_from_cache()
            if is_cache_satisfy(cache_result):
                return cache_result

        @with_lock(
            f"lock-{symbol}-{frame}-ohlcv-query",
            max_concurrent_access=1,
            expiration_time=300,
            timeout=300,
        )
        def lock_part():
            with create_transaction() as db:
                cache_result = query_from_cache()
                if is_cache_satisfy(cache_result):
                    return cache_result

                if len(cache_result.data) == 0:
                    remote_result = self.exchange.fetch_ohlcv(
                        symbol, frame, nomolized_start, nomolized_end
                    )
                    # assert expected_data_length == len(remote_result.data)
                    db.ohlcv_cache.add(remote_result)
                    db.commit()
                    return remote_result

                local_timerange = list(
                    map(lambda item: item.timestamp, cache_result.data)
                )
                result_data = cache_result.data
                miss_time_ranges = get_missed_time_ranges(
                    local_timerange, nomolized_start, nomolized_end, frame
                )
                logger.debug(f"missed_time_ranges: {miss_time_ranges}")
                for time_range in miss_time_ranges:
                    remote_data = self.exchange.fetch_ohlcv(
                        symbol, frame, time_range[0], time_range[1]
                    )
                    db.ohlcv_cache.add(remote_data)
                    result_data.extend(remote_data.data)
                db.commit()
                return CryptoOhlcvHistory(
                    symbol=symbol,
                    frame=frame,
                    # TODO Support other exchange
                    exchange="binance",
                    data=sorted(result_data, key=lambda item: item.timestamp),
                )

        return lock_part()


crypto = CryptoTrade()
__all__ = ["CryptoTrade", "crypto"]
