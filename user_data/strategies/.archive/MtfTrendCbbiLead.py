"""MtfTrendCbbiLead — CBBI-First Strategy

Indicators: CBBI (primary), EMA100/200 (trend safety)
Paradigm: CBBI is the best aggregate sentiment indicator. Let it lead.

Entry:
  - CBBI < 0.5   (market fearful/neutral — buy zone)
  - EMA100 > EMA200 (trend safety — only buy in uptrends)

Exit (any one):
  - CBBI > 0.70  (greed emerging — take profit)
  - EMA100 < EMA200 (trend broken — safety exit)

Parent: None (CBBI-first paradigm)
Created: R96 (v2)
Status: active
"""
from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from autoq_data.cycle_bridge import merge_ahr999, merge_cbbi


class MtfTrendCbbiLead(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = False
    max_open_trades = 1
    minimal_roi = {"0": 100}
    stoploss = -0.25
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

        # CBBI leads: enter when market is fearful
        # Pure CBBI timing: enter when market is fearful
        fear = dataframe["cbbi"] < 0.4

        dataframe.loc[
            fear & (dataframe["volume"] > 0),
            "enter_long"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # CBBI leads exit too: greed = get out
        greed = dataframe["cbbi"] > 0.75  # R98: raised from 0.70 for +38% improvement
        # Safety: trend broken
        trend_broken = dataframe["ema100_1d"] < dataframe["ema200_1d"]

        dataframe.loc[greed | trend_broken, "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
