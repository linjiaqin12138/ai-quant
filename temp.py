import pandas as pd
import talib
import mplfinance as mpf
import datetime
from lib.utils.time import dt_to_float

from lib.dao.data_query import get_ohclv



symbol = 'OMNI/USDT'

# print(dt_to_float(datetime.datetime.now() - datetime.timedelta(hours=24 * 7 * 2)) * 1000)
# print(datetime.datetime.now() - datetime.timedelta(hours=24 * 7 * 2))
df = get_ohclv(symbol, '1h', since=int(dt_to_float(datetime.datetime.now() - datetime.timedelta(hours=24 * 7 * 2)) * 1000), limit=24 * 7)

df['macd'], df['macdSignal'], df['macdHist'] = talib.MACD(df['close'])
df['upperband'], df['middleband'], df['lowerband'] = talib.BBANDS(df['close'], timeperiod=20)
df['sar'] = talib.SAR(df['high'], df['low'], acceleration=0.02, maximum=0.2)

mpf.plot(df.set_index('timestamp'), type='candle', style='yahoo',
         title=f'{symbol} SAR Chart', ylabel='Price', ylabel_lower='MACD',
         addplot=[
             mpf.make_addplot(df['macdHist'], panel=1, color='b', secondary_y=True),
             mpf.make_addplot(df['macdHist'].where(df['macdHist'] >= 0 ), type='bar', panel=1, color='g', alpha=1, secondary_y=True),
             mpf.make_addplot(df['macdHist'].where(df['macdHist'] < 0 ), type='bar', panel=1, color='r', alpha=1, secondary_y=True),
             mpf.make_addplot(df['macdHist'].where(df['macdHist'].shift(1) < df['macdHist']), type='bar', panel=1, color='w', alpha=1, secondary_y=True),
             mpf.make_addplot(df[['upperband', 'middleband', 'lowerband']]),
             mpf.make_addplot(df['sar'], type='scatter'),
         ],
         figscale=1.5, figsize=(16, 10))