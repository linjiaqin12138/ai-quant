from datetime import timedelta, datetime

from lib.strategys.simple_turtle import simple_turtle, Params, Context

from strategy import strategy_test, StrategyTestOptions

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

    

    
