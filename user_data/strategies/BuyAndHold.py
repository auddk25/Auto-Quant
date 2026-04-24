"""BuyAndHold -- Baseline buy-and-hold strategy for comparison

Paradigm: passive benchmark
Hypothesis: None -- this is a baseline to measure whether active strategies
            add value over simply holding BTC and ETH.
Parent: root
Created: R18
Status: active (baseline)
Uses MTF: no
"""

from pandas import DataFrame

from freqtrade.strategy import IStrategy


class BuyAndHold(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    minimal_roi = {"0": 100}
    stoploss = -0.99

    trailing_stop = False
    process_only_new_candles = True

    use_exit_signal = False
    exit_profit_only = False
    ignore_roi_if_entry_signal = True

    startup_candle_count: int = 1

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe["volume"] > 0, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe
