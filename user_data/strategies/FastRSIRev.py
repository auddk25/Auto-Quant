"""
FastRSIRev — Fast RSI(7) flash-crash reversal inside 200-EMA uptrend

Paradigm: mean-reversion
Hypothesis: BTC/ETH 1h reverts from RSI(7) < 20 (rapid 7-bar decline to
            deep oversold) when price has broken below BB lower band
            (25-period, 2.18σ). RSI(7) is much faster than MeanRevADX's
            RSI(20) — it fires on sharp, short flash-crash moves that
            haven't yet driven RSI(20) below 40. These are structurally
            different events: explosive single-session drops vs sustained
            multi-day selloffs. Expected to find entries MeanRevADX misses
            because the 20-period window hasn't yet registered them.
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
        bands = ta.BBANDS(dataframe, timeperiod=25, nbdevup=2.5, nbdevdn=2.5)
        dataframe["bb_lower"] = bands["lowerband"]
        dataframe["bb_middle"] = bands["middleband"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        condition = dataframe["close"] > dataframe["ema200"]
        condition &= dataframe["adx"] > 19
        condition &= dataframe["close"] < dataframe["bb_lower"]
        condition &= dataframe["rsi_fast"] < 20
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_cond = (dataframe["rsi_fast"] > 55) | (dataframe["close"] > dataframe["bb_middle"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe
