from datetime import datetime, timedelta
from typing import List, Dict
from lib.utils.list import map_by
from lib.utils.string import random_id
from lib.logger import logger
from lib.adapter.exchange.crypto_exchange.binance import BinanceExchange
from lib.adapter.gpt import get_agent_by_model
from lib.strategys.gpt_powerd.gpt_crypto_future_trade import Context, Params, Dependency, strategy, OtherOperationsApi, OrderInfo, Ohlcv, PositionRisk
from lib.adapter.database.kv_store import KeyValueStore
from lib.adapter.database.session import SqlAlchemySession
from fake_modules.fake_gpt import fake_gpt, FakeGpt
from fake_modules.fake_news import fakenews
from fake_modules.fake_db import get_fake_session
from fake_modules.fake_notification import fake_notification_logger
from lib.utils.time import dt_to_ts

class OtherOps(OtherOperationsApi):
    current_price: float = None
    current_time: datetime = datetime.now()
    history: Dict[str, List[Ohlcv]] = {
        '1d': [],
        '1h': []
    }
    position: PositionRisk = {
        'leverage': 1,
        'entryPrice': 0,
        'breakEvenPrice': 0,
        'markPrice': 0,
        'positionAmt': 0,
        'unRealizedProfit': 0,
        'liquidationPrice': 0,
        'positionSide': 'LONG',
        'notional': 0,
        'isolated': False,
        'updateTime': 0
    }
    session = get_fake_session()
    kv_store = KeyValueStore(session)

    def set_position_risk(self, position: PositionRisk):
        self.position.update(position)

    def set_current_price(self, price: float):
        self.current_price = price
    
    def set_current_time(self, time: datetime):
        self.current_time = time
    
    def set_history(self, time_frame: str, ohlcv: List[Ohlcv]):
        self.history[time_frame] = ohlcv
    
    def cancel_order(self, symbol, order_id):
        logger.info(f"Cancel Order {symbol} {order_id}")
        return
    
    def create_future_order(self, symbol, order_type, order_side, amount, postion_side, price = None, stop_price = None) -> OrderInfo:
        fake_order = {
            'symbol': symbol,
            'orderId': random_id(10),
            'status': 'NEW',
            'avgPrice': self.current_price, #均价
            'executedQty': amount,
            'cumQuote': amount * self.current_price,
            'side': order_side.upper(),
            'updateTime': dt_to_ts(self.current_time),
            'positionSide': postion_side.upper(),
            'stopPrice': stop_price,
            'origType': order_type,
            'closePosition': False
        }
        with self.session:
            self.kv_store.set(fake_order['orderId'], fake_order)
            self.session.commit()
        return fake_order
    
    def get_latest_price(self, symbol):
        return self.current_price
    
    def get_ohlcv_history(self, symbol, time_frame, limit):
        return self.history[time_frame][-limit:]
    
    def get_order(self, symbol, order_id):
        with self.session:
            return self.kv_store.get(order_id)

    def get_position_info(self, symbol, side):
        return self.position
    
    def market_future_data(self, symbol):
        return {
            'last_funding_rate': 0.00001,
            'global_long_short_account_ratio': 3,
            'top_long_short_account_ratio': 2,
            'top_long_short_ratio': 3,
        }

    def set_leverate(self, symbol, leverage):
        pass

def test_crypto_future_strategy():
    fake_other_api = OtherOps()
    fake_other_api.set_history('1d', [
        Ohlcv(timestamp=datetime(2024, 12, 31, 0, 0), open=0.31382, high=0.3289,  low=0.30909, close=0.31582, volume=4538134421.0), 
        Ohlcv(timestamp=datetime(2025, 1, 1, 0, 0),   open=0.31582, high=0.32741, low=0.3118,  close=0.32504, volume=3054929290.0), 
        Ohlcv(timestamp=datetime(2025, 1, 2, 0, 0),   open=0.32505, high=0.34483, low=0.3245,  close=0.33879, volume=5569548837.0), 
        Ohlcv(timestamp=datetime(2025, 1, 3, 0, 0),   open=0.3388,  high=0.3894,  low=0.33552, close=0.37981, volume=8541064051.0), 
        Ohlcv(timestamp=datetime(2025, 1, 4, 0, 0),   open=0.37981, high=0.39864, low=0.37632, close=0.39467, volume=7616689597.0), 
        Ohlcv(timestamp=datetime(2025, 1, 5, 0, 0),   open=0.39466, high=0.39773, low=0.37512, close=0.38219, volume=4469246852.0),
        Ohlcv(timestamp=datetime(2025, 1, 6, 0, 0),   open=0.3822,  high=0.39556, low=0.3758,  close=0.38767, volume=5611238595.0),
    ])  
    fake_other_api.set_history('1h', [
        Ohlcv(timestamp=datetime(2025, 1, 4, 12, 0), open=0.39189, high=0.39194, low=0.38414, close=0.38718, volume=394908665.0), 
        Ohlcv(timestamp=datetime(2025, 1, 4, 13, 0), open=0.38717, high=0.39499, low=0.38713, close=0.38916, volume=491559995.0), 
        Ohlcv(timestamp=datetime(2025, 1, 4, 14, 0), open=0.38916, high=0.39052, low=0.38575, close=0.38794, volume=302966781.0), 
        Ohlcv(timestamp=datetime(2025, 1, 4, 15, 0), open=0.38795, high=0.39087, low=0.38666, close=0.38782, volume=270389491.0), 
        Ohlcv(timestamp=datetime(2025, 1, 4, 16, 0), open=0.38783, high=0.388, low=0.38286, close=0.38399, volume=347575813.0), 
        Ohlcv(timestamp=datetime(2025, 1, 4, 17, 0), open=0.38399, high=0.38836, low=0.38372, close=0.38817, volume=150876967.0), 
        Ohlcv(timestamp=datetime(2025, 1, 4, 18, 0), open=0.38816, high=0.38999, low=0.38528, close=0.3884, volume=248918786.0), 
        Ohlcv(timestamp=datetime(2025, 1, 4, 19, 0), open=0.38841, high=0.39178, low=0.3878, close=0.39161, volume=197939234.0), 
        Ohlcv(timestamp=datetime(2025, 1, 4, 20, 0), open=0.39162, high=0.39165, low=0.38726, close=0.38897, volume=210389262.0), 
        Ohlcv(timestamp=datetime(2025, 1, 4, 21, 0), open=0.38896, high=0.39448, low=0.38806, close=0.39362, volume=343037251.0), 
        Ohlcv(timestamp=datetime(2025, 1, 4, 22, 0), open=0.39361, high=0.39476, low=0.39056, close=0.39199, volume=242691468.0), 
        Ohlcv(timestamp=datetime(2025, 1, 4, 23, 0), open=0.392, high=0.392, low=0.37632, close=0.37921, volume=899860574.0), 
        Ohlcv(timestamp=datetime(2025, 1, 5, 0, 0), open=0.37922, high=0.38307, low=0.379, close=0.38185, volume=352895438.0), 
        Ohlcv(timestamp=datetime(2025, 1, 5, 1, 0), open=0.38185, high=0.38509, low=0.38104, close=0.38457, volume=201719575.0), 
        Ohlcv(timestamp=datetime(2025, 1, 5, 2, 0), open=0.38457, high=0.3851, low=0.38151, close=0.38235, volume=150150560.0), 
        Ohlcv(timestamp=datetime(2025, 1, 5, 3, 0), open=0.38236, high=0.3846, low=0.38236, close=0.38389, volume=81669690.0), 
        Ohlcv(timestamp=datetime(2025, 1, 5, 4, 0), open=0.38389, high=0.38805, low=0.38312, close=0.38691, volume=162900812.0), 
        Ohlcv(timestamp=datetime(2025, 1, 5, 5, 0), open=0.38691, high=0.3928, low=0.38661, close=0.39073, volume=306889858.0), 
        Ohlcv(timestamp=datetime(2025, 1, 5, 6, 0), open=0.39074, high=0.39864, low=0.38895, close=0.39608, volume=388848036.0), 
        Ohlcv(timestamp=datetime(2025, 1, 5, 7, 0), open=0.39609, high=0.39621, low=0.39235, close=0.39467, volume=271185509.0), 
        Ohlcv(timestamp=datetime(2025, 1, 5, 8, 0), open=0.39466, high=0.39773, low=0.39181, close=0.39219, volume=287317964.0), 
        Ohlcv(timestamp=datetime(2025, 1, 5, 9, 0), open=0.39219, high=0.39392, low=0.38904, close=0.39121, volume=238321563.0), 
        Ohlcv(timestamp=datetime(2025, 1, 5, 10, 0), open=0.3912, high=0.39266, low=0.3892, close=0.38994, volume=136491437.0), 
        Ohlcv(timestamp=datetime(2025, 1, 5, 11, 0), open=0.38994, high=0.39018, low=0.38755, close=0.38854, volume=136512850.0), 
        Ohlcv(timestamp=datetime(2025, 1, 5, 12, 0), open=0.38854, high=0.39185, low=0.38792, close=0.39134, volume=207242760.0), 
        Ohlcv(timestamp=datetime(2025, 1, 5, 13, 0), open=0.39134, high=0.39165, low=0.3887, close=0.38935, volume=90271575.0), 
        Ohlcv(timestamp=datetime(2025, 1, 5, 14, 0), open=0.38935, high=0.39175, low=0.38779, close=0.38985, volume=171422912.0), 
        Ohlcv(timestamp=datetime(2025, 1, 5, 15, 0), open=0.38985, high=0.39102, low=0.38857, close=0.38964, volume=82959320.0), 
        Ohlcv(timestamp=datetime(2025, 1, 5, 16, 0), open=0.38964, high=0.38972, low=0.38222, close=0.38606, volume=406987753.0), 
        Ohlcv(timestamp=datetime(2025, 1, 5, 17, 0), open=0.38605, high=0.38668, low=0.38229, close=0.38287, volume=178757304.0), 
        Ohlcv(timestamp=datetime(2025, 1, 5, 18, 0), open=0.38286, high=0.38401, low=0.38111, close=0.38316, volume=195043769.0), 
        Ohlcv(timestamp=datetime(2025, 1, 5, 19, 0), open=0.38317, high=0.38549, low=0.38208, close=0.38217, volume=165301282.0), 
        Ohlcv(timestamp=datetime(2025, 1, 5, 20, 0), open=0.38217, high=0.38297, low=0.38023, close=0.38111, volume=207624827.0), 
        Ohlcv(timestamp=datetime(2025, 1, 5, 21, 0), open=0.3811, high=0.38336, low=0.37868, close=0.37913, volume=204969611.0), 
        Ohlcv(timestamp=datetime(2025, 1, 5, 22, 0), open=0.37914, high=0.3832, low=0.37512, close=0.38166, volume=528735979.0), 
        Ohlcv(timestamp=datetime(2025, 1, 5, 23, 0), open=0.38166, high=0.38548, low=0.38055, close=0.38345, volume=269662605.0), 
        Ohlcv(timestamp=datetime(2025, 1, 6, 0, 0), open=0.38346, high=0.38487, low=0.38126, close=0.38254, volume=150088050.0), 
        Ohlcv(timestamp=datetime(2025, 1, 6, 1, 0), open=0.38255, high=0.38329, low=0.38011, close=0.38092, volume=114212793.0), 
        Ohlcv(timestamp=datetime(2025, 1, 6, 2, 0), open=0.38091, high=0.38213, low=0.37784, close=0.38193, volume=194622138.0), 
        Ohlcv(timestamp=datetime(2025, 1, 6, 3, 0), open=0.38193, high=0.38318, low=0.38107, close=0.382, volume=92220161.0), 
        Ohlcv(timestamp=datetime(2025, 1, 6, 4, 0), open=0.38199, high=0.384, low=0.38036, close=0.38115, volume=124338516.0), 
        Ohlcv(timestamp=datetime(2025, 1, 6, 5, 0), open=0.38115, high=0.38337, low=0.38108, close=0.38226, volume=77201257.0), 
        Ohlcv(timestamp=datetime(2025, 1, 6, 6, 0), open=0.38225, high=0.38421, low=0.3809, close=0.38334, volume=87553070.0), 
        Ohlcv(timestamp=datetime(2025, 1, 6, 7, 0), open=0.38334, high=0.38489, low=0.38091, close=0.38219, volume=121387356.0), 
        Ohlcv(timestamp=datetime(2025, 1, 6, 8, 0), open=0.3822, high=0.38313, low=0.37841, close=0.37879, volume=188746429.0), 
        Ohlcv(timestamp=datetime(2025, 1, 6, 9, 0), open=0.37879, high=0.38422, low=0.3758, close=0.38288, volume=293729986.0), 
        Ohlcv(timestamp=datetime(2025, 1, 6, 10, 0), open=0.38288, high=0.38952, low=0.38219, close=0.38496, volume=493416806.0), 
        Ohlcv(timestamp=datetime(2025, 1, 6, 11, 0), open=0.38497, high=0.38763, low=0.38361, close=0.38575, volume=165095306.0), 
        Ohlcv(timestamp=datetime(2025, 1, 6, 12, 0), open=0.38576, high=0.3878, low=0.38562, close=0.38756, volume=128389753.0), 
        Ohlcv(timestamp=datetime(2025, 1, 6, 13, 0), open=0.38757, high=0.38855, low=0.38609, close=0.38659, volume=142259831.0), 
        Ohlcv(timestamp=datetime(2025, 1, 6, 14, 0), open=0.3866, high=0.38771, low=0.38248, close=0.38396, volume=216050488.0), 
        Ohlcv(timestamp=datetime(2025, 1, 6, 15, 0), open=0.38395, high=0.38485, low=0.3795, close=0.38295, volume=275790868.0), 
        Ohlcv(timestamp=datetime(2025, 1, 6, 16, 0), open=0.38295, high=0.3847, low=0.38101, close=0.38243, volume=181697411.0), 
        Ohlcv(timestamp=datetime(2025, 1, 6, 17, 0), open=0.38243, high=0.3855, low=0.3824, close=0.38549, volume=116388494.0), 
        Ohlcv(timestamp=datetime(2025, 1, 6, 18, 0), open=0.38549, high=0.38678, low=0.3836, close=0.38509, volume=170265666.0), 
        Ohlcv(timestamp=datetime(2025, 1, 6, 19, 0), open=0.38509, high=0.38833, low=0.3843, close=0.38667, volume=186333517.0), 
        Ohlcv(timestamp=datetime(2025, 1, 6, 20, 0), open=0.38667, high=0.38777, low=0.38463, close=0.3849, volume=140948082.0), 
        Ohlcv(timestamp=datetime(2025, 1, 6, 21, 0), open=0.3849, high=0.3866, low=0.38235, close=0.38592, volume=183848011.0), 
        Ohlcv(timestamp=datetime(2025, 1, 6, 22, 0), open=0.38592, high=0.39319, low=0.38173, close=0.39033, volume=652812640.0), 
        Ohlcv(timestamp=datetime(2025, 1, 6, 23, 0), open=0.39035, high=0.39199, low=0.38791, close=0.38947, volume=530140471.0), 
        Ohlcv(timestamp=datetime(2025, 1, 7, 0, 0), open=0.38948, high=0.39556, low=0.38634, close=0.38974, volume=582064563.0), 
        Ohlcv(timestamp=datetime(2025, 1, 7, 1, 0), open=0.38974, high=0.38974, low=0.38402, close=0.38762, volume=294457337.0), 
        Ohlcv(timestamp=datetime(2025, 1, 7, 2, 0), open=0.38762, high=0.39048, low=0.38607, close=0.38884, volume=175304832.0), 
        Ohlcv(timestamp=datetime(2025, 1, 7, 3, 0), open=0.38884, high=0.39099, low=0.38812, close=0.38891, volume=112799144.0), 
        Ohlcv(timestamp=datetime(2025, 1, 7, 4, 0), open=0.38891, high=0.3907, low=0.38728, close=0.38842, volume=102982605.0), 
        Ohlcv(timestamp=datetime(2025, 1, 7, 5, 0), open=0.38842, high=0.38932, low=0.3857, close=0.38643, volume=105472293.0), 
        Ohlcv(timestamp=datetime(2025, 1, 7, 6, 0), open=0.38643, high=0.38855, low=0.38605, close=0.38759, volume=76820711.0), 
        Ohlcv(timestamp=datetime(2025, 1, 7, 7, 0), open=0.38759, high=0.38795, low=0.38503, close=0.38767, volume=95423351.0), 
        Ohlcv(timestamp=datetime(2025, 1, 7, 8, 0), open=0.38768, high=0.39121, low=0.3858, close=0.38856, volume=161550153.0), 
        Ohlcv(timestamp=datetime(2025, 1, 7, 9, 0), open=0.38856, high=0.39621, low=0.38631, close=0.39571, volume=367765857.0), 
        Ohlcv(timestamp=datetime(2025, 1, 7, 10, 0), open=0.3957, high=0.3983, low=0.39095, close=0.39126, volume=413363746.0), 
        Ohlcv(timestamp=datetime(2025, 1, 7, 11, 0), open=0.39125, high=0.39266, low=0.39024, close=0.39072, volume=75887970.0),
        Ohlcv(timestamp=datetime(2025, 1, 7, 12, 0), open=0.39125, high=0.39266, low=0.39024, close=0.39072, volume=75887970.0)
    ])
    fake_other_api.set_current_time(datetime(2025, 1, 7, 13, 0))
    fake_other_api.set_current_price(0.39072)
    fake_other_api.set_position_risk({
        'leverage': 3,
        'liquidationPrice': 0.38891 * (1 + 1 * 1 / 3),
        'positionAmt': -771.39,
        "notional": 150 * 3
    })
    fakenews.set_news('cointime', [])
    fakenews.set_news('jin10', [])
    fake_voter_gpt = FakeGpt()
    # fake_voter_gpt.set_reply("""
    #     {
    #         "action": "buy_long",
    #         "leverage": 3,
    #         "cost": 100.0,
    #         "take_profit": 0.395,
    #         "stop_loss": 0.375,
    #         "summary": "短期趋势向上，结合技术指标和市场情绪，适度加仓做多。",
    #         "reason": "1. OHLCV分析：1小时K线显示价格在0.375至0.390区间震荡，近期有向上突破的迹象，成交量逐渐放大；\n2. 技术指标分析：SMA5(0.386)上穿SMA20(0.385)，RSI(57)接近中性偏强，MACD柱状图逐渐增大，KDJ显示短期内有向上动能，ATR显示波动率适中；\n3. 新闻/市场情绪分析：当前没有明显的负面新闻，市场情绪偏向乐观，多空持仓人数比为3，显示多头占优；\n4. 仓位与风险偏好分析：可用100 USDT，使用3倍杠杆开多，风险可控，适合短线操作；\n5. 止盈止损设置分析：止盈设置在0.395，止损设置在0.375，确保在波动中保护资金安全。"
    #     }
    # """)
    fake_voter_gpt.set_reply("""
{
    "action": "hold",
    "reason": ".......",
    "summary": "xxx"             
}
    """)
    params = Params(money=100, symbol = 'DOGE/USDT', risk_prefer="风险喜好型", data_frame='1h')
    deps = Dependency(
        notification=fake_notification_logger,
        news_summary_agent =fake_gpt,
        # result_voter_agents= map_by(['llama-3.1-405b'], lambda m: get_agent_by_model(m)),
        result_voter_agents = [fake_voter_gpt],
        other_operations=fake_other_api,
        session=get_fake_session(),
        news_api=fakenews
    )
    with Context(params = params, deps=deps) as context:
        strategy(context)