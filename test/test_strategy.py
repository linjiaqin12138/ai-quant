from datetime import timedelta, datetime

from lib.adapter.gpt import get_agent_by_model
from lib.model import CryptoOhlcvHistory, Ohlcv
from lib.modules.notification_logger import NotificationLogger
from lib.strategys.simple_turtle import simple_turtle, Params, Context
from lib.strategys.macd_sar import macd_sar, ParamsBase, Context as MacdSarContext
from lib.strategys.boll import boll, Params as BollParams, Context as BollContext
from lib.strategys.gpt import GptStrategyDependency, gpt as gpt_strategy, Context as GptContext

from lib.utils.list import map_by
from strategy import strategy_test, StrategyTestOptions
from fake_modules.fake_notification import FakeNotification
from fake_modules.fake_db import get_fake_session
from fake_modules.fake_crypto import fake_crypto

def test_simple_turtle_stategy():
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

def test_boll_strategy():
    strategy_test(
        boll, 
        test_options=StrategyTestOptions(
            batch_count = 21,
            from_time =datetime.now() - timedelta(hours=1000),
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

def test_gpt_strategy():
    params = ParamsBase(
        money=100, 
        data_frame='1d', 
        symbol = 'DOGE/USDT'
    )
    fake_crypto.set_history(
        CryptoOhlcvHistory(
            data=[
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
            pair='DOGE/USDT', 
            frame='1d', 
            exchange='binance'
        )
    )
    fake_crypto.set_price(0.15546)
    deps = GptStrategyDependency(
        notification=NotificationLogger('Test-Strategy', FakeNotification()),
        news_summary_agent=get_agent_by_model('gpt-3.5-turbo'),
        voter_agents=map_by(['llama-3.2-90b', 'grok-2-mini', 'qwen-2-72b', 'Baichuan3-Turbo', 'gpt-4-turbo'], get_agent_by_model),
        crypto=fake_crypto,
        session=get_fake_session()
    )
    with GptContext(params = params, deps=deps) as context:
        gpt_strategy(context)
    