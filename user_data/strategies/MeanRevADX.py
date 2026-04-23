"""
MeanRevADX — RSI oversold dip with ADX trend filter and BB-lower entry gate

Paradigm: mean-reversion
Hypothesis: BTC/ETH 1h reverts reliably from RSI<40 oversold dips that occur
            inside trending markets (ADX>19). Entry requires price to break
            below the lower Bollinger Band (25-period, 2.18σ) while the
            200-EMA confirms the broader uptrend. Exit when RSI recovers
            above 58 and price reclaims the BB midline.
Parent: root — derived from autoresearch/apr22 run, best commit 16f9046.
        879 experiments, Sharpe 2.10, max_dd 0.96%, 66 trades, pf 20.4.
        Key finding: ADX filter was the breakthrough (removed exit_profit_only
        regime trick; edge is real without it).
Created: <fill after first commit>
Status: active
"""

from pandas import DataFrame
import talib.abstract as ta

from freqtrade.strategy import IStrategy


class MeanRevADX(IStrategy):
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
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=20)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        bands = ta.BBANDS(dataframe, timeperiod=25, nbdevup=2.18, nbdevdn=2.18)
        dataframe["bb_upper"] = bands["upperband"]
        dataframe["bb_middle"] = bands["middleband"]
        dataframe["bb_lower"] = bands["lowerband"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        condition = dataframe["close"] > dataframe["ema200"]
        condition &= dataframe["rsi"] < 40
        condition &= dataframe["close"] < dataframe["bb_lower"] * 0.997
        condition &= dataframe["adx"] > 19
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_cond = (dataframe["rsi"] > 58) & (dataframe["close"] > dataframe["bb_middle"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe
