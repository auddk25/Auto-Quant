"""MtfTrendSimple -- Minimal Indicator Combo

Indicators: EMA100, EMA200, AHR999, CBBI (per user preference)
Paradigm: One entry condition + one exit condition.

Entry: AHR999 < 0.8  (undervalued — cycle indicator says cheap)
Exit:  EMA100 < EMA200 (trend broken — trend indicator says get out)

That's it. CBBI is loaded as informational but not used for trading.
The philosophy: buy when cheap (cycle), sell when trend ends (trend).

Parent: None
Created: R92
Status: active
"""
from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from autoq_data.cycle_bridge import merge_ahr999, merge_cbbi


class MtfTrendSimple(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = False
    max_open_trades = 1
    minimal_roi = {"0": 100}
    stoploss = -0.99
    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema100"] = ta.EMA(dataframe, timeperiod=100)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = merge_ahr999(dataframe, metadata)
        dataframe = merge_cbbi(dataframe, metadata)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe
        # ONE condition: cycle says undervalued
        dataframe.loc[
            (dataframe["ahr999"] < 0.8) & (dataframe["volume"] > 0),
            "enter_long"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ONE condition: trend broken
        dataframe.loc[
            dataframe["ema100_1d"] < dataframe["ema200_1d"],
            "exit_long"
        ] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
