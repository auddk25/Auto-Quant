"""
MFIMeanRev — Money Flow Index (MFI) with MeanRevADX filters

Paradigm: mean-reversion
Hypothesis: MFI (volume-weighted RSI) < 25 oversold combined with the 
            high-quality trend and volatility gates from MeanRevADX (ADX>19, 
            BB2.18*0.997).
Parent: MeanRevADX
Created: 2026-04-23
Status: active
"""

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy


class MFIMeanRev(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    minimal_roi = {"0": 0.008}
    stoploss = -0.08

    trailing_stop = False
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = True

    startup_candle_count: int = 200

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["mfi"] = ta.MFI(dataframe, timeperiod=14)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        bands = ta.BBANDS(dataframe, timeperiod=25, nbdevup=2.18, nbdevdn=2.18)
        dataframe["bb_middle"] = bands["middleband"]
        dataframe["bb_lower"] = bands["lowerband"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        condition = dataframe["close"] > dataframe["ema200"]
        condition &= dataframe["adx"] > 19
        condition &= dataframe["close"] < dataframe["bb_lower"] * 0.997
        condition &= dataframe["mfi"] < 30
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit when MFI > 70 or price reclaims the BB midline
        exit_cond = (dataframe["mfi"] > 70) | (dataframe["close"] > dataframe["bb_middle"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe
