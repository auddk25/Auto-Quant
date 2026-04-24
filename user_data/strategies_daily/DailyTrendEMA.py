"""
DailyTrendEMA -- Daily trend-following with pullback entry
"""

from typing import Optional

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade
from datetime import datetime


class DailyTrendEMA(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1d"
    can_short = False

    minimal_roi = {"0": 10.0}
    stoploss = -0.10

    trailing_stop = True
    trailing_stop_positive = 0.03
    trailing_stop_positive_offset = 0.08
    trailing_only_offset_is_reached = True
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = True

    startup_candle_count: int = 50

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Uptrend: EMA20 > EMA50, price above EMA200
        uptrend = (dataframe["ema20"] > dataframe["ema50"]) & (dataframe["close"] > dataframe["ema200"])
        # Pullback: low near EMA20, close recovers above
        pullback = (dataframe["low"] <= dataframe["ema20"] * 1.005) & (dataframe["close"] > dataframe["ema20"])
        # RSI in healthy range (not overbought, not crashing)
        rsi_ok = (dataframe["rsi"] > 40) & (dataframe["rsi"] < 65)
        condition = uptrend & pullback & rsi_ok & (dataframe["adx"] > 20)
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit when close drops below EMA20 (faster than EMA50)
        trend_break = dataframe["close"] < dataframe["ema20"]
        dataframe.loc[trend_break, "exit_long"] = 1
        return dataframe

