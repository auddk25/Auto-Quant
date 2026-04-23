"""
WilliamsRev — Williams %R extreme oversold bounce inside 200-EMA uptrend

Paradigm: mean-reversion
Hypothesis: BTC/ETH 1h reverts from Williams %R < -80 (price near the
            N-period low in range terms) when price has broken below the
            BB lower band (25-period, 2.0σ). WilliamsR is range-based
            (highest_high - close / range) vs RSI which is momentum-based
            (up-close velocity). These two gates should fire at genuinely
            different bars: WilliamsR fires when the close is near the
            recent low in absolute range terms, not necessarily after
            sustained momentum decline.
Parent: root
Created: <fill after commit>
Status: active
"""

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy


class WilliamsRev(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    minimal_roi = {"0": 0.010}
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
        dataframe["willr"] = ta.WILLR(dataframe, timeperiod=14)
        bands = ta.BBANDS(dataframe, timeperiod=25, nbdevup=2.0, nbdevdn=2.0)
        dataframe["bb_lower"] = bands["lowerband"]
        dataframe["bb_middle"] = bands["middleband"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        condition = dataframe["close"] > dataframe["ema200"]
        condition &= dataframe["adx"] > 15
        condition &= dataframe["close"] < dataframe["bb_lower"]
        condition &= dataframe["willr"] < -80
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_cond = (dataframe["willr"] > -20) | (dataframe["close"] > dataframe["bb_middle"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe
