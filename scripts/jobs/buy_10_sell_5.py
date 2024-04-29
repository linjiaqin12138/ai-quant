import datetime
import time

from lib.dao.data_query import get_ohclv, get_all_pairs
from lib.dao.exchange import buy
from lib.utils.logger import logger
from lib.notification import send_push
from lib.utils.time import unify_dt


all_pairs = list(filter(lambda pair: pair.endswith('USDT') and pair != 'NBTUSDT', get_all_pairs()))

interval_min = 10 

try:
    while True:
        curr_time = unify_dt(datetime.datetime.now(), interval_min * 60)
        messages_10 = []
        messages_5 = []
        buy_message = []

        for pair in all_pairs:
            df = get_ohclv(pair, '1m', limit=interval_min + 1)
            
            # for i in range(len(df)):
            max_high = max(df['high'])
            high_idx = 0
            for i in range(len(df)):
                if df['high'].iloc[i] == max_high:
                    high_idx = i
                    break
        
            data_after_high = df[high_idx:]
            min_low = min(data_after_high['low'])
            min_idx = 0
            for i in range(len(data_after_high)):
                if data_after_high['low'].iloc[i] == min_low:
                    min_idx = i
        
            decline_rate = (max_high - min_low) / max_high * 100
        
            if decline_rate > 10:
                messages_10.append(f'{pair} decline over 10% in {interval_min}min: {round(decline_rate, 2)}%')
                # buy_result = buy(pair, 50)
                # if 'error' not in buy_result:
                #     buy_message.append(f'Buy {pair}')
            elif decline_rate > 5:
                messages_5.append(f'{pair} decline over 5% in {interval_min}min: {round(decline_rate, 2)}%')
        
        logger.info('Finished this checking loop')

        if len(messages_10) + len(messages_5) > 0:
            message = '\n'.join(messages_10 + messages_5)
            logger.info(f'Send push message: {message}')
            result = send_push({ 'content': message, 'title': f'过去{interval_min}分钟行情' })
            if not result['success']:
                logger.warn('Send push failed')

        while unify_dt(datetime.datetime.now(), interval_min * 60) == curr_time:
            time.sleep(1)

        logger.info('Start next check loop')
except Exception as e:
    logger.error('Unexpeted error: ', e)
    send_push({ 'content': str(e), 'title': '发生未知错误，脚本退出' })
