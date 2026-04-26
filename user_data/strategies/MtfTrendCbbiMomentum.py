"""MtfTrendCbbiMomentum — CBBI Direction Strategy

Indicators: CBBI (primary), EMA100/200 (trend filter), AHR999 (valuation)
Paradigm: CBBI absolute level only works in capitulation.
          CBBI DIRECTION works in all markets.

Entry:
  - CBBI rising over 5 days (fear subsiding = confidence returning)
  - CBBI < 0.65 (not already euphoric)
  - EMA100 > EMA200 (trend is up)

Exit:
  - CBBI falling over 5 days (confidence eroding)
  - CBBI > 0.80 (extreme greed — blow-off top)

Why momentum: CBBI < 0.4 only triggers in extreme fear (rare).
              CBBI rising from 0.5 to 0.6 = "dip being bought" (common).
              This captures far more entries in normal bull markets.

Parent: CbbiLead (R98)
Created: R99
Status: active
"""
from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from autoq_data.cycle_bridge import merge_ahr999, merge_cbbi


class MtfTrendCbbiMomentum(IStrategy):
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
        dataframe = merge_cbbi(dataframe, metadata)
        # CBBI 5-day momentum: positive = fear subsiding
        # On 1h data, CBBI is daily — need to track daily changes
        # Use shift(24) for approximate daily change on 1h candles
        dataframe["cbbi_5d_ago"] = dataframe["cbbi"].shift(24 * 5)
        dataframe["cbbi_momentum"] = dataframe["cbbi"] - dataframe["cbbi_5d_ago"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        # CBBI rising (confidence returning) + not already greedy + trend up
        fear_subsiding = dataframe["cbbi_momentum"] > 0
        not_euphoric = dataframe["cbbi"] < 0.65
        trend_ok = dataframe["ema100_1d"] > dataframe["ema200_1d"]

        dataframe.loc[
            fear_subsiding & not_euphoric & trend_ok & (dataframe["volume"] > 0),
            "enter_long"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit (any one):
        confidence_falling = dataframe["cbbi_momentum"] < -0.03  # tighter: mild fear returning
        extreme_greed = dataframe["cbbi"] > 0.80
        trend_broken = dataframe["ema100_1d"] < dataframe["ema200_1d"]

        dataframe.loc[
            confidence_falling | extreme_greed | trend_broken,
            "exit_long"
        ] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
