import talib

from ..dao.data_query import get_ohclv
from ..typedef import Scale
from ..utils.logger import logger

pre_cost = 1  # usdt
lst_usdt = 20
current_usdt = 20  # USDT
current_btc = 0

# def macd_mix_sar(pair: str, scale: Scale):


def loop():
    # 获取BTC/USDT交易对的历史K线数据
    df = get_ohclv("BTC/USDT", Scale.One_Day.value, 35)

    # 计算MACD, SAR指标
    df["macd"], df["macdSignal"], df["macdHist"] = talib.MACD(df["close"])
    df["sar"] = talib.SAR(df["high"], df["low"], acceleration=0.02, maximum=0.2)
    df["signal"] = 0  # 初始化信号列，0表示无操作
    df["position"] = 0  # 仓位状态，0表示空仓，1表示持仓
    # 买入信号：当价格从下方穿过SAR线时
    df.loc[df["close"] > df["sar"], "signal"] = 1

    # 卖出信号：当价格从上方穿过SAR线时
    df.loc[df["close"] < df["sar"], "signal"] = -1

    # 根据信号列计算仓位状态
    df.loc[df["signal"].diff() > 0, "position"] = 1
    df.loc[df["signal"].diff() < 0, "position"] = -1
    # # 查找金叉、死叉信号

    for i in range(1, len(df)):
        if df["position"].iloc[i] > 0 and current_usdt > 0:
            buy = current_usdt / df["close"].iloc[i]
            cost = buy * 0.001 * df["close"].iloc[i]
            pre_cost -= cost
            lst_usdt = current_usdt
            current_btc = buy
            logger.info(
                f"[{df['timestamp'].iloc[i]}] 花{current_usdt} USDT 买入 BTC {current_btc}，手续费 {cost} USDT"
            )
            current_usdt = 0

        elif df["position"].iloc[i] < 0 and current_btc > 0:
            sell = current_btc * df["close"].iloc[i]
            cost = sell * 0.001
            pre_cost -= cost
            current_usdt = sell
            trade_gain = current_usdt - lst_usdt
            gain_rate = trade_gain / lst_usdt * 100
            logger.info(
                f"[{df['timestamp'].iloc[i]}] 卖出 BTC {current_btc}，得到 USDT {current_usdt} 手续费 {cost} USDT 收益 {trade_gain} 收益率 {gain_rate}%"
            )
            current_btc = 0

        if pre_cost <= 0:
            logger.info("手续费耗尽")
            break

    if pre_cost:
        logger.info("手续费剩余： ", pre_cost)

    print(
        "总收益",
        (
            (current_usdt if current_usdt > 0 else current_btc * df["close"].iloc[-1])
            - 20
        )
        / 20
        * 100,
        "%",
    )
