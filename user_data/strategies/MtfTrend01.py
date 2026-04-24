"""
MtfTrend01 -- Daily EMA trend filter + 4h BB reversion entry

Paradigm: trend-following with mean-reversion entry
Hypothesis: Entering long on 4h BB lower touch when daily trend is bullish
            (close > EMA50) captures dips within uptrends. Exit on daily
            EMA death cross (EMA40 < EMA120) or 4h RSI overbought.
Parent: root
Created: R1
Status: active
Uses MTF: yes (1d trend filter, 4h entry signal)
"""

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy, informative


class MtfTrend01(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    minimal_roi = {"0": 100}
    stoploss = -0.15

    trailing_stop = False
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    startup_candle_count: int = 200

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema40"] = ta.EMA(dataframe, timeperiod=40)
        dataframe["ema120"] = ta.EMA(dataframe, timeperiod=120)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        return dataframe

    @informative("4h")
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        bb = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe["bb_lower"] = bb["lowerband"]
        dataframe["bb_upper"] = bb["upperband"]
        dataframe["bb_mid"] = bb["middleband"]
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["close_1d"] > dataframe["ema50_1d"])
                & (dataframe["ema40_1d"] > dataframe["ema120_1d"])
                & (dataframe["close"] <= dataframe["bb_lower_4h"])
                & (dataframe["rsi_4h"] < 40)
                & (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["ema40_1d"] < dataframe["ema120_1d"])
                | (dataframe["rsi_4h"] > 75)
            ),
            "exit_long",
        ] = 1
        return dataframe
