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
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        bands = ta.BBANDS(dataframe, timeperiod=25, nbdevup=2.5, nbdevdn=2.5)
        dataframe["bb_lower"] = bands["lowerband"]
        dataframe["bb_middle"] = bands["middleband"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # low-to-moderate trend strength (complements MeanRevADX's ADX>19 range)
        condition = dataframe["adx"] < 25
        condition &= dataframe["close"] > dataframe["ema200"]
        condition &= dataframe["rsi"] < 30
        condition &= dataframe["close"] < dataframe["bb_lower"]
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_cond = (dataframe["rsi"] > 60) | (dataframe["close"] > dataframe["bb_middle"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe
