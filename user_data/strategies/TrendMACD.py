"""
TrendMACD — MACD momentum crossover following the 200-EMA trend

Paradigm: trend-following
Hypothesis: BTC/ETH 1h exhibits persistent directional momentum after the
            MACD line crosses above its signal line, but only when price is
            above the 200-EMA (macro uptrend) and ADX confirms trend strength
            (>20). Momentum strategies should capture sustained moves that
            mean-reversion misses by design.
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
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe["macd"] = macd["macd"]
        dataframe["macdsignal"] = macd["macdsignal"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        condition = dataframe["close"] > dataframe["ema200"]
        condition &= dataframe["adx"] > 20
        condition &= dataframe["macd"] > dataframe["macdsignal"]
        condition &= dataframe["macd"].shift(1) <= dataframe["macdsignal"].shift(1)
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_cond = (dataframe["macd"] < dataframe["macdsignal"]) | (dataframe["rsi"] > 70)
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe
