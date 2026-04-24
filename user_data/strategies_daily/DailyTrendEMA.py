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
    stoploss = -0.99

    trailing_stop = False
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = True

    startup_candle_count: int = 50

    tp1_profit = 0.20
    tp2_profit = 0.50

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
        # Pullback to EMA20: low touches or dips below EMA20, close recovers above
        pullback = (dataframe["low"] <= dataframe["ema20"] * 1.01) & (dataframe["close"] > dataframe["ema20"])
        # Trend strength
        condition = uptrend & pullback & (dataframe["adx"] > 20)
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit when trend breaks: close below EMA50
        trend_break = dataframe["close"] < dataframe["ema50"]
        dataframe.loc[trend_break, "exit_long"] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        if current_profit >= self.tp2_profit:
            return "tp2_50pct_profit"
        if current_profit >= self.tp1_profit:
            return "tp1_20pct_profit"
        return None

