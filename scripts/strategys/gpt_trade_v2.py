from datetime import datetime
import json
from typing import List
from dataclasses import asdict, dataclass 

from lib.model.common import Ohlcv, Order
from lib.tools.market_master import MarketMaster, TradeContext, TradeLog
from lib.tools.news_helper import NewsHelper
from lib.modules.strategy.strategyv2 import StrategyBase
from lib.utils.time import dt_to_ts

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

@dataclass
class GptStrategy(StrategyBase):
    advice_model_provider: str = 'paoluz'
    advice_model: str = 'byte/deepseek-r1'
    advice_model_temperature: float = 0.2
    news_summary_model_provider: str = 'paoluz'
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
        operations['buy_cost'] = order.get_net_cost()
        operations['sell_amount'] = order.get_net_amount()
        operations['price'] = self.current_price
        operations['position_ratio'] = (self.hold_amount * operations['price']) / (self.free_money + self.hold_amount * operations['price'])
        operations['summary'] = summary
        operations['timestamp'] = dt_to_ts(order.timestamp)
        self.state.append('operations', operations)

    def _prepare(self):
        self.market_master = MarketMaster(
            risk_prefer=self.risk_prefer,
            strategy_prefer=self.strategy_prefer,
            llm_provider=self.advice_model_provider,
            model=self.advice_model,
            temperature=self.advice_model_temperature,
            news_helper=NewsHelper(
                llm_provider=self.news_summary_model_provider,
                model=self.news_summary_model,
            ),
            msg_logger=self.logger,
            use_crypto_future_info=False if self._is_test_mode else True
        )

    def _core(self, ohlcv_history: List[Ohlcv]):
        self.logger.msg("运行时间：", self.current_time)
        advice = self.market_master.give_trade_adevice(TradeContext(
            self.symbol,
            account_info={
                'free': self.free_money, 
                'hold_amount': self.hold_amount
            },
            trade_history=self.state.get('operations'),
            ohlcv_list=ohlcv_history,
            curr_time=self.current_time,
            curr_price=self.current_price
        ))

        self.logger.msg(json.dumps(asdict(advice), indent=2, ensure_ascii=False))
        if advice.action == 'buy':
            order = self.buy(spent=advice.buy_cost, comment=advice.reason)
            self._add_operation(order, advice.summary)
        elif advice.action == 'sell':
            order = self.sell(amount=advice.sell_amount, comment=advice.reason)
            self._add_operation(order, advice.summary)

        if self._is_test_mode:
            self.state.set('bt_addtional_info', { 'reason': advice.reason, 'summary': advice.summary })

if __name__ == '__main__':
    s = GptStrategy(
        advice_model_provider='siliconflow',
        advice_model='deepseek-ai/DeepSeek-V3',
        news_summary_model_provider='siliconflow',
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
    s.back_test(
        datetime(2025, 4, 1), 
        datetime(2025, 4, 25),
        name='以太坊4月回测', 
        symbol='WCT/USDT',  
        frame='1d',
        investment=50000,
        risk_prefer="稳健型",
        strategy_prefer="短线投资",
        recovery_file="./recover_eth.json",
        show_indicators=['boll', 'macd']
    )
