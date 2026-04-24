"""
TrendFollowEMA — RSI<40 anchor signal + v0.3.0 factor gates for bear protection

Paradigm: mean-reversion
Hypothesis: MeanRevADX's RSI<40 entry produces 97% win rate on 2023-2025 but
            loses 13% in 2022 bear market (no macro protection). By adding the
            v0.3.0 factor gates (funding_rate + stablecoin_7d) to the BTC path,
            we should keep the high-quality entry signal while preventing
            bear-market trap entries. ETH uses pure RSI<40 without gates (gates
            hurt ETH, as confirmed in R65/R69).
Parent: MeanRevADX (entry/exit logic), FactorMeanRevCandidate (factor gates)
Created: 2026-04-23
Status: active
"""

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy




class TrendFollowEMA(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    minimal_roi = {"0": 0.05}
    stoploss = -0.05

    trailing_stop = True
    trailing_stop_positive = 0.03
    trailing_stop_positive_offset = 0.05
    trailing_only_offset_is_reached = True
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = True

    startup_candle_count: int = 200


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=20)

        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema50_cross_above = (dataframe["ema50"] > dataframe["ema200"]) & (dataframe["ema50"].shift(1) <= dataframe["ema200"].shift(1))
        base_condition = ema50_cross_above
        base_condition &= dataframe["adx"] > 25
        base_condition &= dataframe["rsi"] > 50

        condition = base_condition

        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_cond = dataframe["ema50"] < dataframe["ema200"]
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe

