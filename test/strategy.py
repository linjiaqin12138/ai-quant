from typing import Type, TypedDict, Optional
from dataclasses import dataclass
from datetime import datetime
import numpy as np 
import mplfinance as mpf

from lib.model import OhlcvHistory
from lib.modules.notification_logger import NotificationLogger
from lib.modules.strategy import BasicContext, BasicDependency, ParamsBase, StrategyFunc
from lib.modules.exchange_proxy import  crypto
from lib.utils.ohlcv import boll_info, macd_info, sar_info, to_df

from fake_modules.fake_db import get_fake_session
from fake_modules.fake_notification import FakeNotification
from fake_modules.fake_exchange_proxy import fake_exchange

IndicatorOptions = TypedDict('IndicatorOptions', {
    'macd': bool,
    'sar': bool,
    'boll': bool
})

DrawOptions = TypedDict('DrawOptions', {
    'enabled': bool,
    'indicators': Optional[IndicatorOptions]
})

@dataclass
class StrategyTestOptions:
    batch_count: int
    from_time: datetime
    end_time: datetime
    draw: DrawOptions

def strategy_test(strategy_func: StrategyFunc, test_options: StrategyTestOptions, params: ParamsBase, contextClass: Type[BasicContext]):
    stub_deps = BasicDependency(exchange=fake_exchange, session = get_fake_session(), notification=NotificationLogger('Fake Notification', notification=FakeNotification()))

    ohlcv_datas = crypto.get_ohlcv_history(params.symbol, params.data_frame, test_options.from_time, test_options.end_time)
    df = to_df(ohlcv_datas.data)

    init_coin = params.money / ohlcv_datas.data[test_options.batch_count].close
    df['compaired_gain'] = df['close'] * init_coin
    df['strategy_gain'] = float(params.money)
    df['buy_point'] = np.nan
    df['sell_point'] = np.nan

    total_money = params.money
    total_stake = 0
    with contextClass(params, stub_deps) as context:
        for idx in range(0, len(ohlcv_datas.data)):
            if idx < test_options.batch_count:
                df.loc[ohlcv_datas.data[idx].timestamp, 'compaired_gain'] = float(params.money)
                continue
            
            fake_exchange.clear()
            fake_exchange.set_curr_time(ohlcv_datas.data[idx].timestamp)
            fake_exchange.set_curr_price(float(ohlcv_datas.data[idx].open))
            fake_exchange.set_curr_data(
                OhlcvHistory(
                    symbol=ohlcv_datas.symbol,
                    frame=ohlcv_datas.frame,
                    data=ohlcv_datas.data[idx - test_options.batch_count: idx]
                )
            )

            strategy_func(context)
    
            if fake_exchange.is_buy:
                df.loc[ohlcv_datas.data[idx].timestamp, 'buy_point'] = ohlcv_datas.data[idx].open
                total_money -= fake_exchange.get_buy_cost()
                total_stake += (fake_exchange.get_buy_cost() / float(ohlcv_datas.data[idx].open))
            if fake_exchange.is_sell:
                df.loc[ohlcv_datas.data[idx].timestamp, 'sell_point'] = ohlcv_datas.data[idx].open
                total_money += fake_exchange.get_sell_amount() * float(ohlcv_datas.data[idx].open)
                total_stake -= fake_exchange.get_sell_amount()

            df.loc[ohlcv_datas.data[idx].timestamp, 'strategy_gain'] = total_money + total_stake * float(ohlcv_datas.data[idx].open)

    if test_options.draw['enabled']:
        add_plot = [
            mpf.make_addplot(df['compaired_gain'], color='gray', panel=1, secondary_y=False),
            mpf.make_addplot(df['strategy_gain'], color='blue', panel=1, secondary_y=False) 
        ]
        if df['buy_point'].any():
            add_plot.append(mpf.make_addplot(df['buy_point'], markersize = 50, type='scatter', color='red', marker='^'))
        if df['sell_point'].any():
            add_plot.append(mpf.make_addplot(df['sell_point'], markersize = 50, type='scatter', color='green', marker='v'))

        if test_options.draw.get('indicators') and test_options.draw.get('indicators').get('macd'):
            macd = macd_info(ohlcv_datas.data)
            add_plot.append(mpf.make_addplot(macd['macd_hist_series'].where(macd['macd_hist_series'] >= 0 ), type='bar', panel=2, color='g', alpha=1)),
            add_plot.append(mpf.make_addplot(macd['macd_hist_series'].where(macd['macd_hist_series'] < 0 ), type='bar', panel=2, color='r', alpha=1)),

        if test_options.draw.get('indicators') and test_options.draw.get('indicators').get('sar'):
            sar = sar_info(ohlcv_datas.data)
            add_plot.append(mpf.make_addplot(sar['sar_series'], type='scatter', marker='*', color='yellow'))

        if test_options.draw.get('indicators') and test_options.draw.get('indicators').get('boll'):
            boll = boll_info(ohlcv_datas.data)
            add_plot.append(mpf.make_addplot(boll['lowerband_series'], color='red'))
            add_plot.append(mpf.make_addplot(boll['middleband_series'], color='gray'))
            add_plot.append(mpf.make_addplot(boll['upperband_series'], color='green'))

        mpf.plot(df, type='candle', style='yahoo',
            title=f'{params.symbol} Strategy', ylabel='Price',
            addplot=add_plot,
            figscale=1.5, figsize=(16, 10)
        )
