"""
HammerRev — Hammer candlestick reversal at BB lower band

Paradigm: mean-reversion (price-action)
Hypothesis: BTC/ETH 1h reverts when a hammer candle forms at the BB lower
            band (25-period, 2.0σ). A hammer = the candle's LOW breaks the
            band but the CLOSE recovers above it, with a lower shadow more
            than 2× the body. This is the market explicitly rejecting lower
            prices in the same hour — immediate price-action confirmation
            rather than an oscillator measuring prior-bar velocity.
            Conceptually distinct from RSI/StochRSI: those measure what
            happened over past N bars; the hammer measures THIS candle.
Parent: root
Created: <fill after commit>
Status: active
"""

from pandas import DataFrame
import numpy as np
import talib.abstract as ta

from freqtrade.strategy import IStrategy


class HammerRev(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    minimal_roi = {"0": 0.010}
    stoploss = -0.05

    trailing_stop = False
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = True

    startup_candle_count: int = 200

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        bands = ta.BBANDS(dataframe, timeperiod=25, nbdevup=2.0, nbdevdn=2.0)
        dataframe["bb_lower"] = bands["lowerband"]
        dataframe["bb_middle"] = bands["middleband"]
        # Hammer components
        dataframe["body"] = (dataframe["close"] - dataframe["open"]).abs()
        dataframe["lower_shadow"] = (
            dataframe[["open", "close"]].min(axis=1) - dataframe["low"]
        )
        dataframe["upper_shadow"] = (
            dataframe["high"] - dataframe[["open", "close"]].max(axis=1)
        )
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        condition = dataframe["close"] > dataframe["ema200"]
        condition &= dataframe["adx"] > 19
        # candle's low pierced BB lower band
        condition &= dataframe["low"] < dataframe["bb_lower"]
        # close recovered above BB lower band
        condition &= dataframe["close"] > dataframe["bb_lower"]
        # hammer: long lower shadow (>2× body), short upper shadow (<= body)
        condition &= dataframe["lower_shadow"] > 2 * dataframe["body"]
        condition &= dataframe["upper_shadow"] <= dataframe["body"]
        condition &= dataframe["body"] > 0
        condition &= dataframe["rsi"] < 45
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_cond = (dataframe["rsi"] > 60) | (dataframe["close"] > dataframe["bb_middle"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe
