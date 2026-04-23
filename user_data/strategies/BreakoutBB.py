"""
BreakoutBB — Bollinger Band upper breakout after low-volatility squeeze

Paradigm: breakout
Hypothesis: BTC/ETH 1h shows persistent upside moves when price closes above
            the upper Bollinger Band (20-period, 2σ) following a period of
            compressed volatility (BB width < 0.06). Volatility expansion after
            a squeeze tends to produce directional follow-through rather than
            immediate mean-reversion.
Parent: root
Created: 9864ab8
Status: active
"""

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy


class BreakoutBB(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    minimal_roi = {"0": 0.05}
    stoploss = -0.04

    trailing_stop = False
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    startup_candle_count: int = 50

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        bands = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe["bb_upper"] = bands["upperband"]
        dataframe["bb_middle"] = bands["middleband"]
        dataframe["bb_lower"] = bands["lowerband"]
        dataframe["bb_width"] = (
            (dataframe["bb_upper"] - dataframe["bb_lower"]) / dataframe["bb_middle"]
        )
        dataframe["bb_width_prev"] = dataframe["bb_width"].shift(1)
        dataframe["volume_ma"] = ta.SMA(dataframe["volume"], timeperiod=20)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        squeeze = dataframe["bb_width_prev"] < 0.03
        breakout = dataframe["close"] > dataframe["bb_upper"]
        momentum = dataframe["rsi"] > 55
        vol_confirm = dataframe["volume"] > dataframe["volume_ma"] * 1.5
        dataframe.loc[squeeze & breakout & momentum & vol_confirm, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_cond = (dataframe["rsi"] > 80) | (dataframe["close"] < dataframe["bb_middle"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe
