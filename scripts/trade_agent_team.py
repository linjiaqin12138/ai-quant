from lib.modules.strategy.strategyv2 import StrategyBase


class TradeAgent(StrategyBase):
    def __init__(self, advice_model_provider='paoluz', advice_model='byte/deepseek-r1',
                 news_summary_model_provider='paoluz', news_summary_model='gpt-4o-mini',
                 risk_prefer='风险厌恶型', strategy_prefer='中长期投资', data_fetch_amount=60):
        super().__init__()
        self.advice_model_provider = advice_model_provider
        self.advice_model = advice_model
        self.news_summary_model_provider = news_summary_model_provider
        self.news_summary_model = news_summary_model
        self.risk_prefer = risk_prefer
        self.strategy_prefer = strategy_prefer
        self._data_fetch_amount = data_fetch_amount

    def _addtional_state_parameters(self):
        return {
            'operations': []
        }
    
    def _add_operation(self, order, summary):
        operations = {}
        operations['action'] = order.side
        operations['buy_cost'] = order.get_net_cost()
        operations['sell_amount'] = order.get_net_amount()
        operations['price'] = self.current_price
        operations['position_ratio'] = (self.hold_amount * operations['price']) / (self.free_money + self.hold_amount * operations['price'])
        operations['summary'] = summary
        operations['timestamp'] = dt_to_ts(order.timestamp)
        self.state.append('operations', operations)