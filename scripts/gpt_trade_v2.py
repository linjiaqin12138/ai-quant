from datetime import datetime
from enum import Enum
import json
from typing import List, Literal, Optional
from dataclasses import asdict, dataclass 

import typer

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

class Mode(str, Enum):
    test = "test"
    job = "job"

@dataclass
class GptStrategyMixin:
    advice_mode_provider: str = 'paoluz'
    advice_model: str = 'byte/deepseek-r1'
    news_summary_mode_provider: str = 'paoluz'
    news_summary_model: str = 'gpt-4o-mini'
    risk_prefer: str = '风险厌恶型'
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

def main(
    symbol: str = typer.Argument(..., help="股票代码"),
    mode: Mode = typer.Option('test', help="回测或实盘模式"),
    name: str = typer.Argument(..., help="任务名称"),
    investment: float = typer.Argument(..., help="初始投资金额"),
    start_time: str = typer.Option("2025-01-01", help="回测开始时间，格式YYYY-MM-DD"),
    end_time: str = typer.Option("2025-03-01", help="回测结束时间，格式YYYY-MM-DD"),
    advice_model_provider: str = typer.Option("siliconflow", help="模型供应商"),
    advice_model: str = typer.Option("deepseek-ai/DeepSeek-V3", help="模型名"),
    news_summary_model_provider: str = typer.Option("siliconflow", help="新闻摘要模型供应商"),
    news_summary_model: str = typer.Option("THUDM/glm-4-9b-chat", help="新闻摘要模型名"),
    risk_prefer: str = typer.Option("风险喜好型", help="风险偏好"),
    strategy_prefer: str = typer.Option("低吸高抛", help="策略偏好"),
    recovery_file: Optional[str] = typer.Option("", help="回测恢复恢复文件路径"),
    result_folder: Optional[str] = typer.Option(None, help="回测结果文件夹路径")
):
    s = GptStrategy(
        advice_model_provider=advice_model_provider,
        advice_model=advice_model,
        news_summary_model_provider=news_summary_model_provider,
        news_summary_model=news_summary_model
    )
    if mode == 'test':
        s.back_test(
            datetime.strptime(start_time, "%Y-%m-%d"),
            datetime.strptime(end_time, "%Y-%m-%d"),
            name=name,
            symbol=symbol,
            investment=investment,
            risk_prefer=risk_prefer,
            strategy_prefer=strategy_prefer,
            recovery_file=recovery_file or f'{symbol}_{start_time}_{end_time}.json',
            result_folder=result_folder or f'{symbol.replace("/", "")}_{start_time}_{end_time}'
        )
    else:
        s.run(
            name = name,
            symbol = symbol,
            investment = investment
        )

if __name__ == "__main__":
    typer.run(main)