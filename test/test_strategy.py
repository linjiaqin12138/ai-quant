import pytest
from datetime import timedelta, datetime
from lib.strategys.simple_turtle import simple_turtle, Params, Context
from lib.strategys.macd_sar import macd_sar, ParamsBase, Context as MacdSarContext
from lib.strategys.boll import boll, Params as BollParams, Context as BollContext
from strategy import strategy_test, StrategyTestOptions

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