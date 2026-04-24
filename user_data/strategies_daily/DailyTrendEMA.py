"""
DailyTrendEMA -- Daily EMA crossover trend-following strategy
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
        dataframe["ema10"] = ta.EMA(dataframe, timeperiod=10)
        dataframe["ema30"] = ta.EMA(dataframe, timeperiod=30)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cross_up = (dataframe["ema10"] > dataframe["ema30"]) & (dataframe["ema10"].shift(1) <= dataframe["ema30"].shift(1))
        condition = cross_up & (dataframe["close"] > dataframe["ema200"])
        condition &= dataframe["adx"] > 15
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cross_down = (dataframe["ema10"] < dataframe["ema30"]) & (dataframe["ema10"].shift(1) >= dataframe["ema30"].shift(1))
        dataframe.loc[cross_down, "exit_long"] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        if current_profit >= self.tp2_profit:
            return "tp2_50pct_profit"
        if current_profit >= self.tp1_profit:
            return "tp1_20pct_profit"
        return None

