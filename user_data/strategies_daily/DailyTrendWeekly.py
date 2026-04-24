"""
DailyTrendWeekly -- Daily EMA35/105 crossover (weekly-scale trend)
"""

from typing import Optional

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade
from datetime import datetime


class DailyTrendWeekly(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1d"
    can_short = False

    minimal_roi = {"0": 10.0}
    stoploss = -0.99

    trailing_stop = False
    use_custom_stoploss = True
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = True
    ignore_roi_if_entry_signal = True

    startup_candle_count: int = 110

    tp1_profit = 0.60

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema35"] = ta.EMA(dataframe, timeperiod=35)
        dataframe["ema105"] = ta.EMA(dataframe, timeperiod=105)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cross_up = (dataframe["ema35"] > dataframe["ema105"]) & (dataframe["ema35"].shift(1) <= dataframe["ema105"].shift(1))
        dataframe.loc[cross_up, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cross_down = (dataframe["ema35"] < dataframe["ema105"]) & (dataframe["ema35"].shift(1) >= dataframe["ema105"].shift(1))
        dataframe.loc[cross_down, "exit_long"] = 1
        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, after_fill: bool, **kwargs) -> float:
        if current_profit >= 0.30:
            return -0.05
        return self.stoploss

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        if current_profit >= self.tp1_profit:
            return "tp1_60pct_profit"
        return None
