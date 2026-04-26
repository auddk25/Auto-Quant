"""MtfTrendLongShort — CBBI Momentum Long/Short Strategy

Paradigm: CBBI momentum works in both directions.
          - CBBI rising = fear subsiding → go long
          - CBBI falling = confidence dropping → go short

Requires: config_futures.json (futures mode, isolated margin)

Entry Long:
  - CBBI 3d momentum > 0 (fear subsiding)
  - CBBI < 0.65 (not already greedy)
  - EMA100 > EMA200 (trend is up)

Entry Short:
  - CBBI 3d momentum < 0 (confidence dropping)
  - CBBI > 0.25 (not already oversold)
  - EMA100 < EMA200 (trend is down)

Exit (any one):
  - CBBI 4d momentum crosses opposite direction
  - CBBI extreme zone (long: >0.80, short: <0.15)
  - EMA trend reversal

Parent: CbbiMomentum R99v4
Created: R102
Status: active
"""
from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from autoq_data.cycle_bridge import merge_cbbi


class MtfTrendLongShort(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = True
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
        dataframe["cbbi_3d_ago"] = dataframe["cbbi"].shift(24 * 3)
        dataframe["cbbi_4d_ago"] = dataframe["cbbi"].shift(24 * 4)
        dataframe["cbbi_mom_3d"] = dataframe["cbbi"] - dataframe["cbbi_3d_ago"]
        dataframe["cbbi_mom_4d"] = dataframe["cbbi"] - dataframe["cbbi_4d_ago"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ── Long: CBBI rising + not greedy + uptrend ──
        long_cond = (
            (dataframe["cbbi_mom_3d"] > 0)
            & (dataframe["cbbi"] < 0.65)
            & (dataframe["ema100_1d"] > dataframe["ema200_1d"])
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[long_cond, "enter_long"] = 1

        # ── Short: CBBI falling + not oversold + downtrend ──
        short_cond = (
            (dataframe["cbbi_mom_3d"] < 0)
            & (dataframe["cbbi"] > 0.25)
            & (dataframe["ema100_1d"] < dataframe["ema200_1d"])
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[short_cond, "enter_short"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ── Exit Long ──
        dataframe.loc[
            (dataframe["cbbi_mom_4d"] < -0.03)
            | (dataframe["cbbi"] > 0.80)
            | (dataframe["ema100_1d"] < dataframe["ema200_1d"]),
            "exit_long"
        ] = 1

        # ── Exit Short ──
        dataframe.loc[
            (dataframe["cbbi_mom_4d"] > 0.03)
            | (dataframe["cbbi"] < 0.15)
            | (dataframe["ema100_1d"] > dataframe["ema200_1d"]),
            "exit_short"
        ] = 1

        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
