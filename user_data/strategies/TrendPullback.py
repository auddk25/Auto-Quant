"""
TrendPullback — Trend-following pullback entry

Paradigm: Trend-following
Hypothesis: BTC/ETH 1h strong trends (ADX > 30) often have minor pullbacks 
            to the 20-period EMA. Entering when price is below EMA20 
            but above EMA200 captures the trend continuation.
Parent: root
Created: 2026-04-23
Status: active
"""

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy


class TrendPullback(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    minimal_roi = {"0": 0.02}
    stoploss = -0.04

    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.015

    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        condition = dataframe["close"] > dataframe["ema200"]
        condition &= dataframe["adx"] > 30
        condition &= dataframe["close"] < dataframe["ema20"]
        
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit if trend weakens or price breaks below EMA200
        exit_cond = (dataframe["adx"] < 25) | (dataframe["close"] < dataframe["ema200"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe
