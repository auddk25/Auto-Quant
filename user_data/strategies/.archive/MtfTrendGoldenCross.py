"""MtfTrendGoldenCross -- Golden Cross Trend Following

Paradigm: EMA50/200 Golden Cross on Daily Timeframe
Hypothesis: The simplest reliable trend signal in any asset class.
            - Golden Cross (EMA50 > EMA200) = Bull market => enter long, hold.
            - Death Cross (EMA50 < EMA200) = Bear market => exit, stay cash.
            - No intra-trend exits, no RSI, no short-term noise.
            - BTC and ETH both eligible, 100% allocation on entry.
Parent: None (classic paradigm)
Created: R88
Status: active
"""
from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative


class MtfTrendGoldenCross(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = False
    max_open_trades = 1
    minimal_roi = {"0": 100}
    stoploss = -0.99  # Essentially no stoploss — trust the weekly trend
    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Golden Cross: EMA50 above EMA200 on daily timeframe
        golden_cross = (
            (dataframe["ema50_1d"] > dataframe["ema200_1d"])
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[golden_cross, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Death Cross: EMA50 below EMA200
        dataframe.loc[dataframe["ema50_1d"] < dataframe["ema200_1d"], "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
