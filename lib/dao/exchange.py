import os
import time

import ccxt

from ..utils.logger import logger

exchange = ccxt.binance({
  'apiKey': os.environ.get('API_KEY'),
  'secret': os.environ.get('SECRET_KEY')
})

proxy = os.environ.get('PROXY')
if proxy:
    logger.info(f'Enable proxy: {proxy}')
    # Must set https proxy when using http proxy
    # otherwise using socks proxy, but i havn't success :(
    exchange.httpsProxy = proxy
    exchange.wsProxy = proxy

MAX_RETRY_TIME = 5
def call_with_retry(function, **args):
    count = 0
    while True:
        try: 
            return getattr(exchange, function)(**args)
        except ccxt.errors.RequestTimeout as e:
            count += 1
            logger.warn(f'Retry {function} {count} times')
            time.sleep(2 ** (count - 1))
            if count > MAX_RETRY_TIME:
                raise e

def with_retry(function: str): 
    count = 0
    while True:
        try: 
            return getattr(exchange, function)
        except ccxt.errors.RequestTimeout as e:
            count += 1
            logger.warn(f'Retry {function} {count} times')
            time.sleep(2 ** (count - 1))
            if count > MAX_RETRY_TIME:
                raise e

fetch_balance = with_retry('fetch_balance')
create_market_buy_order = with_retry('create_market_buy_order')
fetch_ohlcv = with_retry('fetch_ohlcv')
load_markets = with_retry('load_markets')
fetch_order_book = with_retry('fetch_order_book')
create_order = with_retry('create_order')

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