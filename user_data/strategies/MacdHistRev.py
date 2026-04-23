"""
MacdHistRev — MACD histogram recovery from negative peak + BB lower band

Paradigm: mean-reversion
Hypothesis: BTC/ETH 1h reverts when MACD histogram is recovering from its
            most negative point (bearish momentum peaking) while price has
            broken below BB lower band (25-period, 2.18σ). The histogram
            recovery detects the moment short-term bearish momentum (12/26
            EMA difference) starts to weaken — structurally different from
            RSI-based entries which measure N-bar velocity, not momentum
            peak detection. Expected to fire at genuine turning points where
            the rate of decline is already slowing before price bottoms.
Parent: root
Created: <fill after commit>
Status: active
"""

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy


class MacdHistRev(IStrategy):
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
        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe["macd_hist"] = macd["macdhist"]
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        bands = ta.BBANDS(dataframe, timeperiod=25, nbdevup=2.18, nbdevdn=2.18)
        dataframe["bb_lower"] = bands["lowerband"]
        dataframe["bb_middle"] = bands["middleband"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        condition = dataframe["close"] > dataframe["ema200"]
        condition &= dataframe["adx"] > 19
        condition &= dataframe["close"] < dataframe["bb_lower"]
        # histogram still negative (bearish overall)
        condition &= dataframe["macd_hist"] < 0
        # histogram recovering — bearish momentum weakening (divergence signal)
        condition &= dataframe["macd_hist"] > dataframe["macd_hist"].shift(1)
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_cond = (dataframe["macd_hist"] > 0) | (dataframe["close"] > dataframe["bb_middle"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe
