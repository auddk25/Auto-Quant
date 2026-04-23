"""
KeltnerRev — Keltner Channel mean reversion

Paradigm: mean-reversion
Hypothesis: Keltner Channels (EMA-based) are smoother than Bollinger Bands 
            (SMA-based) and might provide better entry timing for 
            mean-reversion on 1h crypto.
Parent: root
Created: 2026-04-23
Status: active
"""

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy


class KeltnerRev(IStrategy):
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
        
        # Keltner Channel calculation
        # Middle line: 20-period EMA
        # Band width: 2.0 * 20-period ATR
        dataframe["kc_middle"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=20)
        dataframe["kc_lower"] = dataframe["kc_middle"] - (dataframe["atr"] * 2.0)
        dataframe["kc_upper"] = dataframe["kc_middle"] + (dataframe["atr"] * 2.0)
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        condition = dataframe["close"] > dataframe["ema200"]
        condition &= dataframe["adx"] > 15
        condition &= dataframe["close"] < dataframe["kc_lower"]
        condition &= dataframe["rsi"] < 40
        
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit at middle line
        exit_cond = (dataframe["close"] > dataframe["kc_middle"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe
