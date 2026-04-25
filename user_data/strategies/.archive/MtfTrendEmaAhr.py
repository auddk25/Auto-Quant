"""MtfTrendEmaAhr — EMA100/200 Trend + AHR999 Valuation (Minimal Pair)

Indicators: EMA100, EMA200, AHR999 (just 3, simpler than EmaValuation)
Paradigm: Trend + Valuation = the two most orthogonal signals.

Entry:
  - EMA100 > EMA200  (trend is up)
  - AHR999 < 1.2     (not overvalued)

Exit:
  - EMA100 < EMA200  (trend reversed)
  - AHR999 > 1.5     (overvalued)

Why drop CBBI: CBBI correlates with AHR999 (both measure market temperature).
                 AHR999 is mathematically derived from price, CBBI requires API.
                 Using just AHR999 = simpler + no external API dependency.

Parent: MtfTrendEmaValuation (R94)
Created: R95
Status: active
"""
from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from autoq_data.cycle_bridge import merge_ahr999


class MtfTrendEmaAhr(IStrategy):
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
        dataframe["ema100"] = ta.EMA(dataframe, timeperiod=100)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = merge_ahr999(dataframe, metadata)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        trend_ok     = dataframe["ema100_1d"] > dataframe["ema200_1d"]
        valuation_ok = dataframe["ahr999"] < 1.2

        dataframe.loc[
            trend_ok & valuation_ok & (dataframe["volume"] > 0),
            "enter_long"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        trend_broken = dataframe["ema100_1d"] < dataframe["ema200_1d"]
        overvalued   = dataframe["ahr999"] > 1.5

        dataframe.loc[trend_broken | overvalued, "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
