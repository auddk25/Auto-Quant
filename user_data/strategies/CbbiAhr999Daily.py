"""CbbiAhr999Daily — CBBI + AHR999 Daily Bottom-Fishing Strategy

Paradigm: Cycle-based bottom-fishing with dual on-chain indicators
Hypothesis: CBBI (sentiment) + AHR999 (valuation) together identify
            undervalued zones with higher accuracy than either alone.
            Daily timeframe reduces noise and extends holding periods.
Parent: CbbiMomentum (R99), Cycle01 (R86)
Created: R103
Status: active
Uses MTF: no (daily-only strategy)
"""
from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy
from autoq_data.cycle_bridge import merge_cbbi, merge_ahr999


class CbbiAhr999Daily(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1d"
    can_short = False
    max_open_trades = 1
    minimal_roi = {"0": 100}
    stoploss = -0.25
    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    # ---- Configurable parameters (set by screening script) ----
    ENTRY_MODE = "threshold"   # "threshold" | "momentum" | "hybrid"
    EXIT_MODE = "high_estimate"  # "high_estimate" | "momentum_rev" | "trend"

    # Threshold entry params
    CB_THRESHOLD = 0.35
    AHR_THRESHOLD = 0.60

    # Momentum entry params
    MOMENTUM_N = 3

    # High-estimate exit params
    EXIT_CB = 0.80
    EXIT_AHR = 1.2

    # Momentum reversal exit params
    EXIT_MOM_N = 3
    EXIT_MOM_THRESHOLD = 0.03

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = merge_cbbi(dataframe, metadata)
        dataframe = merge_ahr999(dataframe, metadata)
        # Momentum calculations
        for n in [3, 5, 7]:
            dataframe[f"cbbi_mom_{n}"] = dataframe["cbbi"] - dataframe["cbbi"].shift(n)
            dataframe[f"ahr_mom_{n}"] = dataframe["ahr999"] - dataframe["ahr999"].shift(n)
        # Trend indicators for exit mode Z
        dataframe["sma200"] = ta.SMA(dataframe, timeperiod=200)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        cbbi = dataframe["cbbi"]
        ahr = dataframe["ahr999"]
        vol_ok = dataframe["volume"] > 0

        if self.ENTRY_MODE == "threshold":
            cond = (cbbi < self.CB_THRESHOLD) & (ahr < self.AHR_THRESHOLD) & vol_ok
        elif self.ENTRY_MODE == "momentum":
            n = self.MOMENTUM_N
            cond = (dataframe[f"cbbi_mom_{n}"] > 0) & (dataframe[f"ahr_mom_{n}"] > 0) & vol_ok
        elif self.ENTRY_MODE == "hybrid":
            n = self.MOMENTUM_N
            cond = (
                (cbbi < self.CB_THRESHOLD) & (ahr < self.AHR_THRESHOLD) &
                (dataframe[f"cbbi_mom_{n}"] > 0) & vol_ok
            )
        else:
            cond = vol_ok & False  # no entry

        # Edge detection: only enter when condition transitions False → True
        cond = cond.fillna(False)
        edge = cond & ~cond.shift(1).fillna(False)
        dataframe.loc[edge, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cbbi = dataframe["cbbi"]
        ahr = dataframe["ahr999"]

        if self.EXIT_MODE == "high_estimate":
            cond = (cbbi > self.EXIT_CB) | (ahr > self.EXIT_AHR)
        elif self.EXIT_MODE == "momentum_rev":
            n = self.EXIT_MOM_N
            cond = dataframe[f"cbbi_mom_{n}"] < -self.EXIT_MOM_THRESHOLD
        elif self.EXIT_MODE == "trend":
            cond = (dataframe["close"] < dataframe["sma200"]) | (dataframe["ema50"] < dataframe["ema200"])
        else:
            cond = cbbi > 0.80  # fallback

        dataframe.loc[cond.fillna(False), "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
