"""
DailyTrendEMA -- Daily SMA crossover trend-following strategy
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

    startup_candle_count: int = 150

    tp1_profit = 0.60

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["sma50"] = ta.SMA(dataframe, timeperiod=50)
        dataframe["sma150"] = ta.SMA(dataframe, timeperiod=150)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cross_up = (dataframe["sma50"] > dataframe["sma150"]) & (dataframe["sma50"].shift(1) <= dataframe["sma150"].shift(1))
        dataframe.loc[cross_up, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cross_down = (dataframe["sma50"] < dataframe["sma150"]) & (dataframe["sma50"].shift(1) >= dataframe["sma150"].shift(1))
        dataframe.loc[cross_down, "exit_long"] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        if current_profit >= self.tp1_profit:
            return "tp1_60pct_profit"
        return None

