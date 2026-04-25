"""MtfTrendHybrid — Instant Entry + SMA200 Exit

Combines the best of two worlds:
- SmartHold: enter immediately (capture full bull run)
- Bear01: use SMA200 as the ultimate bear/bull filter

Entry: Immediately on backtest start (BTC only, no timing).
Exit:  1d close < SMA200  (trend broken — much faster signal than EMA death cross)

Why SMA200 exit instead of EMA crossover:
  EMA50/200 death cross needs a sustained downtrend to trigger.
  In a slow grind down (-16% in Q1 2026), death cross may not happen until -25%.
  SMA200 break triggers as soon as price drops below its 200-day average,
  which happens faster and protects capital sooner.

Parent: MtfTrendSmartHold (R90) + MtfTrendBear01 (R87)
Created: R93
Status: active
Uses: 1d SMA200 only — the simplest possible trend filter
"""
from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative


class MtfTrendHybrid(IStrategy):
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
        dataframe["sma200"] = ta.SMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe
        # Enter immediately — default position is IN the market
        dataframe.loc[dataframe["volume"] > 0, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ONE exit condition: daily close drops below SMA200
        dataframe.loc[
            dataframe["close_1d"] < dataframe["sma200_1d"],
            "exit_long"
        ] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
