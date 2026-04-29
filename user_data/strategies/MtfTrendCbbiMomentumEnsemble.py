"""MtfTrendCbbiMomentumEnsemble — Ensemble CBBI Momentum Strategy

Combines 3 parameter variants with voting to reduce overfitting.

Variant 1: EXIT_THRESHOLD=-0.020 (conservative)
Variant 2: EXIT_THRESHOLD=-0.018 (balanced)
Variant 3: EXIT_THRESHOLD=-0.015 (aggressive)

Entry: ≥2 variants signal entry
Exit: ≥2 variants signal exit

Parent: MtfTrendCbbiMomentumParam (R104)
Created: R105 (robustness optimization)
Status: active
"""
from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from autoq_data.cycle_bridge import merge_cbbi


class MtfTrendCbbiMomentumEnsemble(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = False
    max_open_trades = 1
    minimal_roi = {"0": 100}
    stoploss = -0.25
    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    # ---- Fixed parameters ----
    ENTRY_MOM = 3
    CB_THRESHOLD = 0.65
    EXIT_MOM = 3
    EXIT_CBBI = 0.80
    TREND_FAST = 100
    TREND_SLOW = 200

    # ---- Ensemble variants (EXIT_THRESHOLD only) ----
    VARIANT_THRESHOLDS = [-0.020, -0.018, -0.015]
    VOTE_THRESHOLD = 2  # Need ≥2 variants to agree

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.TREND_FAST)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.TREND_SLOW)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = merge_cbbi(dataframe, metadata)
        for n in [2, 3, 4, 5, 6]:
            dataframe[f"cbbi_mom_{n}d"] = dataframe["cbbi"] - dataframe["cbbi"].shift(24 * n)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        # Common conditions
        fear_subsiding = dataframe[f"cbbi_mom_{self.ENTRY_MOM}d"] > 0
        not_euphoric = dataframe["cbbi"] < self.CB_THRESHOLD
        trend_ok = dataframe["ema_fast_1d"] > dataframe["ema_slow_1d"]
        volume_ok = dataframe["volume"] > 0

        # Entry is common to all variants (same entry logic)
        # Only EXIT varies, so entry vote = all 3 agree (always 3/3)
        dataframe.loc[
            fear_subsiding & not_euphoric & trend_ok & volume_ok,
            "enter_long"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Compute exit signals for each variant
        exit_votes = 0
        for threshold in self.VARIANT_THRESHOLDS:
            confidence_falling = dataframe[f"cbbi_mom_{self.EXIT_MOM}d"] < threshold
            extreme_greed = dataframe["cbbi"] > self.EXIT_CBBI
            trend_broken = dataframe["ema_fast_1d"] < dataframe["ema_slow_1d"]

            variant_exit = confidence_falling | extreme_greed | trend_broken
            exit_votes += variant_exit.astype(int)

        # Exit if ≥2 variants agree
        dataframe.loc[
            (exit_votes >= self.VOTE_THRESHOLD) & (dataframe["volume"] > 0),
            "exit_long"
        ] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
