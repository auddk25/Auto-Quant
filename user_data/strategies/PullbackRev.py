"""
PullbackRev — systematic pullback reversal after 3 consecutive down-closes

Paradigm: mean-reversion
Hypothesis: BTC/ETH 1h in an uptrend (EMA200) snaps back after 3+ consecutive
            lower closes that have also broken below the BB lower band (25-period,
            2.18σ). The structural gate (3 bars declining) combined with the BB
            break ensures the entry is both a confirmed pullback trend AND a
            volatility-adjusted extreme. Complements MeanRevADX (needs RSI<40)
            and StochRev (needs StochRSI<0.15) with a price-action trigger.
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
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        bands = ta.BBANDS(dataframe, timeperiod=25, nbdevup=2.18, nbdevdn=2.18)
        dataframe["bb_lower"] = bands["lowerband"]
        dataframe["bb_middle"] = bands["middleband"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        condition = dataframe["close"] > dataframe["ema200"]
        condition &= dataframe["adx"] > 15
        # price has broken below lower band (depth gate)
        condition &= dataframe["close"] < dataframe["bb_lower"]
        # structural pullback: 3 consecutive lower closes confirm the move
        condition &= dataframe["close"].shift(1) < dataframe["close"].shift(2)
        condition &= dataframe["close"].shift(2) < dataframe["close"].shift(3)
        condition &= dataframe["close"].shift(3) < dataframe["close"].shift(4)
        condition &= dataframe["rsi"] < 40
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_cond = (dataframe["rsi"] > 60) | (dataframe["close"] > dataframe["bb_middle"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe
