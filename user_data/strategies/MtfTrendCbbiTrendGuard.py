"""MtfTrendCbbiTrendGuard — Ensemble CBBI with Trend Guard

Adds daily SMA200 trend guard to Ensemble CBBI strategy.

Logic:
- Entry: Ensemble CBBI (3-variant voting) + daily close > SMA200
- Exit: Ensemble voting (≥2 variants)

The SMA200 filter prevents entries during bear markets,
addressing the high dependency on 2024 bull market risk.

Parent: MtfTrendCbbiMomentumEnsemble (R105) + MtfTrendBear01
Created: R110 (combination strategy exploration)
Status: active
"""
from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy
from autoq_data.cycle_bridge import merge_cbbi


class MtfTrendCbbiTrendGuard(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = False
    max_open_trades = 1
    minimal_roi = {"0": 100}
    stoploss = -0.25
    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    # ---- CBBI Parameters (from Ensemble) ----
    ENTRY_MOM = 3
    CB_THRESHOLD = 0.65
    EXIT_MOM = 3
    EXIT_CBBI = 0.80

    # ---- Trend Guard Parameters ----
    SMA_PERIOD = 200

    # ---- Ensemble Voting ----
    VARIANT_THRESHOLDS = [-0.020, -0.018, -0.015]
    VOTE_THRESHOLD = 2

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = merge_cbbi(dataframe, metadata)
        # CBBI momentum
        for n in [2, 3, 4, 5, 6]:
            dataframe[f"cbbi_mom_{n}d"] = dataframe["cbbi"] - dataframe["cbbi"].shift(24 * n)
        # Trend guard: daily SMA200
        dataframe["sma200"] = ta.SMA(dataframe, timeperiod=self.SMA_PERIOD)
        # Voting for ensemble exit
        for i, threshold in enumerate(self.VARIANT_THRESHOLDS):
            dataframe[f"exit_vote_{i}"] = (
                (dataframe[f"cbbi_mom_{self.EXIT_MOM}d"] < threshold) |
                (dataframe["cbbi"] > self.EXIT_CBBI) |
                (dataframe["close"] < dataframe["sma200"])
            ).astype(int)
        dataframe["exit_votes"] = sum(dataframe[f"exit_vote_{i}"] for i in range(len(self.VARIANT_THRESHOLDS)))
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        fear_subsiding = dataframe[f"cbbi_mom_{self.ENTRY_MOM}d"] > 0
        not_euphoric = dataframe["cbbi"] < self.CB_THRESHOLD
        trend_guard = dataframe["close"] > dataframe["sma200"]
        volume_ok = dataframe["volume"] > 0

        dataframe.loc[
            fear_subsiding & not_euphoric & trend_guard & volume_ok,
            "enter_long"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_signal = dataframe["exit_votes"] >= self.VOTE_THRESHOLD

        dataframe.loc[
            exit_signal & (dataframe["volume"] > 0),
            "exit_long"
        ] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
