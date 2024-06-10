import sys
from datetime import datetime, timedelta
from lib.history import OhlcvHistory
from lib.utils.ohlcv_helper import * 
from lib.utils.logger import logger
from lib.notification import send_push

message = []
def log_info(msg: str):
    message.append(msg)
    logger.info(msg)

if __name__ == '__main__':
    interval = sys.argv[1] if len(sys.argv) == 2 else '15m'
    interesting = ['DOGE/USDT', 'TRB/USDT', 'TRU/USDT']

    data_count = 36
    for pair in interesting:
        history = OhlcvHistory(pair, interval)
        data = history.range_query(datetime.now() - timedelta(minutes=15 * data_count), datetime.now())
        assert len(data) == data_count
        macd = macd_info(data)
        boll = boll_info(data)
        if macd['dead_cross_idxs'] and macd['dead_cross_idxs'][-1] == data_count - 1:
            log_info(f"{pair} {interval} 死叉出现")
        if macd['gold_cross_idxs'] and macd['gold_cross_idxs'][-1] == data_count - 1:
            log_info(f"{pair} {interval} 金叉出现")
        if macd['turn_good_idxs'] and macd['turn_good_idxs'][-1] == data_count - 1:
            log_info(f"{pair} {interval} 趋势变好")
        if macd['turn_bad_idxs'] and macd['turn_bad_idxs'][-1] == data_count - 1:
            log_info(f"{pair} {interval} 趋势变坏")
        if boll['band_open_idxs'] and boll['band_open_idxs'][-1] == data_count - 1:
            log_info(f"{pair} {interval} 布林线扩张")
            if boll['increase_over_band_idxs'] and boll['increase_over_band_idxs'][-1] == data_count - 1:
                log_info(f"涨破布林线")
            if boll['decrease_over_band_idxs'] and boll['decrease_over_band_idxs'][-1] == data_count - 1:
                log_info(f"跌破布林线")
        if boll['band_close_idxs'] and boll['band_close_idxs'][-1] == data_count - 1:
            log_info(f"{pair} {interval} 布林线收缩")
        if boll['turn_good_idxs'] and boll['turn_good_idxs'][-1] == data_count - 1:
            log_info(f'{pair} {interval}涨破布林线均线')
        if boll['turn_bad_idxs'] and boll['turn_bad_idxs'][-1] == data_count - 1:
            log_info(f'{pair} {interval}跌破布林线均线')
    
    if message:
        send_push({
            'title': f'行情通知 - {interval}',
            'content': '\n'.join(message)
        })


