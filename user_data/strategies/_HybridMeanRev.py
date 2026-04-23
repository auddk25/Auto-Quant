"""
HybridMeanRev — archived dual oscillator mean reversion candidate

Paradigm: mean-reversion
Hypothesis: Combining MFI (volume-weighted momentum) with StochRSI (fast price
            momentum) as a dual gate, plus the MeanRevADX filters (ADX>19,
            BB2.18*0.997), provides reliable entries.
Parent: MeanRevADX, StochMeanRev, MFIMeanRev
Created: 2026-04-23
Status: archived

Archived because FactorMeanRevCandidate produced higher validation Sharpe
while keeping the active roster capped at 3 strategies.
"""

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy


class HybridMeanRev(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    minimal_roi = {"0": 0.010}
    stoploss = -0.08

    trailing_stop = False
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = True

    startup_candle_count: int = 200

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        rsi = ta.RSI(dataframe, timeperiod=20)
        stoch = ta.STOCH(
            dataframe.assign(high=rsi, low=rsi, close=rsi),
            fastk_period=14,
            slowk_period=3,
            slowd_period=3,
        )
        dataframe["stoch_k"] = stoch["slowk"] / 100.0

        dataframe["mfi"] = ta.MFI(dataframe, timeperiod=14)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        bands = ta.BBANDS(dataframe, timeperiod=25, nbdevup=2.18, nbdevdn=2.18)
        dataframe["bb_middle"] = bands["middleband"]
        dataframe["bb_lower"] = bands["lowerband"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        condition = dataframe["close"] > dataframe["ema200"]
        condition &= dataframe["close"] < dataframe["ema20"]
        condition &= dataframe["adx"] > 19
        condition &= dataframe["close"] < dataframe["bb_lower"] * 0.997
        condition &= dataframe["stoch_k"] < 0.25
        condition &= dataframe["mfi"] < 35
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_cond = (dataframe["stoch_k"] > 0.80) | (dataframe["close"] > dataframe["bb_middle"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe
