"""
MtfTrend02 -- Daily EMA trend + 4h EMA crossover momentum entry

Paradigm: pure trend-following
Hypothesis: ETH underperforms BB reversion (MtfTrend01) because it trends
            harder. A 4h EMA crossover entry (fast > slow) within a daily
            uptrend should capture momentum moves better than mean-reversion.
Parent: MtfTrend01 (fork)
Created: R3
Status: active
Uses MTF: yes (1d trend filter, 4h momentum entry)
"""

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy, informative


class MtfTrend02(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    minimal_roi = {"0": 100}
    stoploss = -0.08

    trailing_stop = False
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    startup_candle_count: int = 200

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema150"] = ta.EMA(dataframe, timeperiod=150)
        return dataframe

    @informative("4h")
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema12"] = ta.EMA(dataframe, timeperiod=12)
        dataframe["ema26"] = ta.EMA(dataframe, timeperiod=26)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema12_prev"] = dataframe["ema12"].shift(1)
        dataframe["ema26_prev"] = dataframe["ema26"].shift(1)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["close_1d"] > dataframe["ema50_1d"])
                & (dataframe["ema50_1d"] > dataframe["ema150_1d"])
                & (dataframe["ema12_4h"] > dataframe["ema26_4h"])
                & (dataframe["ema12_prev_4h"] <= dataframe["ema26_prev_4h"])
                & (dataframe["rsi_4h"] > 40)
                & (dataframe["rsi_4h"] < 70)
                & (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe["ema50_1d"] < dataframe["ema150_1d"])
                | (dataframe["ema12_4h"] < dataframe["ema26_4h"])
            ),
            "exit_long",
        ] = 1
        return dataframe

    def custom_stoploss(self, pair: str, trade, current_time, current_rate,
                        current_profit, **kwargs) -> float:
        if current_profit >= 0.30:
            return -0.05
        return self.stoploss
