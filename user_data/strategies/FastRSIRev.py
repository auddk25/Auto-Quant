"""
FastRSIRev — Fast RSI(7) flash-crash reversal inside 200-EMA uptrend

Paradigm: mean-reversion
Hypothesis: BTC/ETH 1h reverts from RSI(7) < 20 (rapid 7-bar decline to
            deep oversold) when price has broken below BB lower band
            (25-period, 2.18σ) AND RSI(20) is still above 30. The RSI(20)>30
            gate ensures this is a PURE FLASH CRASH that hasn't yet become a
            sustained selloff (which MeanRevADX catches via RSI(20)<40).
            This makes FastRSIRev and MeanRevADX complementary: FastRSIRev
            handles explosive single-session drops; MeanRevADX handles
            sustained multi-day selloffs.
Parent: root
Created: <fill after commit>
Status: active
"""

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy


class FastRSIRev(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    minimal_roi = {"0": 0.008}
    stoploss = -0.06

    trailing_stop = False
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = True

    startup_candle_count: int = 200

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["rsi_fast"] = ta.RSI(dataframe, timeperiod=7)
        dataframe["rsi_slow"] = ta.RSI(dataframe, timeperiod=20)
        bands = ta.BBANDS(dataframe, timeperiod=25, nbdevup=2.18, nbdevdn=2.18)
        dataframe["bb_lower"] = bands["lowerband"]
        dataframe["bb_middle"] = bands["middleband"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        condition = dataframe["close"] > dataframe["ema200"]
        condition &= dataframe["adx"] > 19
        condition &= dataframe["close"] < dataframe["bb_lower"]
        condition &= dataframe["rsi_fast"] < 20
        condition &= dataframe["rsi_slow"] > 30
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_cond = (dataframe["rsi_fast"] > 55) | (dataframe["close"] > dataframe["bb_middle"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe
