"""MtfTrendCbbiRegimeSwitch — Market Regime Switching Strategy

Combines Ensemble CBBI with market regime detection.

Logic:
- Bull regime (EMA50 > EMA200): Full Ensemble entry (CBBI momentum + CBBI < 0.65)
- Choppy regime (EMA50 ≈ EMA200): Stricter entry (add CBBI momentum > 0.02)
- Bear regime (EMA50 < EMA200): No entry

This addresses the two remaining risks:
1. High dependency on 2024 bull market → filter out bear trades
2. Unstable consolidation performance → stricter entry in choppy

Parent: MtfTrendCbbiMomentumEnsemble (R105) + MtfTrendSmartHold
Created: R110 (combination strategy exploration)
Status: active
"""
from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
import numpy as np
from freqtrade.strategy import IStrategy
from autoq_data.cycle_bridge import merge_cbbi


class MtfTrendCbbiRegimeSwitch(IStrategy):
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
    EXIT_THRESHOLD = -0.02
    EXIT_CBBI = 0.80

    # ---- Regime Parameters ----
    REGIME_FAST = 50       # EMA50 for regime detection
    REGIME_SLOW = 200      # EMA200 for regime detection
    CHOPPY_BAND = 0.02     # ±2% band for choppy regime
    CHOPPY_MOM = 0.02      # Stronger momentum required in choppy

    # ---- Ensemble Voting ----
    VARIANT_THRESHOLDS = [-0.020, -0.018, -0.015]
    VOTE_THRESHOLD = 2

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = merge_cbbi(dataframe, metadata)
        # CBBI momentum
        for n in [2, 3, 4, 5, 6]:
            dataframe[f"cbbi_mom_{n}d"] = dataframe["cbbi"] - dataframe["cbbi"].shift(24 * n)
        # Regime detection EMAs
        dataframe["regime_fast"] = ta.EMA(dataframe, timeperiod=self.REGIME_FAST)
        dataframe["regime_slow"] = ta.EMA(dataframe, timeperiod=self.REGIME_SLOW)
        # Regime classification
        ratio = dataframe["regime_fast"] / dataframe["regime_slow"]
        dataframe["is_bull"] = ratio > (1 + self.CHOPPY_BAND)
        dataframe["is_bear"] = ratio < (1 - self.CHOPPY_BAND)
        dataframe["is_choppy"] = ~dataframe["is_bull"] & ~dataframe["is_bear"]
        # Voting for ensemble exit
        for i, threshold in enumerate(self.VARIANT_THRESHOLDS):
            dataframe[f"exit_vote_{i}"] = (
                (dataframe[f"cbbi_mom_{self.EXIT_MOM}d"] < threshold) |
                (dataframe["cbbi"] > self.EXIT_CBBI) |
                (dataframe["regime_fast"] < dataframe["regime_slow"])
            ).astype(int)
        dataframe["exit_votes"] = sum(dataframe[f"exit_vote_{i}"] for i in range(len(self.VARIANT_THRESHOLDS)))
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        # Common conditions
        fear_subsiding = dataframe[f"cbbi_mom_{self.ENTRY_MOM}d"] > 0
        not_euphoric = dataframe["cbbi"] < self.CB_THRESHOLD
        volume_ok = dataframe["volume"] > 0

        # Regime-specific entry
        # Bull: standard Ensemble entry
        bull_entry = dataframe["is_bull"] & fear_subsiding & not_euphoric
        # Choppy: require stronger momentum
        choppy_entry = dataframe["is_choppy"] & (dataframe[f"cbbi_mom_{self.ENTRY_MOM}d"] > self.CHOPPY_MOM) & not_euphoric
        # Bear: no entry

        dataframe.loc[
            (bull_entry | choppy_entry) & volume_ok,
            "enter_long"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Ensemble voting exit
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
