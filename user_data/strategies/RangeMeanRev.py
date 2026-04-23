"""
RangeMeanRev — deep-oversold mean-reversion in ranging (non-trending) markets

Paradigm: mean-reversion
Hypothesis: BTC/ETH 1h reverts sharply from RSI<25 oversold levels when the
            market is in a sideways regime (ADX<20, no directional trend).
            Ranging markets produce reliable oscillations between support and
            resistance; mean-reversion in low-ADX environments should
            complement MeanRevADX which only fires in trending markets (ADX>19).
Parent: root
Created: <fill after commit>
Status: active
"""

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy


class RangeMeanRev(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    minimal_roi = {"0": 0.008}
    stoploss = -0.05

    trailing_stop = False
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = True

    startup_candle_count: int = 50

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        stoch = ta.STOCH(dataframe, fastk_period=14, slowk_period=3, slowd_period=3)
        dataframe["stoch_k"] = stoch["slowk"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ranging regime (no strong trend) but in macro uptrend
        condition = dataframe["adx"] < 20
        condition &= dataframe["close"] > dataframe["ema200"]
        # dual oversold: both RSI and Stoch confirm extreme reading
        condition &= dataframe["rsi"] < 35
        condition &= dataframe["stoch_k"] < 20
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_cond = (dataframe["rsi"] > 60) | (dataframe["stoch_k"] > 75)
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe
