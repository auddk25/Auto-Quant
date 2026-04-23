"""
TrendMACD — buy pullback to EMA20 inside a strong EMA triple-alignment trend

Paradigm: trend-following
Hypothesis: BTC/ETH 1h shows persistent bounces from EMA20 when all three
            EMAs (20>50>200) are aligned upward and ADX confirms trend
            strength. This captures shallow trend pullbacks rather than deep
            oversold events, complementing the deep-dip mean-reversion approach.
Parent: root
Created: 9864ab8
Status: active
"""

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy


class TrendMACD(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    minimal_roi = {"0": 0.04}
    stoploss = -0.05

    trailing_stop = False
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    startup_candle_count: int = 200

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # all EMAs aligned up (strong trend)
        condition = dataframe["ema20"] > dataframe["ema50"]
        condition &= dataframe["ema50"] > dataframe["ema200"]
        condition &= dataframe["adx"] > 20
        # price touching EMA20 from above (shallow pullback)
        condition &= dataframe["low"] <= dataframe["ema20"] * 1.002
        condition &= dataframe["close"] > dataframe["ema20"] * 0.995
        # not oversold (different from MeanRevADX)
        condition &= dataframe["rsi"] > 42
        condition &= dataframe["rsi"] < 65
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_cond = (dataframe["rsi"] > 72) | (dataframe["ema20"] < dataframe["ema50"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe
