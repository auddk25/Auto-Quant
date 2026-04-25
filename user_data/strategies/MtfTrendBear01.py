"""MtfTrendBear01 -- Bear-Aware Trend Following

Paradigm: SMA200 Trend Filter with Macro Confirmation
Hypothesis: The biggest edge in crypto is avoiding bear markets. This strategy:
            - Only enters when 1d close > SMA200 (bull regime confirmed)
            - Requires macro health (funding not panic, stablecoins not shrinking)
            - Exits ONLY on SMA200 break (relatively slow, avoids whipsaws)
            - BTC and ETH both eligible.
Parent: None (new paradigm)
Created: R87
Status: active
Uses: 1d SMA200 trend, macro factors (funding_rate, stablecoin_mcap_growth)
"""

from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from autoq_data.strategy_bridge import merge_external_factors


class MtfTrendBear01(IStrategy):
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
        dataframe = merge_external_factors(
            dataframe, metadata,
            columns=["funding_rate", "stablecoin_mcap_growth"],
        )
        dataframe["funding_rate"] = dataframe["funding_rate"].fillna(0)
        dataframe["stablecoin_mcap_growth"] = dataframe["stablecoin_mcap_growth"].fillna(0)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Bull regime: above SMA200
        is_bull = dataframe["close_1d"] > dataframe["sma200_1d"]
        # Macro: funding not panic, stablecoins growing (liquidity flowing in)
        macro_ok = (
            (dataframe["funding_rate"] > -0.01)
            & (dataframe["stablecoin_mcap_growth"] > 0)
        )
        buy_cond = is_bull & macro_ok & (dataframe["volume"] > 0)
        dataframe.loc[buy_cond, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Only exit when daily trend truly broken
        dataframe.loc[dataframe["close_1d"] < dataframe["sma200_1d"], "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
