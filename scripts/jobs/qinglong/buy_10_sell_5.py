import traceback
import datetime
from typing import TypedDict, Dict, List

import pandas as pd

from lib.dao.data_query import get_ohclv, get_all_pairs
from lib.dao.event import get_event, set_event
from lib.dao.exchange import buy_at_market_price, get_remain_money, sell_at_price, fetch_order, fetch_ticker
from lib.utils.logger import logger
from lib.notification import send_push
from lib.utils.time import curr_ts

interval_min = 10
EVENT_KEY = ACTION_REASON = 'BUY_10_SELL_5'
# Key is order_id
OrderContext = TypedDict('OrderContext', {
    'buy_price': float
})
BuyTenSellFiveEventContext = Dict[str, Dict[str, OrderContext]]
GlobalContext = TypedDict('GlobalContext', { 
    'remain': float, 
    'events': BuyTenSellFiveEventContext,
    'importantMessage': List[str]
})
# get_event(EVENT_KEY)


GLOBAL_CONTEXT: GlobalContext = {
    'remain': 0,
    'events': {},
    'importantMessage': [],
    'data': pd.DataFrame
}

def is_eight_clock():
    now = datetime.datetime.now()
    return now.hour == 8 and now.minute < 10

def report():
    if len(GLOBAL_CONTEXT['importantMessage']) > 0:
        message = '\n'.join(GLOBAL_CONTEXT['importantMessage'])
        logger.info(f'Send push message: {message}')
        result = send_push({ 'content': message, 'title': f'过去{interval_min}分钟行情' })
        if not result['success']:
            logger.warn('Send push failed')
    else:
        logger.info('No important message need to be reported')

def log_info(msg: str):
    GLOBAL_CONTEXT['importantMessage'].append(msg)
    logger.info(msg)

def add_order(events: BuyTenSellFiveEventContext, symbol: str, id: str, context: OrderContext):
    if events.get(symbol) is None:
        events[symbol] = {}
    events[symbol][id] = context

def action_decline_over(pair: str, decline_rate: float, spend: float):
    log_info(f'{pair} decline over {decline_rate}% in {interval_min}min: {round(decline_rate, 2)}%')
    result = buy_at_market_price(pair, reason=ACTION_REASON, spend=spend if GLOBAL_CONTEXT['remain'] >= 20 else GLOBAL_CONTEXT['remain'])
    price = result['average']
    amount = result['amount']
    cost = result['cost']

    GLOBAL_CONTEXT['remain'] -= cost

    to_sell_at_price = price * (decline_rate / 2) / 100 + price
    to_gain= cost * (decline_rate / 2) / 100
    log_info(f'buy {pair} with USDT {cost} and try to sell when price up from {result["average"]} to {to_sell_at_price}, gain money {to_gain} with rate {decline_rate / 2}')
    
    res = sell_at_price(pair, to_sell_at_price, amount, ACTION_REASON)
    add_order(GLOBAL_CONTEXT['events'], pair, res['id'], { 'buy_price': price })

def monitor_orders():
    GLOBAL_CONTEXT['events'] = get_event(EVENT_KEY) or {}
    if GLOBAL_CONTEXT['events']:
        # To Fix dictionary changed size during iteration
        pairs = list(GLOBAL_CONTEXT['events'].keys())
        for pair in pairs:
            # To Fix dictionary changed size during iteration
            order_ids = list((GLOBAL_CONTEXT['events'][pair] or {}).keys())
            orders = GLOBAL_CONTEXT['events'][pair]
            for order_id in order_ids:
                order_info = fetch_order(order_id, pair)
                if order_info['status'] != 'open':
                    log_info(f'{pair} 的在价格为{orders[order_id]["buy_price"]}买入，{order_info["average"]}卖出的单已经被卖出')
                    del orders[order_id]
                    # orders[order_id] = None # Will store null into json
                elif (curr_ts() - order_info['timestamp'] / 1000) / 84600 > 3 and is_eight_clock():
                    past_days = int((curr_ts() - order_info['timestamp'] / 1000) / 84600)
                    ticker = fetch_ticker(pair)
                    curr_price = ticker['last']
                    rate = (curr_price - orders[order_id]["buy_price"]) / orders[order_id]["buy_price"] * 100
                    log_info(f'{pair} 的在价格为{orders[order_id]["buy_price"]}买入，{order_info["price"]}卖出的单已经超过{past_days}天没有卖出, 现在卖出将{"盈利" if rate > 0 else "亏损"}{abs(round(rate, 4))}%, 当前价格为{curr_price}')
            if not orders:
                del GLOBAL_CONTEXT['events'][pair]
        set_event(EVENT_KEY, GLOBAL_CONTEXT["events"])

# def run_with_interval(interval_in_min: int):

def main():
    try:
        # 监控买入的订单状态
        monitor_orders()

        GLOBAL_CONTEXT['remain'] = get_remain_money()
        if GLOBAL_CONTEXT['remain']  < 10:
            logger.info(f'钱太少，只有{GLOBAL_CONTEXT["remain"] }, 溜了溜了，不买了')
            report()
            return 0

        all_pairs = list(filter(lambda pair: pair.endswith('USDT'), get_all_pairs()))
        decline_rates = []
        for pair in all_pairs:
            if GLOBAL_CONTEXT['remain'] < 10:
                # 余钱不够，不继续扫描
                continue

            df = get_ohclv(pair, '1m', limit=interval_min + 1)
            
            max_high = max(max(df['open']), max(df['close']))
            low = df['close'].iloc[-1]
        
            decline_rate = (max_high - low) / max_high * 100 if max_high > low else 0
            decline_rates.append([pair, decline_rate])
        
            if decline_rate > 10:
                action_decline_over(pair, 10, 20)
            elif decline_rate > 5:
                action_decline_over(pair, 5, 20)
        
        set_event(EVENT_KEY, GLOBAL_CONTEXT['events'])

        df = pd.DataFrame(decline_rates, columns = ['pair', 'decline_rate'])
        df.sort_values(by='decline_rate', ascending=False, inplace=True)
        print(f'过去{interval_min}分钟跌幅前3的交易对: ')
        print(df.head(3))

        report()
        
        logger.info('Finish minotoring')
    except Exception as e:
        logger.error('Unexpeted error: ', e)
        send_push({
            'content': traceback.format_exc(chain=False),
            'title': '发生未知错误，脚本退出'
        })
        return 1

main()