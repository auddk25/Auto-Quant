"""
DailyTrendEMA -- Daily ADX/DI trend-following strategy
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
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema150"] = ta.EMA(dataframe, timeperiod=150)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        condition = (dataframe["plus_di"] > dataframe["minus_di"])
        condition &= (dataframe["plus_di"].shift(1) <= dataframe["minus_di"].shift(1))
        condition &= dataframe["adx"] > 20
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_cond = (dataframe["plus_di"] < dataframe["minus_di"])
        exit_cond &= (dataframe["plus_di"].shift(1) >= dataframe["minus_di"].shift(1))
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        if current_profit >= self.tp1_profit:
            return "tp1_60pct_profit"
        return None
