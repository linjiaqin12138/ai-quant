from dataclasses import dataclass
from typing import Any, List, TypedDict, Optional
from datetime import datetime, timedelta

from ..utils.number import change_rate, get_total_assets

from ..model import CryptoHistoryFrame, Ohlcv
from ..utils.time import dt_to_ts, timeframe_to_second, ts_to_dt
from ..utils.ohlcv import to_df
from ..modules.notification_logger import NotificationLogger
from ..modules.strategy import Dependency, ParamsBase, ResultBase, ContextBase

ContextDict = TypedDict('Context', {
    'account_usdt_amount': float,
    'account_coin_amount': float,
    'buyable': bool,
    'sellable': bool,
    'max_price': Optional[float], # Required if sellable
    'buy_round': int,
    'last_time_buy': Optional[int]
})

@dataclass
class Params(ParamsBase):
    min_window: int
    max_window: int
    max_retrieval: Optional[float] = None
    max_buy_round: int = 1

class Context(ContextBase):

    def __init__(self, params: Params, deps: Dependency):
        super().__init__(params, deps)

    def init_id(self, params: Params) -> str:
        return f'{super().init_id(params)}_TURTLE_PLAN'
    
    def init_context(self, params: Params) -> ContextDict:
        return {
            'account_usdt_amount': params.money,
            'account_coin_amount': 0,
            'buyable': True,
            'sellable': False,
            'buy_round': 0,
        }
    
    def set(self, key: str, value: Any) -> None:
        if key == 'last_time_buy':
            assert type(value) == datetime
            return super().set(key, dt_to_ts(value))
        return super().set(key, value)
    
    def get(self, key: str) -> Any | None:
        if key == 'max_price':
            assert self._context['buy_round'] > 0

        if key == 'last_time_buy' and self._context.get(key):
            return ts_to_dt(self._context[key])

        return super().get(key)

def time_pass(last_time: datetime, now: datetime, frame: CryptoHistoryFrame) -> int:
    return int((now - last_time) / timedelta(seconds=timeframe_to_second(frame)))

def simple_turtle(context: Context, data: List[Ohlcv] = []) -> ResultBase:
    params: Params = context._params
    deps = context._deps

    expected_data_length = max(params.max_window, params.min_window) + 1
    if len(data) == 0:
        data = deps.crypto.get_ohlcv_history(params.symbol, params.data_frame, 
           datetime.now() - (expected_data_length) * timedelta(seconds = timeframe_to_second(params.data_frame)),
           datetime.now()           
        ).data
    assert len(data) >= expected_data_length
   

    # 为了防止单元测试中datetime.now()返回当前时间，所以实际通过这种方式来作为当前时间，效果差不多
    curr_time = data[-1].timestamp + timedelta(seconds=timeframe_to_second(params.data_frame))

    df = to_df(data)
    df["min_in_window"] = df["close"].rolling(window=params.min_window).min()
    df["max_in_window"] = df["close"].rolling(window=params.max_window).max()
    close_price = float(df['close'].iloc[-1])
    
    if context.get('buy_round') > 0 and context.get('max_price') < close_price:
        curr_gain = get_total_assets(close_price, context.get('account_coin_amount') , context.get('account_usdt_amount') )
        passed_time = time_pass(context.get('last_time_buy'), curr_time, params.data_frame)
        deps.notification_logger.msg(f'{params.symbol} 买入{passed_time}个周期涨到最高价 {close_price}, 总收益率：', change_rate(params.money, curr_gain) * 100, '%')
        context.set('max_price', close_price)

    if context.get('buyable'):
        is_max_window = close_price > df['max_in_window'].iloc[-2]
        is_next_round = (context.get('last_time_buy') is None) or time_pass(context.get('last_time_buy') , curr_time, params.data_frame) >= params.max_window

        if is_max_window and not is_next_round:
            deps.notification_logger.msg(f'{params.symbol} 价格突破{params.max_window}周期最大值, 但不买入')

        if is_next_round and is_max_window:
            spent = context.get('account_usdt_amount') * 0.5 if context.get('buy_round') + 1 < params.max_buy_round else context.get('account_usdt_amount') 
            order = deps.crypto.create_order(params.symbol, 'market', 'buy', 'TURTLE_PLAN', spent = spent)

            context.set('sellable', True)
            context.set('account_usdt_amount', context.get('account_usdt_amount') - order.cost)
            context.set('account_coin_amount', context.get('account_coin_amount') + order.amount)
            context.set('max_price', close_price)
            context.set('buy_round', context.get('buy_round') + 1)
            context.set('last_time_buy', curr_time)
            if context.get('buy_round') >= params.max_buy_round:
                context.set('buyable', False)
        
            deps.notification_logger.msg(f'{order.timestamp} 花费 ', order.cost, ' USDT 买入 ', order.amount, '个', params.symbol, ', 剩余: ', context.get("account_usdt_amount"), ' USDT')
    
    
    if context.get('sellable') :
        is_max_retrieval = (params.max_retrieval and change_rate(context.get('max_price') , close_price) < -params.max_retrieval)
        is_min_window = close_price < df['min_in_window'].iloc[-2]

        if is_max_retrieval:
            deps.notification_logger.msg(f'{params.symbol} 达到最大回撤 {params.max_retrieval * 100}%, 卖出')
        if is_min_window:
            deps.notification_logger.msg(f'{params.symbol} 价格跌破{params.min_window}周期最小值，卖出')
    
        if is_min_window or is_max_retrieval:
            order = deps.crypto.create_order(params.symbol, 'market', 'sell', 'TURTLE_PLAN', amount = context.get('account_coin_amount') )
            context.set('buyable', True)
            context.set('sellable', False)
            context.set('account_usdt_amount', context.get('account_usdt_amount') + order.cost)
            context.set('account_coin_amount', context.get('account_coin_amount') - order.amount)
            context.delete('max_price')
            context.delete('last_time_buy')
            context.set('buy_round', 0)

            deps.notification_logger.msg(f'{order.timestamp} 卖出 ', order.amount, ' ', params.symbol, ', 总共', order.cost, ' USDT 剩余: ', context.get("account_usdt_amount"), 'USDT')

    return ResultBase(
        total_assets=get_total_assets(close_price, context.get('account_coin_amount') , context.get('account_usdt_amount') )
    )

def run(params: dict, notification: NotificationLogger):
    with Context(params = Params(**params), deps=Dependency(notification=notification)) as context:
        simple_turtle(context)


        