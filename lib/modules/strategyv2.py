import abc
import json
import math
from datetime import datetime
import time
from typing import Any, Dict, Literal, Optional, List

import pandas as pd
import numpy as np
from tqdm import tqdm

from lib.model.common import Ohlcv, Order
from lib.utils.time import round_datetime_in_period, dt_to_ts, time_ago_from, ts_to_dt
from lib.utils.ohlcv import to_df
from lib.utils.string import random_id
from lib.adapter.database.session import SqlAlchemySession
from lib.adapter.database.kv_store import KeyValueStore
from lib.adapter.notification import PushPlus
from lib.adapter.notification.api import NotificationAbstract
from lib.modules.notification_logger import NotificationLogger
from lib.modules.trade import TradeOperations, CryptoTrade, AshareTrade

class StateApi(abc.ABC):
    @abc.abstractmethod
    def get(self, key: str) -> Optional[Dict[str, Any]]:
        return None
    
    @abc.abstractmethod
    def delete(self, key: str) -> None:
        return None
    
    @abc.abstractmethod
    def set(self, key: str, val: Any) -> None:
        return
    
    @abc.abstractmethod
    def append(self, key: str, val: Any) -> None:
        return 
    
    @abc.abstractmethod
    def increase(self, key: str, value: float | int) -> None:
        return

    @abc.abstractmethod
    def decrease(self, key: str, value: float | int) -> None:
        return
    
    @abc.abstractmethod
    def save(self) -> None:
        return

class SimpleState(StateApi):

    def __init__(self, default: dict):
        self.temp_context = default
        self._context = default

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        return self.temp_context.get(key)
    
    def delete(self, key: str) -> None:
        del self.temp_context[key]
        
    def set(self, key: str, val: Any) -> None:
        self.temp_context[key] = val
    
    def append(self, key: str, val: Any) -> None:
        self.temp_context[key].append(val)
    
    def increase(self, key: str, value: float | int) -> None:
        self.temp_context[key] = self.temp_context[key] + value

    def decrease(self, key: str, value: float | int) -> None:
        self.temp_context[key] = self.temp_context[key] - value
    
    def save(self) -> None:
        self._context = self.temp_context
    
class PersisitentState(StateApi):
    def __init__(self, id, default: dict):
        self.id = id
        self.is_dirt = False
        self.session = SqlAlchemySession()
        self.kv_store = KeyValueStore(self.session)
        with self.session:
            self._context = self.kv_store.get(self.id)
            if self._context is None: 
                self._context = default
                self.is_dirt = True
        
    
    def get(self, key: str) -> Any | None:
        return self._context.get(key)
    
    def set(self, key: str, value: Any) -> None:
        self.is_dirt = True
        self._context[key] = value

    def append(self, key: str, val: Any) -> None:
        assert self._context.get(key) is not None, f'{key} is not exist in context'
        assert isinstance(self._context[key], list), f'{key} is not a value of list'
        self.set(key, self._context[key] + [val])
    
    def increase(self, key: str, value: float | int) -> None:
        assert self._context.get(key) is not None, f'{key} is not exist in context'
        assert isinstance(self._context[key], (int, float)), f'{key} is not a value of number'
        self.set(key, self._context[key] + value)

    def decrease(self, key: str, value: float | int) -> None:
        return self.increase(key, -value)

    def delete(self, key) -> None:
        if self._context.get(key):
            self.is_dirt = True
            del self._context[key]

    def save(self):
        if self.is_dirt:
            with self.session:
                self.kv_store.set(self.id, self._context)
                self.session.commit()
                self.is_dirt = False

class ConsulPrint(NotificationAbstract):
    def send(self, content: str, title: str = ''):
        print(f'[{title}] {content}')

class FakeOrder(Order):

    def get_amount(self, excluding_fee: bool = False):
        return self._amount
    
    def get_cost(self, including_fee: bool = False):
        return self._cost

def save_recovery_data(
        file_path: str, 
        df: pd.DataFrame, 
        start_time: datetime, 
        end_time: datetime,
        state: SimpleState, 
        symbol: str, 
        investment: float, 
        iter_from_idx: int, 
        history: List[Ohlcv]
):
    
    df_dict = df.reset_index().to_dict(orient='records')
    # Convert datetime to timestamp
    for item in df_dict:
        item['timestamp'] = item['timestamp'].value // 10**6  # Ensure timestamp is in milliseconds
        # Set None for null values
        for key in item:
            if math.isnan(item[key]):
                item[key] = None
    recovery_data = {
        'df': df_dict,
        'start_time': start_time.isoformat(),
        'end_time': end_time.isoformat(),
        'state': state._context,
        'symbol': symbol,
        'investment': investment,
        'current_idx': iter_from_idx,
        'history': [ohlcv.__dict__() for ohlcv in history]
    }
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(recovery_data, f, ensure_ascii=False)

def load_recovery_data(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        recovery_data = json.load(f)
    df = pd.DataFrame(recovery_data['df'])
    # Convert timestamp to datetime and set None to np.nan
    df_dict = recovery_data['df']
    for item in df_dict:
        item['timestamp'] = pd.Timestamp(item['timestamp'], unit='ms')
        # Set None to np.nan
        for key in item:
            if item[key] is None:
                item[key] = np.nan
    df = pd.DataFrame(df_dict).set_index('timestamp')
    start_time = pd.to_datetime(recovery_data['start_time'])
    end_time = pd.to_datetime(recovery_data['end_time'])
    state = SimpleState(recovery_data['state'])
    current_idx = recovery_data['current_idx']
    history = [Ohlcv.from_dict(hist) for hist in recovery_data['history']]
    return df, start_time, end_time, state, current_idx, history

class StrategyBase(abc.ABC):
    # 基本默认值
    symbol: str = 'BTC/USDT'
    investment: float = 100.0
    name: str = 'Strategy'
    frame: str = '1d'
    # 这个参数在子类中修改
    _data_fetch_amount: int = 40
    # 用来判断是否运行在回测backtest还是实盘run，来选择性做一些事情
    _is_test_mode: bool = False

    # 实际运行时指定
    state: StateApi
    trade_ops: TradeOperations
    logger: NotificationLogger

    def buy(self, spent: float = None, amount: float = None, comment: str = None) -> Order:
        if not spent and not amount:
            raise ValueError("Either 'spent' or 'amount' must be provided.")
        if spent and amount:
            raise ValueError(f"Invalid operation: spent={spent}, amount={amount}. Both should not be set simultaneously.")
        if spent > self.free_money:
            raise ValueError(f"Spent amount ({spent}) exceeds available free money ({self.free_money}).")
        
        self.logger.msg(f'Attempting to buy: spent={spent}, amount={amount}.')
        
        if not self._is_test_mode:
            order = self.trade_ops.create_order(self.symbol, 'market', 'buy', self.name, amount=amount, spent=spent, comment=comment)
            self.state.decrease('free_money', order.get_cost(True))
            self.state.increase('hold_amount', order.get_amount(True))
            return order
        else:
            self.state.set('bt_observed_action', 'buy')
            increase_amount = spent / self.current_price if spent else amount 
            decrease_money = spent if spent else amount * self.current_price
            self.state.decrease('free_money', decrease_money)
            self.state.increase('hold_amount', increase_amount)
            
            return FakeOrder(
                id=random_id(20),
                timestamp=self.current_time,
                symbol=self.symbol,
                type='market',
                side='buy',
                price=self.current_price,
                _amount = increase_amount,
                _cost = decrease_money,
                fees = []
            )

    
    def sell(self, amount: float, comment: str=None) -> Order:
        self.logger.msg(f'Attempting to sell: amount={amount}.')
        if amount > self.hold_amount:
            raise ValueError(f"Attempted to sell {amount}, but only {self.hold_amount} is held.")

        if not self._is_test_mode:
            order = self.trade_ops.create_order(self.symbol, 'market', 'sell', self.name, amount=amount, comment=comment)
            self.state.increase('free_money', order.get_cost(True))
            self.state.decrease('hold_amount', order.get_amount(True))
            return order
        else:
            self.state.set('bt_observed_action', 'sell')
            self.state.increase('free_money', amount * self.state.get('bt_current_price'))
            self.state.decrease('hold_amount', amount)
            return FakeOrder(
                id=random_id(20),
                timestamp=self.current_time,
                symbol=self.symbol,
                type='market',
                side='sell',
                price=self.current_price,
                _amount = amount,
                _cost = amount * self.state.get('bt_current_price'),
                fees = []
            )
       
    
    def _id(self) -> str:
        return "{{\"name\": {name}, \"frame\": {frame}, \"symbol\": {symbol}}}".format(
            name = self.name,
            symbol = self.symbol,
            frame = self.frame
        )
    
    def _prepare(self):
        """
        Override this function to inject dependencys for run or back_test according to is_test_mode
        """
        return
    
    def _addtional_state_parameters(self):
        """
        Override this function if need to inject addtional initial state parameters
        """
        return {}
    
    @property
    def free_money(self) -> float:
        return self.state.get('free_money')
    
    @property
    def hold_amount(self) -> float:
        return self.state.get('hold_amount')
    
    @property
    def current_price(self) -> float:
        if self._is_test_mode:
            return self.state.get('bt_current_price')
        else:
            return self.trade_ops.get_current_price(self.symbol)

    # Don't use datetime.now in _core()
    @property
    def current_time(self) -> datetime:
        if self._is_test_mode:
            return ts_to_dt(self.state.get('bt_current_time'))
        else:
            return datetime.now()

    @abc.abstractmethod
    def _core(self, ohlcv_history: List[Ohlcv]):
        pass

    def _init_state(self):
        addtional_params = self._addtional_state_parameters()
        for key in addtional_params.keys():
            if key.startswith('bt_'):
                raise ValueError(f"Invalid key '{key}' in additional_params: keys cannot start with 'bt_'.")
        init_state = addtional_params
        init_state.update({
            'free_money': self.investment,
            'hold_amount': 0,
            # bt_current_price (bt_* is reserve for test)
        })
        return init_state

    def run(
            self, 
            name: str = None, 
            symbol: str = None, 
            investment: float = None, 
            frame: str = None,
            **addtional_params
        ):
        self._is_test_mode = False
        self.symbol = symbol or self.symbol
        self.investment = investment or self.investment
        self.name = name or self.name
        self.frame = frame or self.frame
        for param, val in addtional_params:
            setattr(self, param, val)

        self.trade_ops = CryptoTrade() if self.symbol.endswith('USDT') else AshareTrade()
        try:
            if not self.trade_ops.is_business_day():
                return
            ohlcv_list = self.get_ohlcv_history(self.symbol, self.frame, limit=self._data_fetch_amount)
            self.state = PersisitentState(self._id(), default=self._init_state())
            self.logger = NotificationLogger(self.name, PushPlus())

            self._prepare()
            self._core(ohlcv_list)

            self.state.save()
        except Exception as e:
            import traceback
            self.logger.msg(traceback.format_exc())
        finally:
            self.logger.send()

    def _trace_back_business_day_from(self, count: int, from_time: datetime) -> datetime:
        while count > 0:
            days_ahead = time_ago_from(1, self.frame, from_time)
            if self.trade_ops.is_business_day(days_ahead):
                count -= 1
            from_time = days_ahead
        return from_time
    
    def get_ohlcv_history(self, limit: int = None, start_time: datetime = None, end_time: datetime = datetime.now()) -> List[Ohlcv]:
        # TODO：根据is_test_mode，从history中捞必要的部分
        if limit:
            start_time = self._trace_back_business_day_from(limit, end_time)
            return self.trade_ops.get_ohlcv_history(self.symbol, self.frame, start=start_time, end=end_time).data
        else:
            return self.trade_ops.get_ohlcv_history(self.symbol, self.frame, start=start_time, end=end_time).data

    def back_test(
            self,
            start_time: datetime,
            end_time: datetime,
            symbol: str,
            investment: float,
            name: str = None,
            frame: str = None,
            recovery_file: Optional[str] = None,
            show_indicators: List[Literal['macd', 'boll']] = [],
            **addtional_params
        ):
        
        import mplfinance as mpf
        import os
        self._is_test_mode = True
        self.logger = NotificationLogger(self.name, ConsulPrint())
        # 回测时额外指定的策略参数，在整个策略运行过程中不变，不存入恢复文件，只从函数参数中读取
        self.symbol = symbol or self.symbol
        self.investment = investment or self.investment
        self.name = name or self.name
        self.frame = frame or self.frame
        for param, val in addtional_params.items():
            setattr(self, param, val)

        if recovery_file and os.path.exists(recovery_file):
            df, start_time, end_time, self.state, iter_from_idx, history = load_recovery_data(recovery_file)
        else:
            iter_from_idx = 0
            # start_time取整，防止用输入的start_time查询不到start_time所在周期的数据
            start_time = round_datetime_in_period(start_time, self.frame)
  
            self.trade_ops = CryptoTrade() if self.symbol.endswith('USDT') else AshareTrade()
            trace_back_start = self._trace_back_business_day_from(self._data_fetch_amount, start_time)
            history = self.get_ohlcv_history(
                start_time = trace_back_start,
                end_time = end_time
            )
            # TODO: 非交易日start_time 导致history[self._data_fetch_amount:]为空
            # 初始化历史数据的Dataframe以及准备计算的字段
            df = to_df(history[self._data_fetch_amount:])
            df['compaired_gain'] = np.nan
            df['strategy_gain'] = np.nan
            df['buy_point'] = np.nan
            df['sell_point'] = np.nan

            self.state = SimpleState(self._init_state())
            self.state.set('bt_start_amount', investment / history[self._data_fetch_amount].open)
            self.state.set('bt_test_range', [dt_to_ts(start_time), dt_to_ts(end_time)])

        # 加载一些额外的用于测试的数据，注入依赖等，会比较耗时, 应该提供一个接口支持将一些特殊数据进行保存，并在recover的时候从里面加载
        self._prepare()
        
        try:
            process_bar = tqdm(total=len(history) - self._data_fetch_amount, desc="Progress")
            for idx in range(iter_from_idx, len(history)):
                # for idx in trange(iter_from_idx, len(history), desc="Processing", unit="%", unit_scale=True):
                iter_from_idx, current_idx = idx, idx + self._data_fetch_amount
                # print('Process ', int((idx / (len(history) - self._data_fetch_amount)) * 100), '%')
                process_bar.update(idx - process_bar.n)
                if current_idx >= len(history):
                    break
                # self._core中通过self.current_price使用
                self.state.set('bt_current_price', history[current_idx].open)
                # self._core中通过self.current_time使用
                self.state.set('bt_current_time', dt_to_ts(history[current_idx].timestamp))
                # 用来在backtest场景下判断是否进行了交易
                self.state.set('bt_observed_action', 'none')

                self._core(history[iter_from_idx:current_idx])

                # 更新策略的当前收益和比较收益
                df.loc[history[current_idx].timestamp, 'strategy_gain'] = self.hold_amount * self.current_price + self.free_money
                df.loc[history[current_idx].timestamp, 'compaired_gain'] = self.current_price * self.state.get('bt_start_amount')
                # 判断是否进行了交易，并更新交易点的价格
                if self.state.get('bt_observed_action') == 'buy':
                    df.loc[history[current_idx].timestamp, 'buy_point'] = self.current_price 
                if self.state.get('bt_observed_action') == 'sell':
                    df.loc[history[current_idx].timestamp, 'sell_point'] = self.current_price

                self.state.save()
            process_bar.close()
        except (KeyboardInterrupt, Exception) as e:
            if not recovery_file:
                return 
            save_recovery_data(
                recovery_file,
                df,
                start_time,
                end_time,
                self.state,
                symbol,
                investment,
                iter_from_idx,
                history
            )
            raise e
           
        add_plot = [
            mpf.make_addplot(df['compaired_gain'], color='gray', panel=1, secondary_y=False),
            mpf.make_addplot(df['strategy_gain'], color='blue', panel=1, secondary_y=False) 
        ]
        if df['buy_point'].any():
            add_plot.append(mpf.make_addplot(df['buy_point'], markersize = 50, type='scatter', color='red', marker='^'))
        if df['sell_point'].any():
            add_plot.append(mpf.make_addplot(df['sell_point'], markersize = 50, type='scatter', color='green', marker='v'))
        
        if 'macd' in show_indicators:
            from lib.utils.indicators import macd_indicator
            macd = macd_indicator(history)
            macdhist_series = macd.macdhist_series.iloc[-len(df):]
            add_plot.append(
                mpf.make_addplot(
                    macdhist_series.where(macdhist_series >= 0), 
                    type='bar', 
                    panel=2, 
                    color='g', 
                    alpha=1
                )
            )
            add_plot.append(
                mpf.make_addplot(
                    macdhist_series.where(macdhist_series < 0), 
                    type='bar', 
                    panel=2, 
                    color='r', 
                    alpha=1
                )
            )

        if 'boll' in show_indicators:
            from lib.utils.indicators import bollinger_bands_indicator
            boll = bollinger_bands_indicator(history)

            add_plot.append(mpf.make_addplot(boll.lowerband_series.iloc[-len(df):], color='red'))
            add_plot.append(mpf.make_addplot(boll.middleband_series.iloc[-len(df):], color='gray'))
            add_plot.append(mpf.make_addplot(boll.upperband_series.iloc[-len(df):], color='green'))

        mpf.plot(
            df, 
            type='candle',
            # style='yahoo',
            title=self.name,
            ylabel='Price',
            addplot=add_plot,
            figscale=1.5,
            figsize=(16, 10),
            style=mpf.make_mpf_style(rc={'font.family': 'SimHei'})
        )


if __name__ == '__main__':
    class SimpleStategy(StrategyBase):
        _data_fetch_amount = 50

        def _core(self, ohlcv_history: List[Ohlcv]):
            if ohlcv_history[-1].close < ohlcv_history[0].close and self.free_money > 0:
                self.buy(spent = self.free_money)
            elif ohlcv_history[-1].close > ohlcv_history[1].close and self.hold_amount > 0:
                self.sell(self.hold_amount)
            time.sleep(0.1)

    s = SimpleStategy()
    s.back_test(
        name="策略测试",
        symbol='DOGE/USDT',
        start_time=datetime(2025,2,1,8),
        end_time=datetime(2025,2,27,8),
        investment=50000,
        show_indicators=['macd', 'boll']
    )