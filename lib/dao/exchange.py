import os
import time
from typing import Callable, Any, TypeVar

import ccxt

from ..utils.logger import logger

G = TypeVar('G')
exchange = ccxt.binance({
  'apiKey': os.environ.get('BINANCE_API_KEY'),
  'secret': os.environ.get('BINANCE_SECRET_KEY')
})

proxy = os.environ.get('PROXY')
if proxy:
    logger.info(f'Enable proxy: {proxy}')
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
            except ccxt.errors.RequestTimeout as e:
                count += 1
                logger.warn(f'Retry {function} {count} times')
                time.sleep(2 ** (count - 1))
                if count > MAX_RETRY_TIME:
                    raise e
    return function_with_retry

fetch_balance = with_retry(exchange.fetch_balance)
create_market_buy_order = with_retry(exchange.create_market_buy_order)
fetch_ohlcv = with_retry(exchange.fetch_ohlcv)
load_markets = with_retry(exchange.load_markets)
fetch_order_book = with_retry(exchange.fetch_order_book)
fetch_ticker = with_retry(exchange.fetch_ticker)
create_order = with_retry(exchange.create_order)

def sell_all_at_price(pair: str, amount: float, price: float):
    return create_order(pair, 'limit', 'sell', amount, price)

def buy(pair: str, spent_usdt: float):
    order_book = fetch_order_book(symbol=pair)
    best_ask = order_book['asks'][0]  # 最优卖单价格

    balance = fetch_balance()
    logger.info(f'USDT free balance: {balance["USDT"]["free"]}')
    if balance['USDT']['free'] < 1:
        logger.warn('USDT account less than 1, abort buying')
        return { 'error': 'NO_MONEY_TO_BUY' }

    if balance['USDT']['free'] < spent_usdt:
        logger.warn('USDT account is not enough, will use all as possible')
        spent_usdt = balance['USDT']['free']

    amount_to_buy = spent_usdt / best_ask[0]
    logger.info(f'Try spending {spent_usdt} USDT to buy {amount_to_buy} {pair} with price: {best_ask[0]}')

    result = create_market_buy_order(symbol=pair, amount=amount_to_buy)

    logger.info(f'Result: Spend {result["cost"]}')

    return { 'result': result }
      
# __all__ = ['call_with_retry']