"""MtfTrendCycle01v2 -- Cycle Resonance + Trend Safety Exit

Paradigm: Bitcoin Cycle Timing + Trend Confirmation
Hypothesis: Cycle indicators (AHR999+CBBI) identify value zones.
            Trend indicator (SMA200) prevents holding through slow grind-downs.
            - Entry: AHR999+CBBI (cycle says cheap)
            - Exit: AHR999/CBBI overvalued OR trend broken (triple safety)
v2 fix: Added close < SMA200 as trend safety exit (R86 failed in 2026 because
        AHR999/CBBI don't detect slow -16% grinds — they're for tops/bottoms).
Parent: MtfTrendCycle01 R86
Created: R97
Status: active
"""

from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from autoq_data.cycle_bridge import merge_ahr999, merge_cbbi


class MtfTrendCycle01(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    max_open_trades = 1
    minimal_roi = {"0": 100}
    stoploss = -0.25

    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["sma200"] = ta.SMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = merge_ahr999(dataframe, metadata)
        dataframe = merge_cbbi(dataframe, metadata)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        # Cycle accumulation zone: AHR999 undervalued + CBBI confirms
        buy_cond = (
            (dataframe["ahr999"] < 0.80)
            & (dataframe["cbbi"] < 0.5)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[buy_cond, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Three exit conditions (any one triggers):
        overvalued  = dataframe["ahr999"] > 1.3      # cycle says too expensive
        euphoria    = dataframe["cbbi"] > 0.80        # market euphoria
        trend_broken = dataframe["close_1d"] < dataframe["sma200_1d"]  # trend safety (v2 fix)
        dataframe.loc[overvalued | euphoria | trend_broken, "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
