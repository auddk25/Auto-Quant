"""MtfTrendCbbiAdaptive — Adaptive Parameter Strategy

Adjusts exit threshold based on market volatility (ATR).

Logic:
- High volatility (ATR > 1.5x avg): More sensitive exit (EXIT_THRESHOLD = -0.01)
- Normal volatility: Standard exit (EXIT_THRESHOLD = -0.02)
- Low volatility (ATR < 0.7x avg): Less sensitive exit (EXIT_THRESHOLD = -0.03)

Entry logic (unchanged from Ensemble):
- CBBI momentum > 0 (fear subsiding)
- CBBI < 0.65 (not euphoric)
- EMA100 > EMA200 (trend up)

Exit logic (adaptive):
- CBBI momentum < adaptive_threshold
- OR CBBI > 0.80 (extreme greed)
- OR EMA100 < EMA200 (trend broken)

Parent: MtfTrendCbbiMomentumEnsemble (R105)
Created: R109 (adaptive parameter exploration)
Status: active
"""
from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
import numpy as np
from freqtrade.strategy import IStrategy
from autoq_data.cycle_bridge import merge_cbbi


class MtfTrendCbbiAdaptive(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = False
    max_open_trades = 1
    minimal_roi = {"0": 100}
    stoploss = -0.25
    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    # ---- CBBI Parameters (proven) ----
    ENTRY_MOM = 3
    CB_THRESHOLD = 0.65
    EXIT_MOM = 3
    EXIT_CBBI = 0.80

    # ---- Adaptive Parameters ----
    ATR_PERIOD = 20
    ATR_HIGH_MULT = 1.5     # High volatility threshold
    ATR_LOW_MULT = 0.7      # Low volatility threshold
    EXIT_HIGH_VOL = -0.01   # More sensitive exit in high vol
    EXIT_NORMAL = -0.02     # Standard exit
    EXIT_LOW_VOL = -0.03    # Less sensitive exit in low vol

    # ---- Trend Parameters ----
    TREND_FAST = 100
    TREND_SLOW = 200

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = merge_cbbi(dataframe, metadata)
        # CBBI momentum
        for n in [2, 3, 4, 5, 6]:
            dataframe[f"cbbi_mom_{n}d"] = dataframe["cbbi"] - dataframe["cbbi"].shift(24 * n)
        # Trend EMAs
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.TREND_FAST)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.TREND_SLOW)
        # ATR for volatility
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.ATR_PERIOD)
        dataframe["atr_avg"] = dataframe["atr"].rolling(window=100).mean()
        # Adaptive exit threshold
        dataframe["exit_threshold"] = np.where(
            dataframe["atr"] > dataframe["atr_avg"] * self.ATR_HIGH_MULT,
            self.EXIT_HIGH_VOL,
            np.where(
                dataframe["atr"] < dataframe["atr_avg"] * self.ATR_LOW_MULT,
                self.EXIT_LOW_VOL,
                self.EXIT_NORMAL
            )
        )
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        fear_subsiding = dataframe[f"cbbi_mom_{self.ENTRY_MOM}d"] > 0
        not_euphoric = dataframe["cbbi"] < self.CB_THRESHOLD
        trend_ok = dataframe["ema_fast"] > dataframe["ema_slow"]
        volume_ok = dataframe["volume"] > 0

        dataframe.loc[
            fear_subsiding & not_euphoric & trend_ok & volume_ok,
            "enter_long"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Adaptive exit: use dynamic threshold
        confidence_falling = dataframe[f"cbbi_mom_{self.EXIT_MOM}d"] < dataframe["exit_threshold"]
        extreme_greed = dataframe["cbbi"] > self.EXIT_CBBI
        trend_broken = dataframe["ema_fast"] < dataframe["ema_slow"]

        dataframe.loc[
            (confidence_falling | extreme_greed | trend_broken) & (dataframe["volume"] > 0),
            "exit_long"
        ] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
