# -*- coding: utf-8 -*-
import json
import requests
from humps import camelize
from lib.modules.agents.market_master import SimpleTraderAgent, TradeContext, AccountInfo, TradeHistoryList
from lib.adapter.scheduler import TaskScheduler
from lib.utils.list import map_by
from lib.utils.object import remove_none
from lib.utils.number import remain_significant_digits
from app.logger import logger
from app.schemas.ai import TradeAdviceReq
from config import Config

scheduler = TaskScheduler(max_workers=5)  # 5个并发线程
scheduler.start()

def result_notification_task(callback_url: str, result: dict, id: str):
    """
    发送结果通知的任务
    """
    username, password = Config.get_callback_auth()
    rsp = requests.post(
        callback_url,
        json={
            'id': id,
            'result': result
        },
        auth=(username, password)
    )
    logger.info('Result notification response: %s', rsp.status_code)
    logger.debug('Notification response content: %s', rsp.text)
    if rsp.status_code >= 429:
        raise Exception("Failed to notify result")

def add_ai_trade_task(req: TradeAdviceReq):
    """添加AI交易任务"""
    task_id = scheduler.register_task(
        func=ai_trade,
        args=[req],
        description="AI交易建议"
    )
    logger.info("AI交易任务已添加，任务ID: %s", task_id)
    return task_id

risk_prefer_map = {
    "risk_averse": "保守型",
    "stable": "稳健型",
    "risk_seeking": "激进型"
}

strategy_prefer_map = {
    "long_term": "长期投资",
    "short_term": "短线交易",
    "buy_low_sell_high": "低买高卖",
    "trend_following": "趋势跟随"
}

def ai_trade(req: TradeAdviceReq):
    """AI交易建议"""
    logger.debug(f'ai trade handling request: {req.model_dump_json(indent=2)}')
    market_master = SimpleTraderAgent(
        risk_prefer=risk_prefer_map.get(req.risk_prefer),
        strategy_prefer=strategy_prefer_map.get(req.strategy_prefer),
        model=req.llm_settings[0].model,
        temperature=req.llm_settings[0].temperature
    )
    history: TradeHistoryList = map_by(req.historys, lambda h: h.model_dump())
    account_info: AccountInfo = {
        'free': req.remaining,
        'hold_amount': req.hold_amount
    }
    advice = market_master.give_crypto_trade_advice(TradeContext(
        symbol=req.symbol,
        account_info=account_info,
        trade_history=history
    ))
    if advice.action == 'buy':
        account_info['free'] -= advice.buy_cost
        account_info['hold_amount'] += advice.buy_cost / advice.price
    elif advice.action == 'sell':
        account_info['free'] += advice.sell_amount * advice.price
        account_info['hold_amount'] -= advice.sell_amount

    result = advice.__dict__.copy()
    result['position_ratio'] = remain_significant_digits(
        account_info['hold_amount'] * advice.price / (account_info['hold_amount'] * advice.price + account_info['free']),
        2
    )
    result = camelize(remove_none(result))
    logger.debug(f'Trade Advice Result: {json.dumps(result, indent=2, ensure_ascii=False)}')
    scheduler.register_task(
        func=result_notification_task,
        args=[req.callback_url, result, req.id],
        description="AI交易结果通知",
        retry_count=3
    )
    return result