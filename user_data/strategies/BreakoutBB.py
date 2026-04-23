"""
BreakoutBB — breakout from sustained BB squeeze (5+ bars compressed)

Paradigm: breakout
Hypothesis: BTC/ETH 1h produces strong directional moves when price breaks
            the upper BB after a sustained (5+ candle) period of compressed
            volatility (width < 0.04). Sustained compression builds energy;
            single-bar squeezes are noise, multi-bar squeezes signal coiling.
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
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        bands = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe["bb_upper"] = bands["upperband"]
        dataframe["bb_middle"] = bands["middleband"]
        dataframe["bb_lower"] = bands["lowerband"]
        dataframe["bb_width"] = (
            (dataframe["bb_upper"] - dataframe["bb_lower"]) / dataframe["bb_middle"]
        )
        # count consecutive bars below squeeze threshold
        squeeze_mask = (dataframe["bb_width"] < 0.04).astype(int)
        dataframe["squeeze_bars"] = squeeze_mask.groupby(
            (squeeze_mask != squeeze_mask.shift()).cumsum()
        ).cumcount()
        dataframe["volume_ma"] = ta.SMA(dataframe["volume"], timeperiod=20)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # sustained squeeze (5+ bars), then breakout above upper band
        condition = dataframe["close"] > dataframe["ema200"]
        condition &= dataframe["squeeze_bars"].shift(1) >= 5
        condition &= dataframe["close"] > dataframe["bb_upper"]
        condition &= dataframe["rsi"] > 52
        condition &= dataframe["volume"] > dataframe["volume_ma"] * 1.5
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_cond = (dataframe["rsi"] > 78) | (dataframe["close"] < dataframe["bb_middle"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe
