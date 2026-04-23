"""
RSI2Rev — Connors-style fast RSI mean reversion

Paradigm: mean-reversion
Hypothesis: BTC/ETH 1h reverts from RSI(2) < 5 extreme oversold when
            price has also broken below the BB lower band (25-period, 2.0σ).
            RSI(2) is a very fast oscillator that catches quick bounces
            MeanRevADX (RSI 20) misses.
Parent: root
Created: 2026-04-23
Status: active
"""

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy


class RSI2Rev(IStrategy):
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
        dataframe["rsi_2"] = ta.RSI(dataframe, timeperiod=2)
        bands = ta.BBANDS(dataframe, timeperiod=25, nbdevup=2.0, nbdevdn=2.0)
        dataframe["bb_lower"] = bands["lowerband"]
        dataframe["bb_middle"] = bands["middleband"]
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        condition = dataframe["close"] > dataframe["ema200"]
        condition &= dataframe["adx"] > 15
        condition &= dataframe["close"] < dataframe["bb_lower"]
        condition &= dataframe["rsi_2"] < 5
        
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit if RSI(2) > 70 (Connors exit) or price hits middle band
        exit_cond = (dataframe["rsi_2"] > 70) | (dataframe["close"] > dataframe["bb_middle"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe
