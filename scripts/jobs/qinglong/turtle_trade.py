import datetime
import traceback
from typing import Literal, Optional, TypedDict

from lib.dao.data_query import get_ohclv
from lib.dao.event import get_event, set_event
from lib.dao.exchange import buy_at_market_price, get_remain_money, sell_at_market_price
from lib.notification.push.push_plus import send_push
from lib.utils.logger import logger
from lib.utils.time import curr_ts, unify_dt

TurtleContext = TypedDict(
    "TurtleContext",
    {
        "initialMoney": float,  # 初始投资多少，用来计算收益率
        "holdMoney": float,  # 手头剩下的USDT
        "roundNumber": int,  # 第几轮买入
        "initialCoin": float,  # 一开始梭哈买入能买多少，用来对比收益
        "holdCoin": float,  # 手头持有的货币,
        "latestMaxPrice": float,  # 买入期间币价最高值，用来计算最大回撤
        "maxRound": int,
        "stopDeclineRate": Optional[float],
        "minWindow": int,
        "maxWindow": int,
        "frame": Literal["1d", "1m"],
    },
)


ACTION_REASON = "TURTLE_PLAN"

cost_rate = 0.001  # 手续费固定设为 0.1%
important_message = []


def log_info(msg: str):
    logger.info(msg)
    important_message.append(msg)


def transform_to_coin_if_buy(usdt: float, coin_price: float) -> float:
    return (usdt - (usdt * cost_rate)) / coin_price


def transform_to_usdt(coin: float, coin_price: float) -> float:
    return coin_price * coin


def decline_rate(prev, after) -> float:
    return (after - prev) / prev * 100


def is_decline_over(prev, after, rate) -> bool:
    if rate == None:
        return False
    if prev == 0:
        return False
    return after < prev and abs((after - prev) / prev * 100) > rate


def turtle_trade(
    pair,
    frame="1d",
    total_money=100.0,
    max_round=1,
    min_window=20,
    max_window=20,
    stop_decline_rate=None,
):
    logger.info(
        f"Run Turtle Trade Bot for pair {pair} with max_round {max_round}, min_window {min_window}, max_window {max_window}, stop_decline_rate {stop_decline_rate}"
    )

    event_key = f"daily_turtle_trade_for_{pair}"
    context: TurtleContext | None = get_event(event_key)

    # Init Context
    if context is None:
        remain_money = get_remain_money()
        if remain_money < total_money:
            logger.info(
                f"Remain money less than {total_money} start turtle trade for {pair}, abort"
            )
            return
        log_info(f"The first time running for pair {pair}, initing context...")
        context = {
            "initialMoney": total_money,  # 用来算收益率
            "frame": frame,
            "holdMoney": total_money,
            "roundNumber": 0,
            "holdCoin": 0,
            "initialCoin": transform_to_coin_if_buy(total_money, df["close"].iloc[-1]),
            "latestMaxPrice": -1.0,
            "startTime": curr_ts(),
            "maxRound": max_round,
            "stopDeclineRate": stop_decline_rate,
            "minWindow": min_window,
            "maxWindow": max_window,
        }
        set_event(event_key, context)

    logger.info("Current Context: ")
    logger.info(context)
    # 这里开始的代码应该用context了而不是用函数传进来的参数了
    # +2这一个就是今天，今天不能算进去，因为今天刚开始还没过完，然后算滚动串口需要多一天
    df = get_ohclv(
        pair,
        context["frame"],
        limit=max(context["minWindow"], context["maxWindow"]) + 2,
    )
    assert df["timestamp"].iloc[-1].to_pydatetime() == unify_dt(
        datetime.datetime.now(), 86400
    )
    df["max_in_window"] = df["close"].rolling(window=context["maxWindow"]).max()
    df["min_in_window"] = df["close"].rolling(window=context["minWindow"]).min()
    # 无论如何都更新一下这些参数，因为我可能会中途改
    context["minWindow"] = min_window
    context["maxWindow"] = max_window
    context["maxRound"] = max_round
    context["frame"] = frame
    # initialMoney改不了，所以一开始投资多少钱就不能变，除非改数据库
    # context['initialMoney'] =
    if (
        context["latestMaxPrice"] > 0
        and context["latestMaxPrice"] < df["close"].iloc[-2]
    ):
        log_info(f'{pair}目前涨到最高: {df["close"].iloc[-2]} USDT')
        context["latestMaxPrice"] = df["close"].iloc[-2]

    # TODO Support a enum status
    if (
        df["close"].iloc[-2] > df["max_in_window"].iloc[-3]
        and context["holdMoney"] > 0.5
        and (context["maxRound"] > context["roundNumber"])
    ):
        log_info(f"{pair}买入信号出现")

        buy_per_round = context["holdMoney"] / (
            context["maxRound"] - context["roundNumber"]
        )

        context["roundNumber"] += 1

        # 预期花费
        to_spend = 0
        # 预期花费足够
        if context["holdMoney"] > buy_per_round:
            to_spend = buy_per_round
        # 余钱可能不够预期花费，有多少花多少
        else:
            to_spend = total_money
        # amount=None: 预算有多少买多少，按市价购买预算内的币
        buy_result = buy_at_market_price(
            pair, spend=to_spend, reason=ACTION_REASON, amount=None
        )

        actual_spend = buy_result["cost"]
        actual_gain_amount = buy_result["amount"]
        context["holdMoney"] -= actual_spend
        context["holdCoin"] += actual_gain_amount
        if context["latestMaxPrice"] < 0:
            context["latestMaxPrice"] = df["close"].iloc[-2]

        logger.info(
            f"Expected Spend {to_spend}, actual spend {actual_spend}, get amount coin {actual_gain_amount}"
        )
        log_info(
            f"买入价格: {buy_result['average']}, 花费 {actual_spend}, 剩余: {context['holdMoney'] }"
        )
    else:
        is_over_min_window = df["close"].iloc[-2] < df["min_in_window"].iloc[-3]
        is_decline_over_threshold = is_decline_over(
            context["latestMaxPrice"],
            df["close"].iloc[-2],
            context.get("stopDeclineRate"),
        )
        # TODO: Fix holdCoind cannot be 0 if selled coin before
        if (
            transform_to_usdt(context["holdCoin"], df["close"].iloc[-1]) > 0.5
            and is_over_min_window
            or is_decline_over_threshold
        ):
            log_info(f"{pair}卖出信号出现:")
            log_info(
                f"{pair}价格跌破过去{min_window}个周期价格"
                if is_over_min_window
                else f'最大回撤超{context.get("stopDeclineRate")}%: {round(decline_rate(context["latestMaxPrice"], df["close"].iloc[-2]), 4)}'
            )
            # 全部卖出
            sell_result = sell_at_market_price(pair, amount=None, reason=ACTION_REASON)
            context["holdCoin"] -= sell_result["amount"]
            context["holdMoney"] += sell_result["cost"]
            context["latestMaxPrice"] = -1
            context["roundNumber"] = 0

    logger.info("Turtle trade Finished, update context")
    logger.info("Final Context: ")
    logger.info(context)
    set_event(event_key, context)

    # 每周一算一下收益率
    if datetime.datetime.isoweekday(datetime.datetime.now()) == 1:
        gain = context["holdCoin"] * df["close"].iloc[-1] + context["holdMoney"]
        gain_rate = (gain - context["initialMoney"]) / context["initialMoney"] * 100
        compare_rate = (
            (context["initialCoin"] * df["close"].iloc[-1] - context["initialMoney"])
            / context["initialMoney"]
            * 100
        )
        log_info(
            f'{pair} 海龟收益率: {round(context["initialMoney"], 4)} -> {round(gain, 4)} = {round(gain_rate, 4)}%, 比较收益率: {round(compare_rate, 4)}%'
        )


# MONITOR_LIST=[
#     'BTC/USDT',
#     'ETH/USDT',
#     'SOL/USDT',
#     'DOGE/USDT'
#     'TRB/USDT'
# ]
def main():
    try:
        # 比特币不止跌，用简单海龟法则进行交易，因为价格趋势比较稳定
        turtle_trade(
            "BTC/USDT",
            frame="1d",
            total_money=100,
            max_round=1,
            min_window=20,
            max_window=20,
            stop_decline_rate=None,
        )
        # ETH设置两轮买入，止跌10，防止过大回撤
        turtle_trade(
            "ETH/USDT",
            frame="1d",
            total_money=100,
            max_round=2,
            min_window=20,
            max_window=20,
            stop_decline_rate=10,
        )
        # SOL处在历史高位，要防止一下过大回撤
        turtle_trade(
            "SOL/USDT",
            frame="1d",
            total_money=100,
            max_round=2,
            min_window=20,
            max_window=20,
            stop_decline_rate=10,
        )

        if len(important_message) > 0:
            send_push({"title": "海龟交易法报告", "content": "\n".join(important_message)})
        else:
            logger.info("No Event Need to Report")
    except Exception as e:
        logger.error(e)
        send_push({"title": "海龟交易法程序错误", "content": traceback.format_exc(chain=False)})


main()
