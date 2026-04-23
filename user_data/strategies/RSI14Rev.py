"""
RSI14Rev — Standard RSI(14) oversold at tighter threshold inside 200-EMA uptrend

Paradigm: mean-reversion
Hypothesis: BTC/ETH 1h reverts from RSI(14) < 35 when price has broken
            below BB lower band (25-period, 2.0σ). Uses the standard RSI
            period (14) at a tighter threshold than MeanRevADX (RSI(20)<40).
            RSI(14) requires steeper shorter-term declines than RSI(20).
            Expected to fire between the flash-crash timing of RSI(7)<20
            and the sustained-selloff timing of RSI(20)<40 — a middle band
            of moderately-sharp moves that both miss.
Parent: root
Created: <fill after commit>
Status: active
"""

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy


class RSI14Rev(IStrategy):
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
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        bands = ta.BBANDS(dataframe, timeperiod=25, nbdevup=2.18, nbdevdn=2.18)
        dataframe["bb_lower"] = bands["lowerband"]
        dataframe["bb_middle"] = bands["middleband"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        condition = dataframe["close"] > dataframe["ema200"]
        condition &= dataframe["adx"] > 19
        condition &= dataframe["close"] < dataframe["bb_lower"]
        condition &= dataframe["rsi"] < 30
        # RSI is turning up — start of recovery, not still falling
        condition &= dataframe["rsi"] > dataframe["rsi"].shift(1)
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_cond = (dataframe["rsi"] > 58) | (dataframe["close"] > dataframe["bb_middle"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe
