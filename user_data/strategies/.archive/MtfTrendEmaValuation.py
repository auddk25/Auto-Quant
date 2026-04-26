"""MtfTrendEmaValuation — EMA100/200 Trend + AHR999 Valuation + CBBI Sentiment

Indicators: EMA100, EMA200, AHR999, CBBI (all four per user preference)
Paradigm: Trend direction + valuation context = better entry timing

Entry (all must agree):
  - EMA100 > EMA200  (bull trend active)
  - AHR999 < 1.2     (not overvalued yet)
  - CBBI < 0.75       (not euphoric)
  → All three confirm = strong risk/reward entry

Exit (any one triggers):
  - EMA100 < EMA200  (trend reversed)
  - AHR999 > 1.5     (severely overvalued)
  - CBBI > 0.85      (extreme euphoria / blow-off top)
  → Any one = get out

Why EMA100/200 instead of EMA50/200:
  EMA100 is closer to EMA200 → crossovers happen faster.
  This means: enters earlier after a bear, exits sooner when trend weakens.
  The trade-off: slightly more whipsaws, but faster reaction time.

Parent: None (user-directed indicator combo)
Created: R94
Status: active
"""
from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from autoq_data.cycle_bridge import merge_ahr999, merge_cbbi


class MtfTrendEmaValuation(IStrategy):
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

        trend_ok     = dataframe["ema100_1d"] > dataframe["ema200_1d"]
        valuation_ok = dataframe["ahr999"] < 1.2
        sentiment_ok = dataframe["cbbi"] < 0.75

        buy_cond = trend_ok & valuation_ok & sentiment_ok & (dataframe["volume"] > 0)
        dataframe.loc[buy_cond, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        trend_broken = dataframe["ema100_1d"] < dataframe["ema200_1d"]
        overvalued   = dataframe["ahr999"] > 1.5
        euphoria     = dataframe["cbbi"] > 0.85

        dataframe.loc[trend_broken | overvalued | euphoria, "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
