"""MtfTrendEmaCycle — EMA100/200 + AHR999 + CBBI Smart Hold

Indicators (per user preference): EMA100, EMA200, AHR999, CBBI
Paradigm: Enter immediately, exit only on indicator confirmation.

Entry: Immediately on backtest start (BTC only) — don't time the market.
Exit (any one triggers):
  - EMA100 < EMA200  (trend reversed to bearish)
  - AHR999 > 1.5     (cycle says very overvalued)
  - CBBI > 0.8       (market euphoria / extreme greed)

Design rationale: In a bull market, "when to buy" matters less than "when to sell."
                  Entering early + selling at the right time captures the full trend.

Parent: MtfTrendSmartHold (R90) + user's indicator preferences
Created: R91 (revised)
Status: active
"""
from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from autoq_data.cycle_bridge import merge_ahr999, merge_cbbi


class MtfTrendEmaCycle(IStrategy):
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
        # Enter immediately — don't wait for indicator confirmation
        dataframe.loc[dataframe["volume"] > 0, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit on any one of the user's three conditions
        trend_broken = dataframe["ema100_1d"] < dataframe["ema200_1d"]
        overvalued = dataframe["ahr999"] > 1.5
        euphoria = dataframe["cbbi"] > 0.8
        dataframe.loc[trend_broken | overvalued | euphoria, "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
