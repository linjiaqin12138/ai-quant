from datetime import datetime
import json
from typing import Any, List, Optional, TypedDict
from dataclasses import asdict, dataclass 

import akshare as ak
import pandas as pd

from lib.model.common import Ohlcv, Order
from lib.model.news import NewsInfo
from lib.tools import advice_crypto_action, summary_crypto_news, advice_ashare_action, summary_ashare_news,  AgentAdvice, CryptoExchangeFutureInfo, TradeLog
from lib.adapter.exchange.crypto_exchange.binance import BinanceExchange
from lib.modules.strategyv2 import StrategyBase
from lib.modules.news_proxy import news_proxy
from lib.utils.list import filter_by, map_by
from lib.utils.string import hash_str
from lib.utils.time import dt_to_ts, hours_ago, ts_to_dt

COMMON_DEFAULT_PARAMETERS = {
    'advice_mode_provider': 'paoluz',
    'advice_model': 'byte/deepseek-r1',
    'news_summary_mode_provider':'paoluz',
    'news_summary_model': 'gpt-4o-mini',
    'risk_prefer': '风险厌恶型',
    'strategy_prefer': '中长期投资'
}

@dataclass
class GptStrategyMixin:
    advice_mode_provider: str = 'paoluz'
    advice_model: str = 'byte/deepseek-r1'
    news_summary_mode_provider: str = 'paoluz'
    news_summary_model: str = 'gpt-4o-mini'
    risk_prefer: str = '风险厌恶型',
    strategy_prefer: str = '中长期投资'
    _data_fetch_amount = 60

    def _addtional_state_parameters(self):
        return {
            'operations': []
        }
    
    def _add_operation(self, order: Order, summary: str) -> TradeLog:
        operations: TradeLog = {}
        operations['action'] = order.side
        operations['cost'] = order.get_cost(True)
        operations['amount'] = order.get_amount(True)
        operations['position_ratio'] = (self.hold_amount * self.current_price) / (self.free_money + self.hold_amount * self.current_price)
        operations['summary'] = summary
        operations['timestamp'] = dt_to_ts(order.timestamp)
        self.state.append('operations', operations)

class CryptoGptStrategy(GptStrategyMixin, StrategyBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _prepare(self):
        self.binance_future = BinanceExchange(future_mode=True)
        # if self._is_test_mode:
        #     [test_start, test_end] = self.state.get('bt_test_range')
        #     self.funding_rate_history = self.binance_future.binance.fetch_funding_rate_history(self._symbol, params={ 'startTime': test_start, 'endTime': test_end })
        #     # 确保 funding_rate_history 按时间戳排序
        #     self.funding_rate_history = sorted(self.funding_rate_history, key=lambda x: x['timestamp'])
        #     self.global_long_short_account_history = self.binance_future.get_u_base_global_long_short_account_ratio(self._symbol, self._frame, ts_to_dt(test_start), ts_to_dt(test_end))
        #     self.top_long_short_account_history = self.binance_future.get_u_base_top_long_short_account_ratio(self._symbol, self._frame, ts_to_dt(test_start), ts_to_dt(test_end))
        #     self.top_long_short_amount_history = self.binance_future.get_u_base_top_long_short_ratio(self._symbol, self._frame, ts_to_dt(test_start), ts_to_dt(test_end))

    def get_future_info(self) -> Optional[CryptoExchangeFutureInfo]:
        res: CryptoExchangeFutureInfo = {}
        if self._is_test_mode:
            return None
            # def filter_history(history: List[Dict[str, Any]], start: datetime, end: datetime) -> List[Dict[str, Any]]:
            #     return [entry for entry in history if start <= entry['timestamp'] <= end]
            
            # for entry in self.funding_rate_history:
            #     if ts_to_dt(entry['timestamp']) <= self.current_time:
            #         res['future_rate']  = float(entry['info']['fundingRate'])
            #     else:
            #         break 
            # res['global_long_short_account'] = float(filter_history(self.global_long_short_account_history, start, end)[0]['longShortRatio'])
            # res['top_long_short_account'] = float(filter_history(self.top_long_short_account_history, start, end)[0]['longShortRatio'])
            # res['top_long_short_amount'] = float(filter_history(self.top_long_short_amount_history, start, end)[0]['longShortRatio'])
            # return res
        else:
            res['future_rate'] = self.binance_future.get_latest_futures_price_info(self.symbol)['lastFundingRate']
            res['global_long_short_account'] = self.binance_future.get_u_base_global_long_short_account_ratio(self.symbol, '15m', hours_ago(1))[-1]['longShortRatio']
            res['top_long_short_account'] = self.binance_future.get_u_base_top_long_short_account_ratio(self.symbol, '15m', hours_ago(1))[-1]['longShortRatio']
            res['top_long_short_amount'] = self.binance_future.get_u_base_top_long_short_ratio(self.symbol, '15m', hours_ago(1))[-1]['longShortRatio']
            return res

    def _core(self, ohlcv_history: List[Ohlcv]):
        self.logger.msg("Current Time is ", self.current_time)
        news = news_proxy.get_news_during(
            'cointime',
            ohlcv_history[-1].timestamp, 
            self.current_time
        )
        coin_name = self.symbol.rstrip('USDT').rstrip('/')
        news_text = summary_crypto_news(
            coin_name, 
            { 'cointime': news },
            llm_provider = self.news_summary_mode_provider,
            model = self.news_summary_model,
            temperature=0.2
        )
        advice: AgentAdvice = advice_crypto_action(
            coin_name,
            ohlcv_history,
            account_info = {
                'free': self.free_money, 
                'hold_amount': self.hold_amount, 
                'hold_val': self.hold_amount * ohlcv_history[-1].close
            },
            trade_history = self.state.get('operations'),
            exchange_future_info= self.get_future_info(),
            related_news=news_text,
            llm_provider= self.advice_mode_provider,
            model = self.advice_model,
            risk_prefer = self.risk_prefer,
            strategy_prefer = self.strategy_prefer,
            use_indicators = ['sma', 'rsi', 'boll', 'macd', 'stoch', 'atr'],
            detect_ohlcv_pattern = True,
            temperature = 0.2,
            msg_logger = self.logger
        )
        self.logger.msg(json.dumps(asdict(advice), indent=2, ensure_ascii=False))
        if advice.action == 'buy':
            order = self.buy(spent=advice.cost, comment=advice.reason)
            self._add_operation(order, advice.summary)
        elif advice.action == 'sell':
            order = self.sell(amount=advice.amount, comment=advice.reason)
            self._add_operation(order, advice.summary)

class AshareGptStrategy(GptStrategyMixin, StrategyBase):
    

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _addtional_state_parameters(self):
        import akshare as ak 
        result = GptStrategyMixin._addtional_state_parameters(self)
        if self.symbol.startswith(('51', '15', '16')):
            df = ak.fund_name_em()
            result['stock_type'] = 'ETF'
            result['stock_name'] = df['基金简称'].loc[df['基金代码'] == self.symbol].iloc[0]
            result['stock_business'] = self.stock_business # 从run/back_test的addtional_params中指定
        else:
            df = ak.stock_individual_info_em(self.symbol)
            result['stock_type'] = '股票'
            result['stock_name'] = df['value'].loc[df['item'] == '股票简称'].iloc[0]
            result['stock_business'] = df['value'].loc[df['item'] == '行业'].iloc[0]
        return result
    
    def _prepare(self):
        if not self._is_test_mode:
            return
        stock_news_100 = ak.stock_news_em(symbol=self.symbol)
        stock_news_100['发布时间'] = pd.to_datetime(stock_news_100['发布时间'])
        test_stock_news_list = []
        for _, row in stock_news_100.iterrows():
            news_info = {
                'title': row['新闻标题'], 
                'timestamp': dt_to_ts(row['发布时间']),
                'description': row['新闻内容'], 
                'news_id': hash_str(row['新闻标题']),
                'url': row['新闻链接'],
                'platform': 'eastmoney'
            }
            test_stock_news_list.append(news_info)
        self.state.set("bt_stock_news_list", test_stock_news_list)

    def get_stock_news(self, from_time: datetime) -> List[NewsInfo]:
        if self._is_test_mode:
            stock_news_in_range = filter_by(self.state.get('bt_stock_news_list'), lambda n: dt_to_ts(from_time) <= n['timestamp'] <= dt_to_ts(self.current_time))
            result = []
            for item in stock_news_in_range:
                deep_cloned = {}
                deep_cloned.update(item)
                deep_cloned['timestamp'] = ts_to_dt(deep_cloned['timestamp'])
                result.append(NewsInfo(**deep_cloned))
            return result
        else:
            import akshare as ak
            import pandas as pd
            news_100_df = ak.stock_news_em(symbol=self.symbol)

            news_100_df['发布时间'] = pd.to_datetime(news_100_df['发布时间'])

            # 过滤出指定datetime之前的行
            filtered_df = news_100_df[news_100_df['发布时间'] >= from_time]

            news_info_list = []
            for _, row in filtered_df.iterrows():
                news_info = NewsInfo(
                    title=row['新闻标题'], 
                    timestamp=row['发布时间'],
                    description=row['新闻内容'], 
                    news_id = hash_str(row['新闻标题']),
                    url = row['新闻链接'],
                    platform = 'eastmoney'
                )
                news_info_list.append(news_info)

            return news_info_list

    def _core(self, ohlcv_history: List[Ohlcv]):
        caixin_news = news_proxy.get_news_during(
            'caixin',
            ohlcv_history[-1].timestamp, 
            self.current_time
        )
        stock_news_by_eastmoney = self.get_stock_news(ohlcv_history[-1].timestamp)
        stock_name = self.state.get('stock_name')
        stock_type = self.state.get('stock_type')
        stock_business = self.state.get('stock_business')
        news_text = summary_ashare_news(
            stock_name = stock_name, 
            stock_code = self.symbol,
            stock_business = stock_business,
            news_by_platform = {
                'caixin': caixin_news,
                'eastmoney': stock_news_by_eastmoney
            },
            llm_provider = self.news_summary_mode_provider,
            model = self.news_summary_model,
            stock_type = stock_type,
            temperature = 0.2
        )
        advice: AgentAdvice = advice_ashare_action(
            stock_name=stock_name,
            curr_price=self.current_price,
            ohlcv_list=ohlcv_history,
            account_info = {
                'free': self.free_money, 
                'hold_amount': self.hold_amount, 
                'hold_val': self.hold_amount * ohlcv_history[-1].close
            },
            trade_history = self.state.get('operations'),
            related_news=news_text,
            llm_provider= self.advice_mode_provider,
            model = self.advice_model,
            risk_prefer = self.risk_prefer,
            strategy_prefer = self.strategy_prefer,
            use_indicators = ['sma', 'rsi', 'boll', 'macd', 'stoch', 'atr'],
            detect_ohlcv_pattern = True,
            temperature = 0.2,
            msg_logger = self.logger
        )
        self.logger.msg(json.dumps(asdict(advice), indent=2, ensure_ascii=False))
        if advice.action == 'buy':
            order = self.buy(spent=advice.cost, comment=advice.reason)
            self._add_operation(order, advice.summary)
        elif advice.action == 'sell':
            order = self.sell(amount=advice.amount, comment=advice.reason)
            self._add_operation(order, advice.summary)

if __name__ == '__main__':
    s = AshareGptStrategy(
        advice_mode_provider='siliconflow',
        advice_model='deepseek-ai/DeepSeek-V3',
        news_summary_mode_provider='siliconflow',
        news_summary_model='THUDM/glm-4-9b-chat'
    )
    s.back_test(
        datetime(2025, 1, 1), 
        datetime(2025, 3, 1),
        name='闻泰科技 1.1-3.1 回测 DeepSeek V3', 
        symbol='600745',  
        investment=50000,
        risk_prefer="风险喜好型",
        strategy_prefer="低吸高抛，注重短期收益，分批买入卖出不梭哈",
        recovery_file="./recover_600745.json",
        show_indicators=['boll', 'macd']
    )
    # s = CryptoGptStrategy(
    #     advice_mode_provider='paoluz',
    #     advice_model='deepseek-ai/DeepSeek-V3',
    #     news_summary_mode_provider='paoluz',
    #     news_summary_model='gpt-4o-mini'
    # )
    # s.back_test(
    #     start_time=datetime(2025, 1, 1), 
    #     end_time=datetime(2025, 2, 27),
    #     name='ETH 1.1-2.27 回测 DeepSeek V3', 
    #     symbol='ETH/USDT',  
    #     investment=1000,
    #     risk_prefer="风险喜好型",
    #     strategy_prefer="低吸高抛，注重短期收益",
    #     recovery_file="./recover_eth.json"
    # )
    # s.run('SOL GPT 交易报告', 'SOL/USDT', 1000)
    