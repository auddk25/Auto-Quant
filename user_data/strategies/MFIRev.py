"""
MFIRev — Money Flow Index oversold bounce inside 200-EMA uptrend

Paradigm: mean-reversion
Hypothesis: BTC/ETH 1h reverts from MFI<20 volume-confirmed oversold when
            price has also broken below the BB lower band (25-period, 2.0σ).
            MFI incorporates volume unlike RSI/StochRSI — catches genuine
            capitulation (high-volume selling at price extremes). Expected to
            find entries that RSI<40 and StochRSI<0.15 both miss because
            volume confirmation acts as a different structural gate.
Parent: root
Created: <fill after commit>
Status: active
"""

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy


class MFIRev(IStrategy):
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
        dataframe["mfi"] = ta.MFI(dataframe, timeperiod=14)
        bands = ta.BBANDS(dataframe, timeperiod=25, nbdevup=2.0, nbdevdn=2.0)
        dataframe["bb_lower"] = bands["lowerband"]
        dataframe["bb_middle"] = bands["middleband"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        condition = dataframe["close"] > dataframe["ema200"]
        condition &= dataframe["adx"] > 19
        condition &= dataframe["close"] < dataframe["bb_lower"]
        condition &= dataframe["mfi"] < 20
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_cond = (dataframe["mfi"] > 60) | (dataframe["close"] > dataframe["bb_middle"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe
