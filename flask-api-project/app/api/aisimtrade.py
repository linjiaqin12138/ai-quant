from datetime import datetime
from typing import List
import akshare as ak
import requests
import pandas as pd
import json
from lib.adapter.scheduler import TaskScheduler
from lib.model.news import NewsInfo
from lib.tools.agents.advice_action import advice_ashare_action, advice_crypto_action
from lib.tools.agents.summary_news import summary_ashare_news, summary_crypto_news
from lib.modules.exchange_proxy import crypto, cn_market
from lib.modules.news_proxy import news_proxy
from lib.adapter.exchange.crypto_exchange import binance
from lib.utils.list import filter_by, map_by
from lib.utils.number import remain_significant_digits
from lib.utils.string import hash_str
from lib.utils.time import days_ago, hours_ago

analasis_tasks = TaskScheduler(max_workers=5, use_process=False)
analasis_tasks.start()
binance_raw = binance.BinanceExchange(future_mode=False)

def analysis_crypto(reqBody):
    coin_name = reqBody['symbol'].replace('USDT', '').replace('/', '')
    symbol = f'{coin_name}/USDT'
    result = advice_crypto_action(
        coin_name=reqBody['symbol'].replace('USDT', '').replace('/', ''),
        ohlcv_list=crypto.get_ohlcv_history(
            symbol=symbol,
            frame='1d',
            limit=65
        ).data,
        llm_provider='paoluz',
        model=reqBody['llmSettings'][0]['model'],
        temperature=reqBody['llmSettings'][0]['temperature'],
        account_info={
            'free': reqBody['remaining'], 
            'hold_amount': reqBody['holdAmount'], 
            'hold_val': reqBody['holdAmount'] * crypto.get_current_price(f'{coin_name}/USDT')
        },
        trade_history=map_by(filter_by(reqBody['historys'], lambda x: x['action'] != 'hold'), lambda x: {
            'timestamp': x['timestamp'] * 1000,
            'action': x['action'],
            'cost': x['cost'],
            'amount': x['amount'] if x['action'] == 'sell' else x['cost'] / x['price'],
            'position_ratio': x['position_ratio'],
            'reason': x['reason'],
            'summary': x['summary']
        }),
        exchange_future_info = {
            'future_rate': binance_raw.get_latest_futures_price_info(symbol)['lastFundingRate'],
            'global_long_short_account': binance_raw.get_u_base_global_long_short_account_ratio(symbol, '15m', hours_ago(1))[-1]['longShortRatio'],
            'top_long_short_account': binance_raw.get_u_base_top_long_short_account_ratio(symbol, '15m', hours_ago(1))[-1]['longShortRatio'],
            'top_long_short_amount': binance_raw.get_u_base_top_long_short_ratio(symbol, '15m', hours_ago(1))[-1]['longShortRatio'],
        },
        related_news = summary_crypto_news(
            coin_name=coin_name,
            news_by_platform = { 
                'cointime': news_proxy.get_news_during(
                    'cointime', 
                    start=days_ago(1), 
                    end=datetime.now()
                )
            },
            llm_provider='paoluz',
            model='gpt-4o-mini',
            temperature=0.2
        ),
        risk_prefer=reqBody['riskPrefer'],
        strategy_prefer=reqBody['strategyPrefer']
    ).__dict__
    result['price'] = crypto.get_current_price(symbol)
    if result['action'] == 'buy':
        hold_amount = reqBody['holdAmount'] + result['cost'] / result['price']
        remaining = reqBody['remaining'] - result['cost']
        result['position_ratio'] = remain_significant_digits((hold_amount * result['price']) / (hold_amount * result['price'] + remaining), 2)
    elif result['action'] == 'sell':
        hold_amount = reqBody['holdAmount'] - result['amount']
        remaining = reqBody['remaining'] + result['amount'] * result['price']
        result['position_ratio'] = remain_significant_digits((hold_amount * result['price']) / (hold_amount * result['price'] + remaining), 2)
    else:
        hold_amount = reqBody['holdAmount']
        remaining = reqBody['remaining'] 
        result['position_ratio'] = remain_significant_digits((hold_amount * result['price']) / (hold_amount * result['price'] + remaining), 2)
    return result

def get_cn_stock_news(symbol: str, from_time: datetime) -> List[NewsInfo]:
    news_100_df = ak.stock_news_em(symbol=symbol)
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

def analysis_ashare(reqBody):
    ohlcv_list = cn_market.get_ohlcv_history(
        symbol=reqBody['symbol'],
        frame='1d',
        limit=65
    ).data
    caixin_news = news_proxy.get_news_during(
        'caixin',
        ohlcv_list[-1].timestamp, 
        datetime.now()
    )
    stock_news_by_eastmoney = get_cn_stock_news(reqBody['symbol'], ohlcv_list[-1].timestamp)
    df = ak.stock_individual_info_em(reqBody['symbol'])
    stock_name = df['value'].loc[df['item'] == '股票简称'].iloc[0]
    stock_business = df['value'].loc[df['item'] == '行业'].iloc[0]
    stock_type = '股票'
    
    news_text = summary_ashare_news(
        stock_name = stock_name, 
        stock_code = reqBody['symbol'],
        stock_business = stock_business,
        news_by_platform = {
            'caixin': caixin_news,
            'eastmoney': stock_news_by_eastmoney
        },
        llm_provider='paoluz',
        model='gpt-4o-mini',
        temperature=reqBody['llmSettings'][0]['temperature'],
        stock_type = stock_type
    )
    result = advice_ashare_action(
        stock_name=stock_name,
        curr_price=ohlcv_list[-1].close,
        ohlcv_list=ohlcv_list,
        account_info={
            'free': reqBody['remaining'], 
            'hold_amount': reqBody['holdAmount'], 
            'hold_val': reqBody['holdAmount'] * ohlcv_list[-1].close
        },
        trade_history=map_by(filter_by(reqBody['historys'], lambda x: x['action'] != 'hold'), lambda x: {
            'timestamp': x['timestamp'] * 1000,
            'action': x['action'],
            'cost': x['cost'],
            'amount': x['amount'] if x['action'] == 'sell' else x['cost'] / x['price'],
            'position_ratio': x['position_ratio'],
            'reason': x['reason'],
            'summary': x['summary']
        }),
        related_news=news_text,
        llm_provider='paoluz',
        model=reqBody['llmSettings'][0]['model'],
        temperature=reqBody['llmSettings'][0]['temperature'],
        risk_prefer=reqBody['riskPrefer'],
        strategy_prefer=reqBody['strategyPrefer'],
        use_indicators=['sma', 'rsi', 'boll', 'macd', 'stoch', 'atr'],
        detect_ohlcv_pattern=True
    ).__dict__
    result['price'] = ohlcv_list[-1].close
    if result['action'] == 'buy':
        hold_amount = reqBody['holdAmount'] + result['cost'] / result['price']
        remaining = reqBody['remaining'] - result['cost']
        result['position_ratio'] = remain_significant_digits((hold_amount * result['price']) / (hold_amount * result['price'] + remaining), 2)
    elif result['action'] == 'sell':
        hold_amount = reqBody['holdAmount'] - result['amount']
        remaining = reqBody['remaining'] + result['amount'] * result['price']
        result['position_ratio'] = remain_significant_digits((hold_amount * result['price']) / (hold_amount * result['price'] + remaining), 2)
    else:
        hold_amount = reqBody['holdAmount']
        remaining = reqBody['remaining'] 
        result['position_ratio'] = remain_significant_digits((hold_amount * result['price']) / (hold_amount * result['price'] + remaining), 2)
    return result

def analysis_task(reqBody):
    if reqBody['market'] == 'crypto':
        result = analysis_crypto(reqBody)
    else:
        if not cn_market.is_business_day(datetime.now()):
            return None
        result = analysis_ashare(reqBody)
    print(json.dumps({
            'id': reqBody['id'],
            'market': reqBody['market'],
            'result': result
    }, ensure_ascii=False, indent=4))
    requests.post(
        reqBody['callbackUrl'],
        json={
            'id': reqBody['id'],
            'market': reqBody['market'],
            'result': result
        },
        auth=('username', 'password')  # Replace with actual username and password
    )
    return None

def req_hander(reqBody):
    import json
    print(json.dumps(reqBody, ensure_ascii=False, indent=4)) 
    """
    {
        "callbackUrl": "http://localhost:5000/ai/simtrade",
        "id": "50738043-a339-4508-bd73-4f3582088f7a",
        "market": "crypto",
        "symbol": "BTCUSDT",
        "style": "成长投资",
        "horizon": "中长期",
        "llmSettings": {
            "id": "2a2d8849-1537-42fe-b67e-2bd576e8aabc",
            "simulate_trade_info_id": "50738043-a339-4508-bd73-4f3582088f7a",
            "model": "gpt-3.5-turbo",
            "temperature": 0.2
        },
        "historys": [
            {
                "timestamp": 1744277400,
                "action": "buy",
                "cost": 5000,
                "amount": null,
                "price": 33500,
                "reason": "",
                "summary": ""
            }
            ...
        ],
        "holdAmount": 0,
        "remaining": 0
    }
    """
    analasis_tasks.register_task(analysis_task, args=[reqBody], description="分析任务")