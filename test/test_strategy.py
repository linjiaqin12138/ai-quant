import pytest
from datetime import timedelta, datetime

from lib.model import CryptoOhlcvHistory, Ohlcv
from lib.utils.list import map_by
from lib.utils.time import dt_to_ts
from lib.adapter.gpt import get_agent_by_model
from lib.modules.notification_logger import NotificationLogger
from lib.strategys.simple_turtle import simple_turtle, Params, Context
from lib.strategys.macd_sar import macd_sar, ParamsBase, Context as MacdSarContext
from lib.strategys.boll import boll, Params as BollParams, Context as BollContext
from lib.strategys.gpt_powerd.gpt_crypto_trade import GptStrategyDependency, gpt as gpt_strategy, Context as GptContext, OtherDataFetcherAbstract, GptStrategyParams

from strategy import strategy_test, StrategyTestOptions
from fake_modules.fake_notification import FakeNotification
from fake_modules.fake_db import get_fake_session, fake_kv_store_auto_commit
from fake_modules.fake_exchange_proxy import fake_exchange
from fake_modules.fake_news import fakenews
from fake_modules.fake_gpt import fake_gpt

@pytest.mark.skip(reason="Temporarily disabled for devselopment")
def test_simple_turtle_strategy():
    strategy_test(
        simple_turtle, 
        test_options=StrategyTestOptions(
            batch_count = 21,
            from_time =datetime.now() - timedelta(days=300),
            end_time = datetime.now(),
            draw = {'enabled': True }
        ),
        params = Params(
            money=100,
            symbol='ETH/USDT',
            data_frame='1d',
            min_window=20,
            max_window=20,
            max_retrieval=0.1,
            max_buy_round=2
        ),
        contextClass = Context
    )

@pytest.mark.skip(reason="Temporarily disabled for development")
def test_macd_sar_strategy():
    strategy_test(
        macd_sar, 
        test_options=StrategyTestOptions(
            batch_count = 35,
            from_time =datetime.now() - timedelta(hours=400),
            end_time = datetime.now(),
            draw = {
                'enabled': True,
                'indicators': {
                    'macd': True,
                    'sar': True,
                    # 'boll': True
                }
            }
        ),
        params = ParamsBase(
            money=100,
            symbol='BAKE/USDT',
            data_frame='1h',
        ),
        contextClass = MacdSarContext
    )

@pytest.mark.skip(reason="Temporarily disabled for development")
def test_boll_strategy():
    strategy_test(
        boll, 
        test_options=StrategyTestOptions(
            batch_count = 21,
            from_time =datetime.now() - timedelta(hours=300),
            end_time = datetime.now() - timedelta(hours=0),
            draw = {
                'enabled': True,
                'indicators': {
                    # 'macd': True,
                    # 'sar': True,
                    'boll': True
                }
            }
        ),
        params = BollParams(
            money=100,
            symbol='TRB/USDT',
            data_frame='1h',
            max_retrieval = 0.1
        ),
        contextClass = BollContext
    )

@pytest.mark.skip(reason="Temporarily disabled for development")
def test_gpt_strategy():
    params = GptStrategyParams(
        money=100, 
        data_frame='1d', 
        symbol = 'DOGE/USDT',
        strategy_prefer="中长期投资",
        risk_prefer="风险喜好型"
    )
    fake_exchange.set_curr_data(
        CryptoOhlcvHistory(
            data=[
                Ohlcv(timestamp=datetime(2024, 8, 29, 8, 0), open=0.09965, high=0.10259, low=0.09827, close=0.10037, volume=415351459.0), 
                Ohlcv(timestamp=datetime(2024, 8, 30, 8, 0), open=0.10037, high=0.10315, low=0.09697, close=0.10177, volume=628171409.0), 
                Ohlcv(timestamp=datetime(2024, 8, 31, 8, 0), open=0.10177, high=0.10239, low=0.10035, close=0.10128, volume=261630981.0), 
                Ohlcv(timestamp=datetime(2024, 9, 1, 8, 0), open=0.10128, high=0.10153, low=0.09388, close=0.09509, volume=440544625.0), 
                Ohlcv(timestamp=datetime(2024, 9, 2, 8, 0), open=0.09508, high=0.09992, low=0.09409, close=0.09912, volume=456484773.0), 
                Ohlcv(timestamp=datetime(2024, 9, 3, 8, 0), open=0.09912, high=0.10081, low=0.09639, close=0.09677, volume=353919096.0),
                Ohlcv(timestamp=datetime(2024, 9, 4, 8, 0), open=0.09678, high=0.09951, low=0.09184, close=0.098, volume=657720121.0), 
                Ohlcv(timestamp=datetime(2024, 9, 5, 8, 0), open=0.09799, high=0.09917, low=0.096, close=0.09842, volume=407742111.0), 
                Ohlcv(timestamp=datetime(2024, 9, 6, 8, 0), open=0.09842, high=0.09944, low=0.08893, close=0.09254, volume=1019311885.0), 
                Ohlcv(timestamp=datetime(2024, 9, 7, 8, 0), open=0.09255, high=0.0957, low=0.09175, close=0.09539, volume=436400943.0), 
                Ohlcv(timestamp=datetime(2024, 9, 8, 8, 0), open=0.0954, high=0.09699, low=0.09383, close=0.09616, volume=376614257.0), 
                Ohlcv(timestamp=datetime(2024, 9, 9, 8, 0), open=0.09616, high=0.10495, low=0.09571, close=0.10376, volume=896750540.0), 
                Ohlcv(timestamp=datetime(2024, 9, 10, 8, 0), open=0.10375, high=0.1046, low=0.10153, close=0.1028, volume=451668592.0), 
                Ohlcv(timestamp=datetime(2024, 9, 11, 8, 0), open=0.10279, high=0.10305, low=0.09785, close=0.10131, volume=496147874.0), 
                Ohlcv(timestamp=datetime(2024, 9, 12, 8, 0), open=0.10132, high=0.10334, low=0.10044, close=0.10269, volume=469727509.0), 
                Ohlcv(timestamp=datetime(2024, 9, 13, 8, 0), open=0.10269, high=0.10857, low=0.10179, close=0.10696, volume=885331769.0), 
                Ohlcv(timestamp=datetime(2024, 9, 14, 8, 0), open=0.10695, high=0.1077, low=0.1043, close=0.1054, volume=588837803.0), 
                Ohlcv(timestamp=datetime(2024, 9, 15, 8, 0), open=0.1054, high=0.10642, low=0.10212, close=0.10281, volume=454265265.0), 
                Ohlcv(timestamp=datetime(2024, 9, 16, 8, 0), open=0.1028, high=0.10324, low=0.09834, close=0.09964, volume=543744800.0), 
                Ohlcv(timestamp=datetime(2024, 9, 17, 8, 0), open=0.09965, high=0.10266, low=0.0987, close=0.10112, volume=488721301.0), 
                Ohlcv(timestamp=datetime(2024, 9, 18, 8, 0), open=0.10111, high=0.10388, low=0.09932, close=0.10385, volume=549809619.0), 
                Ohlcv(timestamp=datetime(2024, 9, 19, 8, 0), open=0.10384, high=0.10713, low=0.10343, close=0.10499, volume=676116886.0), 
                Ohlcv(timestamp=datetime(2024, 9, 20, 8, 0), open=0.10498, high=0.10749, low=0.1036, close=0.10555, volume=633811834.0), 
                Ohlcv(timestamp=datetime(2024, 9, 21, 8, 0), open=0.10555, high=0.11049, low=0.10404, close=0.10993, volume=543908991.0), 
                Ohlcv(timestamp=datetime(2024, 9, 22, 8, 0), open=0.10994, high=0.10998, low=0.10378, close=0.10633, volume=432001443.0), 
                Ohlcv(timestamp=datetime(2024, 9, 23, 8, 0), open=0.10632, high=0.10919, low=0.1041, close=0.10807, volume=646437650.0), 
                Ohlcv(timestamp=datetime(2024, 9, 24, 8, 0), open=0.10807, high=0.11066, low=0.10676, close=0.10979, volume=747792653.0), 
                Ohlcv(timestamp=datetime(2024, 9, 25, 8, 0), open=0.10977, high=0.11115, low=0.10801, close=0.10849, volume=722241605.0), 
                Ohlcv(timestamp=datetime(2024, 9, 26, 8, 0), open=0.10851, high=0.1207, low=0.10698, close=0.11818, volume=1639288337.0), 
                Ohlcv(timestamp=datetime(2024, 9, 27, 8, 0), open=0.11817, high=0.12873, low=0.11698, close=0.12351, volume=1623183646.0), 
                Ohlcv(timestamp=datetime(2024, 9, 28, 8, 0), open=0.12352, high=0.1321, low=0.1201, close=0.12806, volume=1709881942.0), 
                Ohlcv(timestamp=datetime(2024, 9, 29, 8, 0), open=0.12807, high=0.13044, low=0.12435, close=0.12438, volume=919118406.0), 
                Ohlcv(timestamp=datetime(2024, 9, 30, 8, 0), open=0.12438, high=0.12466, low=0.11325, close=0.11421, volume=1091853755.0), 
                Ohlcv(timestamp=datetime(2024, 10, 1, 8, 0), open=0.11421, high=0.11935, low=0.1026, close=0.10685, volume=1779737388.0), 
                Ohlcv(timestamp=datetime(2024, 10, 2, 8, 0), open=0.10686, high=0.10951, low=0.10223, close=0.10462, volume=1041484705.0), 
                Ohlcv(timestamp=datetime(2024, 10, 3, 8, 0), open=0.10462, high=0.1068, low=0.10108, close=0.10507, volume=990157071.0), 
                Ohlcv(timestamp=datetime(2024, 10, 4, 8, 0), open=0.10506, high=0.11059, low=0.10475, close=0.10924, volume=814968617.0), 
                Ohlcv(timestamp=datetime(2024, 10, 5, 8, 0), open=0.10924, high=0.11025, low=0.10747, close=0.1094, volume=398463760.0), 
                Ohlcv(timestamp=datetime(2024, 10, 6, 8, 0), open=0.10941, high=0.11291, low=0.10839, close=0.11159, volume=470748830.0), 
                Ohlcv(timestamp=datetime(2024, 10, 7, 8, 0), open=0.11159, high=0.11547, low=0.10823, close=0.10841, volume=1181346500.0), 
                Ohlcv(timestamp=datetime(2024, 10, 8, 8, 0), open=0.10841, high=0.10986, low=0.10523, close=0.10709, volume=680791688.0), 
                Ohlcv(timestamp=datetime(2024, 10, 9, 8, 0), open=0.10709, high=0.11153, low=0.10608, close=0.10794, volume=791794301.0), 
                Ohlcv(timestamp=datetime(2024, 10, 10, 8, 0), open=0.10795, high=0.10865, low=0.10311, close=0.10603, volume=713401352.0), 
                Ohlcv(timestamp=datetime(2024, 10, 11, 8, 0), open=0.10603, high=0.11144, low=0.10566, close=0.11077, volume=595969049.0), 
                Ohlcv(timestamp=datetime(2024, 10, 12, 8, 0), open=0.11077, high=0.11219, low=0.10933, close=0.11138, volume=415506248.0), 
                Ohlcv(timestamp=datetime(2024, 10, 13, 8, 0), open=0.11138, high=0.11211, low=0.10864, close=0.1114, volume=478777808.0), 
                Ohlcv(timestamp=datetime(2024, 10, 14, 8, 0), open=0.1114, high=0.11771, low=0.10931, close=0.11669, volume=1252447368.0), 
                Ohlcv(timestamp=datetime(2024, 10, 15, 8, 0), open=0.11669, high=0.11932, low=0.11016, close=0.11748, volume=1635590225.0),
                Ohlcv(timestamp=datetime(2024, 10, 16, 8, 0), open=0.11748, high=0.12999, low=0.1158, close=0.12573, volume=3073408118.0),
                Ohlcv(timestamp=datetime(2024, 10, 17, 8, 0), open=0.12574, high=0.131, low=0.12048, close=0.12967, volume=1921830268.0),
                Ohlcv(timestamp=datetime(2024, 10, 18, 8, 0), open=0.12967, high=0.14083, low=0.12952, close=0.13716, volume=2574606384.0), 
                Ohlcv(timestamp=datetime(2024, 10, 19, 8, 0), open=0.13718, high=0.147, low=0.13702, close=0.14407, volume=2065754362.0), 
                Ohlcv(timestamp=datetime(2024, 10, 20, 8, 0), open=0.14408, high=0.14573, low=0.13721, close=0.14214, volume=1498968992.0), 
                Ohlcv(timestamp=datetime(2024, 10, 21, 8, 0), open=0.14214, high=0.14975, low=0.13816, close=0.14367, volume=2235756592.0), 
                Ohlcv(timestamp=datetime(2024, 10, 22, 8, 0), open=0.14364, high=0.14849, low=0.1365, close=0.1397, volume=1689968224.0), 
                Ohlcv(timestamp=datetime(2024, 10, 23, 8, 0), open=0.1397, high=0.14101, low=0.13312, close=0.13997, volume=1447606402.0), 
                Ohlcv(timestamp=datetime(2024, 10, 24, 8, 0), open=0.13998, high=0.14384, low=0.1363, close=0.14188, volume=1212204102.0), 
                Ohlcv(timestamp=datetime(2024, 10, 25, 8, 0), open=0.14189, high=0.14277, low=0.12779, close=0.13161, volume=1516604558.0), 
                Ohlcv(timestamp=datetime(2024, 10, 26, 8, 0), open=0.13161, high=0.13822, low=0.13071, close=0.13747, volume=766435162.0), 
                Ohlcv(timestamp=datetime(2024, 10, 27, 8, 0), open=0.13747, high=0.14631, low=0.13607, close=0.14426, volume=1098602934.0), 
                Ohlcv(timestamp=datetime(2024, 10, 28, 8, 0), open=0.14427, high=0.16261, low=0.14115, close=0.16146, volume=3223861267.0), 
                Ohlcv(timestamp=datetime(2024, 10, 29, 8, 0), open=0.16145, high=0.1798, low=0.16054, close=0.17586, volume=3867989341.0), 
                Ohlcv(timestamp=datetime(2024, 10, 30, 8, 0), open=0.17586, high=0.17789, low=0.16447, close=0.16828, volume=2167415553.0), 
                Ohlcv(timestamp=datetime(2024, 10, 31, 8, 0), open=0.16828, high=0.17364, low=0.15646, close=0.16164, volume=2005209273.0), 
                Ohlcv(timestamp=datetime(2024, 11, 1, 8, 0), open=0.16164, high=0.169, low=0.15415, close=0.15916, volume=2339768574.0), 
                Ohlcv(timestamp=datetime(2024, 11, 2, 8, 0), open=0.15917, high=0.16372, low=0.15546, close=0.15955, volume=1264695204.0)
            ], 
            symbol='DOGE/USDT', 
            frame='1d', 
            exchange='binance'
        )
    )
    fake_exchange.set_curr_price(0.15546)
    fake_exchange.set_curr_time(datetime(2024, 11, 3, 8, 1))
    fake_gpt.set_reply("""
以下是加密货币新闻的总结，特别关注对DOGE有影响的内容：

1. **市场动态**：今日恐慌与贪婪指数为74，表明市场处于贪婪状态。BTC突破69500美元，ETH突破2500美元，而AAVE突破140美元。主流加密货币的行情显示，市场整体呈上涨趋势，可能会对DOGE产生正面影响。

2. **宏观经济数据**：美国10月非农就业数据低于预期，导致美元指数反弹并重回104水平。这一宏观经济数据可能会影响加密货币市场的整体情绪，间接影响DOGE的价格。

3. **政策变化**：中国人民银行副行长陆磊表示，比特币越接近资产则距离广泛流通的货币越遥远。这一言论反映了官方对于加密货币的态度，可能会对市场产生一定影响，包括DOGE在内的加密货币可能会受到政策导向的影响。

4. **国际局势**：保守党新领袖Kemi Badenoch当选，虽然该党以支持加密货币而闻名，但Badenoch在加密货币方面并不是很活跃。这一政治变动可能会对英国乃至全球的加密货币政策产生影响，间接影响DOGE的价格。

5. **DOGE币相关新闻**：本次提供的新闻中未提及直接关于DOGE的具体新闻，但上述市场动态、政策变化、国际局势等因素都可能间接影响DOGE的价格。

6. **DOGE项目的最新进展**：本次提供的新闻中未提及关于DOGE项目的最新进展。通常情况下，DOGE项目的更新、合作伙伴关系的建立或者社区活动等都会直接影响DOGE的价格和市场表现。

综上所述，虽然本次新闻摘要中没有直接关于DOGE的新闻，但市场动态、宏观经济数据、政策变化、国际局势等因素都可能间接影响DOGE的价格。投资者应密切关注这些因素的发展，以便更好地把握投资机会。
""")
    fakenews.set_news("cointime", [])
    fake_kv_store_auto_commit.set(
        'DOGE/USDT_1d_100_GPT',
        {
            "account_usdt_amount": 120.68, 
            "account_coin_amount": 0.222, 
            "operation_history": [
                {
                    "timestamp": dt_to_ts(datetime(2024, 10, 16, 0, 1, 3)),  
                    "price": 0.11753,
                    
                    "action": "buy",
                    "amount": 84.915,
                    "cost": 9.99005,
                    "remaining_usdt": 20.0347,
                    "remaining_coin": 703.296,
                    "position_ratio": 0.8,
                    "summary": "技术指标良好建仓"
                },
                {
                    "timestamp": dt_to_ts(datetime(2024, 10, 18, 0, 1, 20)), 
                    "price": 0.12971,
                    "action": "sell",
                    "amount": 703.0,
                    "cost": 91.27731613,
                    "remaining_usdt": 111.31201613,
                    "remaining_coin": 0.296,
                    "position_ratio": 0.003,
                    "summary": "获利了结大部分仓位"
                },
                {
                    "timestamp": dt_to_ts(datetime(2024, 10, 19, 0, 1, 8)), 
                    "price": 0.13724,
                    "action": "buy",
                    "amount": 727.272,
                    "cost": 99.91072,
                    "remaining_usdt": 11.401296130000006,
                    "remaining_coin": 727.5680000000001,
                    "position_ratio": 0.89,
                    "summary": "市场走强重新建仓"
                },
                {
                    "timestamp": dt_to_ts(datetime(2024, 10, 22, 0, 1, 12)),
                    "price": 0.14395,
                    "action": "sell",
                    "amount": 363.0,
                    "cost": 52.30610385,
                    "remaining_usdt": 63.707399980000005,
                    "remaining_coin": 364.5680000000001,
                    "position_ratio": 0.45,
                    "summary": "减仓一半锁定利润"
                },
                {
                    "timestamp": dt_to_ts(datetime(2024, 10, 23, 0, 2, 3)),
                    "price": 0.13989,
                    "action": "sell",
                    "amount": 364.0,
                    "cost": 50.970879960000005,
                    "remaining_usdt": 114.67827994000001,
                    "remaining_coin": 0.5680000000000973,
                    "position_ratio": 0.007,
                    "summary": "清仓规避风险"
                },
                {
                    "timestamp": dt_to_ts(datetime(2024, 10, 28, 0, 1, 40)),
                    "price": 0.14431,
                    "action": "buy",
                    "amount": 345.654,
                    "cost": 49.93126,
                    "remaining_usdt": 64.747,
                    "remaining_coin": 346.22,
                    "position_ratio": 0.43,
                    "summary": "市场企稳重新进场"
                },
                {
                    "timestamp": dt_to_ts(datetime(2024, 11, 1, 0, 1, 43)),
                    "price": 0.1615,
                    "action": "sell",
                    "amount": 346.0,
                    "cost": 55.934878999999995,
                    "remaining_usdt": 120.68,
                    "remaining_coin": 0.222,
                    "position_ratio": 0.003,
                    "summary": "高位获利了结"
                }
            ]
        }
    )
    
    class FutureDataFetcher(OtherDataFetcherAbstract):
        def get_latest_futures_price_info(self, symbol: str) -> float:
            return 0.0001
        
        def get_u_base_global_long_short_account_ratio(self, symbol: str) -> float:
            return 1.9904
        
        def get_u_base_top_long_short_account_ratio(self, symbol: str) -> float:
            return 1.9976
        
        def get_u_base_top_long_short_ratio(self, symbol: str) -> float:
            return 2.6734
        
    deps = GptStrategyDependency(
        notification=NotificationLogger('Test-Strategy', FakeNotification()),
        news_summary_agent=fake_gpt,
        voter_agents=map_by(['qwen-2-72b', 'wizardlm-2-8x22b', 'lzlv-70b', 'llama-3.1-405b'], lambda m: get_agent_by_model(m)),
        exchange=fake_exchange,
        session=get_fake_session(),
        news_adapter = fakenews,
        future_data=FutureDataFetcher()
    )
    with GptContext(params = params, deps=deps) as context:
        gpt_strategy(context)
    