import pandas as pd

from lib.dao.data_query import get_ohclv, get_all_pairs
from lib.utils.logger import logger
from lib.notification import send_push

interval_min = 10 

try:
    all_pairs = list(filter(lambda pair: pair.endswith('USDT'), get_all_pairs()))
    messages_10 = []
    messages_5 = []
    decline_rates = []

    for pair in all_pairs:
        df = get_ohclv(pair, '1m', limit=interval_min + 1)
        
        max_high = max(df['high'])
        high_idx = 0
        for i in range(len(df)):
            if df['high'].iloc[i] == max_high:
                high_idx = i
                break
    
        # data_after_high = df[high_idx:]
        # min_low = min(data_after_high['low'])
        # min_idx = 0
        # for i in range(len(data_after_high)):
        #     if data_after_high['low'].iloc[i] == min_low:
        #         min_idx = i
            
        low = df['low'].iloc[-1]
    
        decline_rate = (max_high - low) / max_high * 100
        decline_rates.append([pair, decline_rate])
    
        if decline_rate > 10:
            messages_10.append(f'{pair} decline over 10% in {interval_min}min: {round(decline_rate, 2)}%')
        elif decline_rate > 5:
            messages_5.append(f'{pair} decline over 5% in {interval_min}min: {round(decline_rate, 2)}%')

    df = pd.DataFrame(decline_rates, columns = ['pair', 'decline_rate'])
    df.sort_values(by='decline_rate', ascending=False, inplace=True)
    print('过去10分钟跌幅前3的交易对: ')
    print(df.head(3))

    if len(messages_10) + len(messages_5) > 0:
        message = '\n'.join(messages_10 + messages_5)
        logger.info(f'Send push message: {message}')
        result = send_push({ 'content': message, 'title': f'过去{interval_min}分钟行情' })
        if not result['success']:
            logger.warn('Send push failed')
            exit(1)
    
    logger.info('Finish minotoring')
except Exception as e:
    logger.error('Unexpeted error: ', e)
    send_push({ 'content': str(e), 'title': '发生未知错误，脚本退出' })
    exit(1)
