"""
PullbackRev — systematic pullback reversal after 3 consecutive down-closes

Paradigm: mean-reversion
Hypothesis: BTC/ETH 1h in an uptrend (EMA200) tends to snap back after 3+
            consecutive lower closes with RSI cooling below 45. This measures
            a STRUCTURAL pullback (3 declining bars) rather than extreme
            oscillator readings, catching moderate dips that neither MeanRevADX
            nor StochRev enter (those require extreme BB or oscillator levels).
Parent: root
Created: <fill after commit>
Status: active
"""

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy


class PullbackRev(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    minimal_roi = {"0": 0.008}
    stoploss = -0.04

    trailing_stop = False
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = True

    startup_candle_count: int = 200

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # macro uptrend
        condition = dataframe["close"] > dataframe["ema200"]
        condition &= dataframe["adx"] > 15
        # 3 consecutive lower closes = systematic pullback
        condition &= dataframe["close"].shift(1) < dataframe["close"].shift(2)
        condition &= dataframe["close"].shift(2) < dataframe["close"].shift(3)
        condition &= dataframe["close"].shift(3) < dataframe["close"].shift(4)
        # RSI cooling but not extreme (those go to MeanRevADX / StochRev)
        condition &= dataframe["rsi"] < 45
        condition &= dataframe["rsi"] > 25
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_cond = (dataframe["rsi"] > 60) | (dataframe["close"] > dataframe["ema20"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe
