"""
DailyTrendEMA -- Daily Donchian breakout trend-following strategy
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
    entry_period = 55
    exit_period = 20

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["dc_upper"] = dataframe["high"].rolling(self.entry_period).max()
        dataframe["dc_lower"] = dataframe["low"].rolling(self.exit_period).min()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        condition = dataframe["close"] > dataframe["dc_upper"].shift(1)
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_cond = dataframe["close"] < dataframe["dc_lower"].shift(1)
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        if current_profit >= self.tp1_profit:
            return "tp1_60pct_profit"
        return None
