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

    startup_candle_count: int = 150

    tp1_profit = 0.60

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema150"] = ta.EMA(dataframe, timeperiod=150)
        atr = ta.ATR(dataframe, timeperiod=10)
        hl2 = (dataframe["high"] + dataframe["low"]) / 2
        upper = hl2 + 3.0 * atr
        lower = hl2 - 3.0 * atr
        st = upper.copy()
        direction = 1
        for i in range(1, len(dataframe)):
            if dataframe["close"].iloc[i - 1] > st.iloc[i - 1]:
                direction = 1
            elif dataframe["close"].iloc[i - 1] < st.iloc[i - 1]:
                direction = -1
            if direction == 1:
                st.iloc[i] = max(lower.iloc[i], st.iloc[i - 1]) if st.iloc[i - 1] <= dataframe["close"].iloc[i - 1] else lower.iloc[i]
            else:
                st.iloc[i] = min(upper.iloc[i], st.iloc[i - 1]) if st.iloc[i - 1] >= dataframe["close"].iloc[i - 1] else upper.iloc[i]
        dataframe["supertrend"] = st
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cross_up = (dataframe["ema50"] > dataframe["ema150"]) & (dataframe["ema50"].shift(1) <= dataframe["ema150"].shift(1))
        dataframe.loc[cross_up, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_cond = (dataframe["close"] < dataframe["supertrend"]) & (dataframe["close"].shift(1) >= dataframe["supertrend"].shift(1))
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        if current_profit >= self.tp1_profit:
            return "tp1_60pct_profit"
        return None

