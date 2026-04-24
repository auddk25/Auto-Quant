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

    startup_candle_count: int = 120

    tp1_profit = 0.60

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema40"] = ta.EMA(dataframe, timeperiod=40)
        dataframe["ema120"] = ta.EMA(dataframe, timeperiod=120)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cross_up = (dataframe["ema40"] > dataframe["ema120"]) & (dataframe["ema40"].shift(1) <= dataframe["ema120"].shift(1))
        condition = cross_up & (dataframe["adx"] > 15)
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cross_down = (dataframe["ema40"] < dataframe["ema120"]) & (dataframe["ema40"].shift(1) >= dataframe["ema120"].shift(1))
        dataframe.loc[cross_down, "exit_long"] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        if current_profit >= self.tp1_profit:
            return "tp1_60pct_profit"
        return None

