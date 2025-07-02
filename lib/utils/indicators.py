from dataclasses import dataclass
from typing import List
import pandas as pd
import talib
from lib.model import Ohlcv
from lib.utils.ohlcv import to_df


@dataclass(frozen=True)
class SMAIndicatorResult:
    sma: List[float]

    @property
    def sma_series(self) -> pd.Series:
        return pd.Series(self.sma)


@dataclass(frozen=True)
class RSIIndicatorResult:
    rsi: List[float]

    @property
    def rsi_series(self) -> pd.Series:
        return pd.Series(self.rsi)


@dataclass(frozen=True)
class BollingerBandsIndicatorResult:
    upperband: List[float]
    middleband: List[float]
    lowerband: List[float]

    @property
    def upperband_series(self) -> pd.Series:
        return pd.Series(self.upperband)

    @property
    def middleband_series(self) -> pd.Series:
        return pd.Series(self.middleband)

    @property
    def lowerband_series(self) -> pd.Series:
        return pd.Series(self.lowerband)


@dataclass(frozen=True)
class MACDIndicatorResult:
    macd: List[float]
    macdsignal: List[float]
    macdhist: List[float]

    @property
    def macd_series(self) -> pd.Series:
        return pd.Series(self.macd)

    @property
    def macdsignal_series(self) -> pd.Series:
        return pd.Series(self.macdsignal)

    @property
    def macdhist_series(self) -> pd.Series:
        return pd.Series(self.macdhist)

    @property
    def is_gold_cross(self) -> bool:
        macdhist = self.macdhist_series.dropna()
        return (
            not macdhist.empty and (macdhist.iloc[-1] > 0) and (macdhist.iloc[-2] < 0)
        )

    @property
    def is_dead_cross(self) -> bool:
        macdhist = self.macdhist_series.dropna()
        return (
            not macdhist.empty and (macdhist.iloc[-1] < 0) and (macdhist.iloc[-2] > 0)
        )

    @property
    def is_turn_good(self) -> bool:
        macdhist = self.macdhist_series.dropna()
        return (
            len(macdhist) >= 3
            and (macdhist.iloc[-1] - macdhist.iloc[-2] > 0)
            and (macdhist.iloc[-2] - macdhist.iloc[-3] < 0)
            and (macdhist.iloc[-1] < 0)
        )

    @property
    def is_turn_bad(self) -> bool:
        macdhist = self.macdhist_series.dropna()
        return (
            len(macdhist) >= 3
            and (macdhist.iloc[-1] - macdhist.iloc[-2] < 0)
            and (macdhist.iloc[-2] - macdhist.iloc[-3] > 0)
            and (macdhist.iloc[-1] > 0)
        )


@dataclass(frozen=True)
class StochasticOscillatorIndicatorResult:
    slowk: List[float]
    slowd: List[float]

    @property
    def slowk_series(self) -> pd.Series:
        return pd.Series(self.slowk)

    @property
    def slowd_series(self) -> pd.Series:
        return pd.Series(self.slowd)


@dataclass(frozen=True)
class ATRIndicatorResult:
    atr: List[float]

    @property
    def atr_series(self) -> pd.Series:
        return pd.Series(self.atr)


def sma_indicator(ohlcv_list: List[Ohlcv], timeperiod: int = 5) -> SMAIndicatorResult:
    """
    计算简单移动平均线（Simple Moving Average）技术指标
    :param ohlcv_list: 包含OHLCV数据的列表
    :param timeperiod: 计算SMA的时间周期长度
    :return: 包含计算结果的SMAIndicatorResult对象
    """
    df = to_df(ohlcv_list)
    df["sma"] = talib.SMA(df["close"], timeperiod=timeperiod)
    sma_series = df["sma"].dropna()
    return SMAIndicatorResult(sma=sma_series.tolist())


def rsi_indicator(ohlcv_list: List[Ohlcv], timeperiod: int = 14) -> RSIIndicatorResult:
    """
    计算相对强弱指数（Relative Strength Index）技术指标
    :param ohlcv_list: 包含OHLCV数据的列表
    :param timeperiod: 计算RSI的时间周期长度
    :return: 包含计算结果的RSIIndicatorResult对象
    """
    df = to_df(ohlcv_list)
    df["rsi"] = talib.RSI(df["close"], timeperiod=timeperiod)
    rsi_series = df["rsi"].dropna()
    return RSIIndicatorResult(rsi=rsi_series.tolist())


def bollinger_bands_indicator(
    ohlcv_list: List[Ohlcv],
    timeperiod: int = 20,
    nbdevup: float = 2.0,
    nbdevdn: float = 2.0,
) -> BollingerBandsIndicatorResult:
    """
    计算布林带（Bollinger Bands）技术指标
    :param ohlcv_list: 包含OHLCV数据的列表
    :param timeperiod: 计算布林带的时间周期长度
    :param nbdevup: 布林带上轨标准差倍数
    :param nbdevdn: 布林带下轨标准差倍数
    :return: 包含计算结果的BollingerBandsIndicatorResult对象
    """
    df = to_df(ohlcv_list)
    upperband, middleband, lowerband = talib.BBANDS(
        df["close"], timeperiod=timeperiod, nbdevup=nbdevup, nbdevdn=nbdevdn
    )
    upperband_series = pd.Series(upperband).dropna()
    middleband_series = pd.Series(middleband).dropna()
    lowerband_series = pd.Series(lowerband).dropna()
    return BollingerBandsIndicatorResult(
        upperband=upperband_series.tolist(),
        middleband=middleband_series.tolist(),
        lowerband=lowerband_series.tolist(),
    )


def macd_indicator(
    ohlcv_list: List[Ohlcv],
    fastperiod: int = 12,
    slowperiod: int = 26,
    signalperiod: int = 9,
) -> MACDIndicatorResult:
    """
    计算移动平均收敛发散指标（Moving Average Convergence Divergence）技术指标
    :param ohlcv_list: 包含OHLCV数据的列表
    :param fastperiod: 快速移动平均线计算周期
    :param slowperiod: 慢速移动平均线计算周期
    :param signalperiod: 信号线计算周期
    :return: 包含计算结果的MACDIndicatorResult对象
    """
    df = to_df(ohlcv_list)
    macd, macdsignal, macdhist = talib.MACD(
        df["close"],
        fastperiod=fastperiod,
        slowperiod=slowperiod,
        signalperiod=signalperiod,
    )
    macd_series = pd.Series(macd).dropna()
    macdsignal_series = pd.Series(macdsignal).dropna()
    macdhist_series = pd.Series(macdhist).dropna()
    return MACDIndicatorResult(
        macd=macd_series.tolist(),
        macdsignal=macdsignal_series.tolist(),
        macdhist=macdhist_series.tolist(),
    )


def stochastic_oscillator_indicator(
    ohlcv_list: List[Ohlcv],
    fastk_period: int = 14,
    slowk_period: int = 3,
    slowd_period: int = 3,
) -> StochasticOscillatorIndicatorResult:
    """
    计算随机振荡器（Stochastic Oscillator）技术指标
    :param ohlcv_list: 包含OHLCV数据的列表
    :param fastk_period: 快速随机值的计算周期
    :param slowk_period: 缓慢随机值的移动平均周期
    :param slowd_period: 缓慢随机值均线的移动平均周期
    :return: 包含计算结果的StochasticOscillatorIndicatorResult对象
    """
    df = to_df(ohlcv_list)
    slowk, slowd = talib.STOCH(
        df["high"],
        df["low"],
        df["close"],
        fastk_period=fastk_period,
        slowk_period=slowk_period,
        slowd_period=slowd_period,
    )
    slowk_series = pd.Series(slowk).dropna()
    slowd_series = pd.Series(slowd).dropna()
    return StochasticOscillatorIndicatorResult(
        slowk=slowk_series.tolist(), slowd=slowd_series.tolist()
    )


def atr_indicator(ohlcv_list: List[Ohlcv], timeperiod: int = 14) -> ATRIndicatorResult:
    """
    计算平均真实波幅（Average True Range）技术指标
    :param ohlcv_list: 包含OHLCV数据的列表
    :param timeperiod: 计算ATR的时间周期长度
    :return: 包含计算结果的ATRIndicatorResult对象
    """
    df = to_df(ohlcv_list)
    df["atr"] = talib.ATR(df["high"], df["low"], df["close"], timeperiod=timeperiod)
    atr_series = df["atr"].dropna()
    return ATRIndicatorResult(atr=atr_series.tolist())
