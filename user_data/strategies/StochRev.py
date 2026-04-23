"""
StochRev — Stochastic RSI oversold bounce inside 200-EMA uptrend

Paradigm: mean-reversion
Hypothesis: BTC/ETH 1h reverts from StochRSI < 0.15 (fast oscillator deep
            oversold) when the macro trend (EMA200) is up and ADX confirms
            the trend hasn't collapsed. StochRSI moves faster than plain RSI
            and should catch entries that RSI misses or catches too late,
            complementing MeanRevADX which uses a BB-lower price gate.
Parent: root
Created: <fill after commit>
Status: active
"""

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy


class StochRev(IStrategy):
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
        # StochRSI = stochastic applied to RSI values
        rsi = ta.RSI(dataframe, timeperiod=14)
        dataframe["rsi"] = rsi
        stoch = ta.STOCH(
            dataframe.assign(high=rsi, low=rsi, close=rsi),
            fastk_period=14, slowk_period=3, slowd_period=3,
        )
        dataframe["stoch_k"] = stoch["slowk"] / 100.0
        dataframe["stoch_d"] = stoch["slowd"] / 100.0
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        condition = dataframe["close"] > dataframe["ema200"]
        condition &= dataframe["adx"] > 15
        # StochRSI oversold and K crossing above D
        condition &= dataframe["stoch_k"] < 0.15
        condition &= dataframe["stoch_k"] > dataframe["stoch_d"]
        condition &= dataframe["stoch_k"].shift(1) <= dataframe["stoch_d"].shift(1)
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_cond = (dataframe["stoch_k"] > 0.80) | (dataframe["rsi"] > 65)
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe
