"""
VolSqueeze — Bollinger Band squeeze breakout

Paradigm: Volatility / Breakout
Hypothesis: BTC/ETH 1h breakouts from low-volatility squeezes (Bollinger 
            Bandwidth at its 120-bar low) tend to lead to strong moves.
            Entering when price breaks the upper band after a squeeze
            captures the start of a new trend.
Parent: root
Created: 2026-04-23
Status: active
"""

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy


class VolSqueeze(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # ROI target is higher for breakout
    minimal_roi = {"0": 0.03}
    stoploss = -0.04

    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02

    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        bands = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe["bb_upper"] = bands["upperband"]
        dataframe["bb_lower"] = bands["lowerband"]
        dataframe["bb_middle"] = bands["middleband"]
        
        # Bandwidth calculation
        dataframe["bw"] = (dataframe["bb_upper"] - dataframe["bb_lower"]) / dataframe["bb_middle"]
        # Squeeze = bandwidth is in the lowest 10% of the last 120 bars
        dataframe["bw_min"] = dataframe["bw"].rolling(window=120).min()
        dataframe["squeeze"] = dataframe["bw"] < (dataframe["bw_min"].shift(1) * 1.1)
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        condition = dataframe["close"] > dataframe["ema200"]
        condition &= dataframe["squeeze"]
        condition &= (dataframe["close"] > dataframe["bb_upper"])
        condition &= (dataframe["close"].shift(1) <= dataframe["bb_upper"].shift(1))
        
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit if price drops below the 20-period middle band (trailing stop handles the rest)
        exit_cond = dataframe["close"] < dataframe["bb_middle"]
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe
