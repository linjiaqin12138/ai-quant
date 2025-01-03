import pytest

from lib.adapter.gpt import get_agent_by_model
from lib.adapter.news import news
from lib.utils.list import map_by
from lib.utils.time import hours_ago
from lib.strategys.gpt_powerd.gpt_ashare_trade import Params, Dependency, Context, strategy, OtherDataFetcher

from fake_modules.fake_db import get_fake_session
from fake_modules.fake_notification import fake_notification_logger

def test_get_symbol_news():
    OtherDataFetcher(get_fake_session()).get_symbol_news("159768", hours_ago(24))

@pytest.mark.skip(reason="Temporarily disabled for development")
def test_ashare_gpt_strategy():
    params = Params(
        money=10000, 
        data_frame='1d', 
        symbol = '515060',
        strategy_prefer="中长期投资",
        risk_prefer="风险喜好型",
        news_platforms=['caixin', 'eastmoney']
    )
    # fake_exchange.set_curr_data(
    #     OhlcvHistory(
    #         data=[], 
    #         symbol='515060', 
    #         frame='1d'
    #     )
    # )
    # fake_exchange.set_curr_price(0.15546)
    # fake_exchange.set_curr_time(datetime(2024, 11, 3, 8, 1))
    # fake_kv_store_auto_commit.set('DOGE/USDT_1d_100_GPT', {})

    deps = Dependency(
        notification = fake_notification_logger,
        news_summary_gpt_agent=get_agent_by_model('paoluz-gpt-4o-mini'),
        decision_voters_gpt_agents=map_by(['paoluz-gpt-4o-mini', 'paoluz-grok-beta', 'wizardlm-2-8x22b', 'llama-3.1-405b'], lambda m: get_agent_by_model(m)),
        session=get_fake_session(),
    )
    with Context(params = params, deps=deps) as context:
        strategy(context)
    