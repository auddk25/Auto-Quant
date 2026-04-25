"""MtfTrendCycle01 -- Cycle Resonance Strategy (AHR999 + CBBI)

Paradigm: Bitcoin Cycle Timing via On-Chain Valuation
Hypothesis: AHR999 and CBBI are the two most reliable long-term cycle indicators.
            - AHR999 < 0.45: severe undervaluation (buy zone)
            - CBBI < 0.4: multi-indicator confidence of undervaluation (0-1 scale)
            - When both agree, full-portfolio BTC entry.
            - Exit when AHR999 > 1.5 OR daily trend breaks (close < SMA200).
Parent: None (new paradigm)
Created: R86
Status: active
Uses: AHR999 (pre-computed), CBBI (pre-fetched API data)
"""

from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from autoq_data.cycle_bridge import merge_ahr999, merge_cbbi


class MtfTrendCycle01(IStrategy):
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
        dataframe["sma200"] = ta.SMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = merge_ahr999(dataframe, metadata)
        dataframe = merge_cbbi(dataframe, metadata)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        # Cycle accumulation zone: AHR999 undervalued + CBBI confirms
        buy_cond = (
            (dataframe["ahr999"] < 0.80)
            & (dataframe["cbbi"] < 0.5)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[buy_cond, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit: overvaluation (AHR999 > 1.2 means getting expensive)
        # OR CBBI overheating (market euphoria)
        overvalued = dataframe["ahr999"] > 1.3
        euphoria = dataframe["cbbi"] > 0.80
        dataframe.loc[overvalued | euphoria, "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
