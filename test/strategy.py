from typing import Type, TypedDict, Optional
from dataclasses import dataclass
from datetime import datetime
import numpy as np 
import mplfinance as mpf
from lib.adapter.crypto_exchange.base import CryptoExchangeAbstract, CryptoTicker
from lib.adapter.database.crypto_cache import CryptoOhlcvCacheFetcher
from lib.adapter.database.session import SqlAlchemySession
from lib.model import CryptoFee, CryptoOhlcvHistory, CryptoOrder, CryptoOrderSide
from lib.modules.notification_logger import NotificationLogger
from lib.modules.strategy import ContextBase, Dependency, ParamsBase, StrategyFunc
from lib.modules.crypto import crypto
from lib.utils.ohlcv import boll_info, macd_info, sar_info, to_df
from lib.utils.string import random_id

from fake_modules.fake_db import fake_session
from fake_modules.fake_notification import FakeNotification

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

class FakeExchange(CryptoExchangeAbstract):
    curr_time: datetime
    curr_price: float
    is_buy: bool
    is_sell: bool

    def __init__(self, session: SqlAlchemySession):
        self.fake_session = session

    def set_curr_time(self, datetime: datetime):
        self.curr_time = datetime

    def set_curr_price(self, price: float):
        self.curr_price = price

    def clear(self):
        self.is_buy = False
        self.is_sell = False

    def fetch_ticker(self, pair: str) -> CryptoTicker:
        return CryptoTicker(last = self.curr_price)
    
    def fetch_ohlcv(self, pair, frame, start, end) -> CryptoOhlcvHistory:
        cache = CryptoOhlcvCacheFetcher(self.fake_session)
        with self.fake_session:
            return cache.range_query(pair, frame, start, end)
    
    def create_order(self, pair, type, side: CryptoOrderSide, amount, _price = None) -> CryptoOrder:
        if side == 'buy':
            self.is_buy = True
        if side == 'sell':
            self.is_sell = True
        return CryptoOrder(
            # clientOrderId 
            context = {},
            exchange = 'binance',
            id = random_id(10),
            timestamp = self.curr_time,
            pair = pair,
            type = type,
            side = side,
            amount = amount,
            price = self.curr_price,
            cost = self.curr_price * amount + ((0.001 * amount) * self.curr_price),
            fee = CryptoFee(pair, 0.001 * amount, 0.001) if side == 'buy' else CryptoFee(pair, 0.01 * amount * self.curr_price, 0.001)
        )
    
def strategy_test(strategy_func: StrategyFunc, test_options: StrategyTestOptions, params: ParamsBase, contextClass: Type[ContextBase]):
    fake_exchange = FakeExchange(fake_session)
    stub_deps = Dependency(
        exchange=fake_exchange,
        session=fake_session,
        notification= NotificationLogger('Test-Strategy', FakeNotification())
    )

    ohlcv_datas = crypto.get_ohlcv_history(params.symbol, params.data_frame, test_options.from_time, test_options.end_time)
    df = to_df(ohlcv_datas.data)

    init_coin = params.money / ohlcv_datas.data[test_options.batch_count].close
    df['compaired_gain'] = df['close'] * init_coin
    df['strategy_gain'] = float(params.money)
    df['buy_point'] = np.nan
    df['sell_point'] = np.nan

    with fake_session:
        cache = CryptoOhlcvCacheFetcher(fake_session)
        cache.add(ohlcv_datas)
        fake_session.commit()
    
    with contextClass(params, stub_deps) as context:
        for idx in range(0, len(ohlcv_datas.data)):
            if idx < test_options.batch_count:
                df.loc[ohlcv_datas.data[idx].timestamp, 'compaired_gain'] = float(params.money)
                continue
            
            fake_exchange.clear()
            fake_exchange.set_curr_time(ohlcv_datas.data[idx].timestamp)
            fake_exchange.set_curr_price(float(ohlcv_datas.data[idx].open))

            result = strategy_func(context, ohlcv_datas.data[idx - test_options.batch_count: idx])

            # df['strategy_gain'].iloc[idx] = result.total_assets
            df.loc[ohlcv_datas.data[idx].timestamp, 'strategy_gain'] = result.total_assets
            if fake_exchange.is_buy:
                # df['buy_point'].iloc[idx] = ohlcv_datas.data[idx].open
                df.loc[ohlcv_datas.data[idx].timestamp, 'buy_point'] = ohlcv_datas.data[idx].open
            if fake_exchange.is_sell:
                # df['sell_point'].iloc[idx] = ohlcv_datas.data[idx].open
                df.loc[ohlcv_datas.data[idx].timestamp, 'sell_point'] = ohlcv_datas.data[idx].open
    #stub_deps.notification_logger.send()
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