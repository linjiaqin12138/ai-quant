import datetime
import json
import os
import time
from typing import Literal, Optional, TypeAlias, TypeVar

import ccxt
import requests

from ..utils.logger import logger
from .session import get_session
from .tables import Trade_Action_Info

G = TypeVar("G")
TradeContext: TypeAlias = Optional[dict | list]
exchange = ccxt.binance(
    {
        "apiKey": os.environ.get("BINANCE_API_KEY"),
        "secret": os.environ.get("BINANCE_SECRET_KEY"),
    }
)

proxy = os.environ.get("PROXY")
if proxy:
    logger.info(f"Enable proxy: {proxy}")
    # Must set https proxy when using http proxy
    # otherwise using socks proxy, but i havn't success :(
    exchange.httpsProxy = proxy
    exchange.wsProxy = proxy

MAX_RETRY_TIME = 5


def with_retry(function: G) -> G:
    def function_with_retry(*args, **kwargs):
        count = 0
        while True:
            try:
                return function(*args, **kwargs)
            except (ccxt.errors.NetworkError, ccxt.errors.RequestTimeout) as e:
                count += 1
                logger.warn(f"Retry {function} {count} times")
                time.sleep(2 ** (count - 1))
                if count > MAX_RETRY_TIME:
                    raise e

    return function_with_retry


def add_trade_info(
    pair: str,
    action: Literal["sell", "buy"],
    reason: Optional[str],
    context: TradeContext,
    price: float,
    amount: float,
    type: Literal["limit", "market"],
):
    sess = get_session()
    raw_context = None if context is None else json.dumps(context)
    sess.add(
        Trade_Action_Info(
            **{
                "pair": pair,
                "timestamp": datetime.datetime.now(),
                "action": action,
                "reason": reason,
                "context": raw_context,
                "amount": amount,
                "price": price,
                "type": type,
                "order_id": context["id"] if context is not None else None,
            }
        )
    )
    sess.commit()


def delete_trade_info(order_id: str):
    sess = get_session()
    sess.query(Trade_Action_Info).filter(
        Trade_Action_Info.order_id == order_id
    ).delete()
    sess.commit()


create_market_buy_order = with_retry(exchange.create_market_buy_order)
create_market_sell_order = with_retry(exchange.create_market_sell_order)
create_order = with_retry(exchange.create_order)
_cancel_order = with_retry(exchange.cancel_order)
fetch_order = with_retry(exchange.fetch_order)
fetch_ohlcv = with_retry(exchange.fetch_ohlcv)
fetch_balance = with_retry(exchange.fetch_balance)
fetch_order_book = with_retry(exchange.fetch_order_book)
fetch_ticker = with_retry(exchange.fetch_ticker)
load_markets = with_retry(exchange.load_markets)


def get_remain_money(coin_type: str = "USDT"):
    balance = fetch_balance()
    return balance[coin_type]["free"]


def sell_at_market_price(
    pair: str, amount: Optional[float] = None, reason: Optional[str] = None
):
    all_amount = get_remain_money(pair.split("/")[0]) if amount is None else amount

    res = create_market_sell_order(pair, all_amount)
    logger.info(f"Sell {pair} at market price, amount {all_amount} for reason {reason}")

    add_trade_info(pair, "sell", reason, res, res["average"], res["amount"], "market")
    return res


def buy_at_market_price(
    pair: str,
    amount: Optional[float] = None,
    spend: Optional[float] = None,
    reason: Optional[str] = None,
):
    if amount is None and spend is None:
        raise Exception(
            "PARAMETER_ERROR", "amount or spend should be provided at least one"
        )

    res = None
    if amount is not None:
        res = create_market_buy_order(symbol=pair, amount=amount)
        logger.info(
            f"Buy {pair} at market price with amount {amount} for reason {reason}"
        )
    else:
        order_book = fetch_order_book(symbol=pair)
        best_ask = order_book["asks"][0]  # 最优卖单价格
        amount_to_buy = spend / best_ask[0]
        res = create_market_buy_order(symbol=pair, amount=amount_to_buy)
        logger.info(
            f"Buy {pair} at market price with amount {amount_to_buy} for reason {reason}"
        )

    add_trade_info(pair, "buy", reason, res, res["average"], res["amount"], "market")

    return res


def sell_at_price(
    pair: str,
    price: float,
    amount: Optional[float] = None,
    reason: Optional[str] = None,
):
    all_amount = get_remain_money(pair.split("/")[0]) if amount is None else amount

    res = create_order(pair, "limit", "sell", all_amount, price)
    logger.info(
        f"Sell {pair} at price {price}, amount {all_amount} for reason: {reason}"
    )

    # {'info': {'symbol': 'PONDUSDT', 'orderId': '265354410', 'orderListId': '-1', 'clientOrderId': 'x-R4BD3S82b8452589422d0047060060', 'transactTime': '1714738351794', 'price': '0.02401000', 'origQty': '1002.29000000', 'executedQty': '0.00000000', 'cummulativeQuoteQty': '0.00000000', 'status': 'NEW', 'timeInForce': 'GTC', 'type': 'LIMIT', 'side': 'SELL', 'workingTime': '1714738351794', 'fills': [], 'selfTradePreventionMode': 'EXPIRE_MAKER'}, 'id': '265354410', 'clientOrderId': 'x-R4BD3S82b8452589422d0047060060', 'timestamp': 1714738351794, 'datetime': '2024-05-03T12:12:31.794Z', 'lastTradeTimestamp': None, 'lastUpdateTimestamp': 1714738351794, 'symbol': 'POND/USDT', 'type': 'limit', 'timeInForce': 'GTC', 'postOnly': False, 'reduceOnly': None, 'side': 'sell', 'price': 0.02401, 'triggerPrice': None, 'amount': 1002.29, 'cost': 0.0, 'average': None, 'filled': 0.0, 'remaining': 1002.29, 'status': 'open', 'fee': None, 'trades': [], 'fees': [], 'stopPrice': None, 'takeProfitPrice': None, 'stopLossPrice': None}

    add_trade_info(pair, "sell", reason, res, price, amount, "limit")

    return res


def buy_at_price(
    pair: str, price: float, spend: Optional[float] = None, reason: Optional[str] = None
):
    spend = get_remain_money("USDT") if spend is None else spend
    amount = spend / price

    res = create_order(pair, "limit", "buy", amount, price)
    logger.info(f"Buy {pair} at price {price}, amount {amount} for reason: {reason}")

    add_trade_info(pair, "buy", reason, res, price, amount, "limit")


def cancel_order(pair: str, order_id: str):
    _cancel_order(order_id, pair)
    delete_trade_info(order_id)


def buy(pair: str, spent_usdt: float):
    order_book = fetch_order_book(symbol=pair)
    best_ask = order_book["asks"][0]  # 最优卖单价格

    balance = fetch_balance()
    logger.info(f'USDT free balance: {balance["USDT"]["free"]}')
    if balance["USDT"]["free"] < 1:
        logger.warn("USDT account less than 1, abort buying")
        return {"error": "NO_MONEY_TO_BUY"}

    if balance["USDT"]["free"] < spent_usdt:
        logger.warn("USDT account is not enough, will use all as possible")
        spent_usdt = balance["USDT"]["free"]

    amount_to_buy = spent_usdt / best_ask[0]
    logger.info(
        f"Try spending {spent_usdt} USDT to buy {amount_to_buy} {pair} with price: {best_ask[0]}"
    )

    result = create_market_buy_order(symbol=pair, amount=amount_to_buy)

    logger.info(f'Result: Spend {result["cost"]}')

    return {"result": result}

def long_short_ratio_info(pair: str, period: str, limit: int):
    symbol = pair.replace('/', '')
    url = f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period={period}&limit={limit}"

    # 发起 GET 请求
    return requests.get(url)
    



# __all__ = ['call_with_retry']
