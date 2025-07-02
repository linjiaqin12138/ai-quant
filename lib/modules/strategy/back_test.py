import json
import math
import os
from datetime import datetime
from typing import List, Literal, Optional, Dict

import pandas as pd
import numpy as np
import mplfinance as mpf
from tqdm import tqdm

from lib.adapter.notification.api import NotificationAbstract
from lib.model.common import Ohlcv
from lib.modules.notification_logger import NotificationLogger
from lib.modules.trade import ashare, crypto
from lib.utils.time import round_datetime_in_period, dt_to_ts
from lib.utils.ohlcv import to_df
from .state import SimpleState
from .strategyv2 import StrategyBase


class ConsulPrint(NotificationAbstract):
    def send(self, content: str, title: str = ""):
        print(f"[{title}] {content}")


class BackTest:
    def __init__(
        self,
        strategy: StrategyBase,
        start_time: datetime,
        end_time: datetime,
        name: str = None,
        recovery_file: Optional[str] = None,
        show_indicators: List[Literal["macd", "boll"]] = [],
        result_folder: str = None,
        **addtional_params: Dict,
    ):
        self.strategy = strategy
        self.start_time = start_time
        self.end_time = end_time
        self.name = name
        self.recovery_file = recovery_file
        self.show_indicators = show_indicators
        self.result_folder = result_folder

        strategy._is_test_mode = True
        strategy.logger = NotificationLogger(self.name, ConsulPrint())
        strategy.trade_ops = crypto if self.strategy.symbol.endswith("USDT") else ashare
        for param, val in addtional_params.items():
            setattr(self, param, val)

    def load_recovery_data(self):
        with open(self.recovery_file, "r", encoding="utf-8") as f:
            recovery_data = json.load(f)

        df = pd.DataFrame(recovery_data["df"])
        df_dict = recovery_data["df"]
        for item in df_dict:
            item["timestamp"] = pd.Timestamp(item["timestamp"], unit="ms")
            for key in item:
                if item[key] is None:
                    item[key] = np.nan

        df = pd.DataFrame(df_dict).set_index("timestamp")
        start_time = pd.to_datetime(recovery_data["start_time"])
        end_time = pd.to_datetime(recovery_data["end_time"])
        state = SimpleState(recovery_data["state"])
        current_idx = recovery_data["current_idx"]
        history = [Ohlcv.from_dict(hist) for hist in recovery_data["history"]]
        return df, start_time, end_time, state, current_idx, history

    def save_recovery_data(
        self,
        df: pd.DataFrame,
        state: SimpleState,
        iter_from_idx: int,
        history: List[Ohlcv],
    ):
        df_dict = df.reset_index().to_dict(orient="records")
        for item in df_dict:
            item["timestamp"] = item["timestamp"].value // 10**6
            for key in item:
                if math.isnan(item[key]):
                    item[key] = None

        recovery_data = {
            "df": df_dict,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "state": state._context,
            "symbol": self.strategy.symbol,
            "investment": self.strategy.investment,
            "current_idx": iter_from_idx,
            "history": [ohlcv.to_dict() for ohlcv in history],
        }
        with open(self.recovery_file, "w", encoding="utf-8") as f:
            json.dump(recovery_data, f, ensure_ascii=False)

    def save_results(self, df: pd.DataFrame, history: List[Ohlcv]):
        add_plot = [
            mpf.make_addplot(
                df["compaired_gain"], color="gray", panel=1, secondary_y=False
            ),
            mpf.make_addplot(
                df["strategy_gain"], color="blue", panel=1, secondary_y=False
            ),
        ]

        if df["buy_point"].any():
            add_plot.append(
                mpf.make_addplot(
                    df["buy_point"],
                    markersize=50,
                    type="scatter",
                    color="red",
                    marker="^",
                )
            )
        if df["sell_point"].any():
            add_plot.append(
                mpf.make_addplot(
                    df["sell_point"],
                    markersize=50,
                    type="scatter",
                    color="green",
                    marker="v",
                )
            )

        if "macd" in self.show_indicators:
            from lib.utils.indicators import macd_indicator

            macd = macd_indicator(history)
            macdhist_series = macd.macdhist_series.iloc[-len(df) :]
            add_plot.extend(
                [
                    mpf.make_addplot(
                        macdhist_series.where(macdhist_series >= 0),
                        type="bar",
                        panel=2,
                        color="g",
                        alpha=1,
                    ),
                    mpf.make_addplot(
                        macdhist_series.where(macdhist_series < 0),
                        type="bar",
                        panel=2,
                        color="r",
                        alpha=1,
                    ),
                ]
            )

        if "boll" in self.show_indicators:
            from lib.utils.indicators import bollinger_bands_indicator

            boll = bollinger_bands_indicator(history)
            add_plot.extend(
                [
                    mpf.make_addplot(
                        boll.lowerband_series.iloc[-len(df) :], color="red"
                    ),
                    mpf.make_addplot(
                        boll.middleband_series.iloc[-len(df) :], color="gray"
                    ),
                    mpf.make_addplot(
                        boll.upperband_series.iloc[-len(df) :], color="green"
                    ),
                ]
            )

        kwargs = {
            "type": "candle",
            "title": self.name or self.strategy.name,
            "ylabel": "Price",
            "addplot": add_plot,
            "figscale": 1.5,
            "figsize": (16, 10),
            # 'style': mpf.make_mpf_style(rc={'font.family': 'SimHei'})
        }

        # check if the result folder exists, if not create it
        if self.result_folder:
            if not os.path.exists(self.result_folder):
                os.makedirs(self.result_folder)
            symbolwithoutslash = self.strategy.symbol.replace("/", "")
            save_path = os.path.join(
                self.result_folder,
                f'{symbolwithoutslash}_{self.start_time.strftime("%Y%m%d")}_{self.end_time.strftime("%Y%m%d")}.png',
            )
            kwargs["savefig"] = save_path
            mpf.plot(df, **kwargs)
            result_csv_path = os.path.join(
                self.result_folder,
                f'{symbolwithoutslash}_{self.start_time.strftime("%Y%m%d")}_{self.end_time.strftime("%Y%m%d")}.csv',
            )
            df.to_csv(result_csv_path, index=True)
        else:
            mpf.plot(df, **kwargs)

    def run(self):
        if self.recovery_file and os.path.exists(self.recovery_file):
            df, start_time, end_time, self.strategy.state, iter_from_idx, history = (
                self.load_recovery_data()
            )
        else:
            iter_from_idx = 0
            start_time = round_datetime_in_period(self.start_time, self.strategy.frame)
            trace_back_start = self.strategy._trace_back_business_day_from(
                self.strategy._data_fetch_amount, start_time
            )
            history = self.strategy.get_ohlcv_history(
                start_time=trace_back_start, end_time=self.end_time
            )

            df = to_df(history[self.strategy._data_fetch_amount :])
            for col in ["compaired_gain", "strategy_gain", "buy_point", "sell_point"]:
                df[col] = np.nan

            self.strategy.state = SimpleState(self.strategy._init_state())
            self.strategy.state.set(
                "bt_start_amount",
                self.strategy.investment
                / history[self.strategy._data_fetch_amount].open,
            )
            self.strategy.state.set(
                "bt_test_range", [dt_to_ts(start_time), dt_to_ts(self.end_time)]
            )

        self.strategy._prepare()

        try:
            process_bar = tqdm(
                total=len(history) - self.strategy._data_fetch_amount, desc="Progress"
            )
            for idx in range(iter_from_idx, len(history)):
                iter_from_idx, current_idx = idx, idx + self.strategy._data_fetch_amount
                process_bar.update(idx - process_bar.n)
                if current_idx >= len(history):
                    break

                self.process_history_data(current_idx, history, df)
                self.strategy.state.save()

            process_bar.close()
            self.save_results(df, history)

        except (KeyboardInterrupt, Exception) as e:
            if self.recovery_file:
                self.save_recovery_data(df, self.strategy.state, iter_from_idx, history)
            raise e

    def process_history_data(
        self, current_idx: int, history: List[Ohlcv], df: pd.DataFrame
    ):
        self.strategy.state.set("bt_current_price", history[current_idx].open)
        self.strategy.state.set(
            "bt_current_time", dt_to_ts(history[current_idx].timestamp)
        )
        self.strategy.state.set("bt_observed_action", "none")
        self.strategy.state.set("bt_addtional_info", {})

        # 运行策略
        self.strategy._core(
            history[current_idx - self.strategy._data_fetch_amount : current_idx]
        )

        df.loc[history[current_idx].timestamp, "strategy_gain"] = (
            self.strategy.hold_amount * self.strategy.current_price
            + self.strategy.free_money
        )
        df.loc[history[current_idx].timestamp, "compaired_gain"] = (
            self.strategy.current_price * self.strategy.state.get("bt_start_amount")
        )

        if self.strategy.state.get("bt_observed_action") == "buy":
            df.loc[history[current_idx].timestamp, "buy_point"] = (
                self.strategy.current_price
            )
        if self.strategy.state.get("bt_observed_action") == "sell":
            df.loc[history[current_idx].timestamp, "sell_point"] = (
                self.strategy.current_price
            )
        for col in self.strategy.state.get("bt_addtional_info"):
            df.loc[history[current_idx].timestamp, col] = self.strategy.state.get(
                "bt_addtional_info"
            )[col]
