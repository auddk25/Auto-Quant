"""
StochRev — Stochastic RSI oversold bounce inside 200-EMA uptrend

Paradigm: mean-reversion
Hypothesis: BTC/ETH 1h reverts from StochRSI < 0.10 extreme oversold when
            price has also broken below the BB lower band (25-period, 2.5σ).
            The dual gate (fast oscillator + price below volatility band)
            enforces selectivity. Targets entries MeanRevADX misses because
            plain RSI(20) hasn't yet crossed <40 but StochRSI is already extreme.
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
        rsi = ta.RSI(dataframe, timeperiod=14)
        dataframe["rsi"] = rsi
        stoch = ta.STOCH(
            dataframe.assign(high=rsi, low=rsi, close=rsi),
            fastk_period=14, slowk_period=3, slowd_period=3,
        )
        dataframe["stoch_k"] = stoch["slowk"] / 100.0
        dataframe["stoch_d"] = stoch["slowd"] / 100.0
        bands = ta.BBANDS(dataframe, timeperiod=25, nbdevup=2.0, nbdevdn=2.0)
        dataframe["bb_lower"] = bands["lowerband"]
        dataframe["bb_middle"] = bands["middleband"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        condition = dataframe["close"] > dataframe["ema200"]
        condition &= dataframe["adx"] > 15
        condition &= dataframe["close"] < dataframe["bb_lower"]
        condition &= dataframe["stoch_k"] < 0.15
        condition &= dataframe["stoch_k"] > dataframe["stoch_d"]
        condition &= dataframe["stoch_k"].shift(1) <= dataframe["stoch_d"].shift(1)
        condition &= dataframe["rsi"] < 45
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_cond = (dataframe["stoch_k"] > 0.80) | (dataframe["close"] > dataframe["bb_middle"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe
