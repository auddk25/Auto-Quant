"""MtfTrendCbbiMomentumParam — Parameterized CBBI Direction Strategy

Parameterized version of MtfTrendCbbiMomentum for optimization.

Indicators: CBBI (primary), EMA100/200 (trend filter), AHR999 (valuation)
Paradigm: CBBI absolute level only works in capitulation.
          CBBI DIRECTION works in all markets.

Entry:
  - CBBI rising over N days (fear subsiding = confidence returning)
  - CBBI < threshold (not already euphoric)
  - EMA100 > EMA200 (trend is up)

Exit:
  - CBBI falling over N days (confidence eroding)
  - CBBI > exit_threshold (extreme greed — blow-off top)

Parent: MtfTrendCbbiMomentum (R99)
Created: R104
Status: active
"""
from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from autoq_data.cycle_bridge import merge_ahr999, merge_cbbi


class MtfTrendCbbiMomentumParam(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = False
    max_open_trades = 1
    minimal_roi = {"0": 100}
    stoploss = -0.25
    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    # ---- Configurable parameters (set by screening script) ----
    # Entry parameters
    ENTRY_MOM = 3          # CBBI N-day momentum for entry
    CB_THRESHOLD = 0.65    # CBBI < threshold to enter

    # Exit parameters
    EXIT_MOM = 4           # CBBI N-day momentum for exit
    EXIT_THRESHOLD = -0.03 # momentum < threshold to exit
    EXIT_CBBI = 0.80       # CBBI > threshold to exit

    # Trend parameters
    TREND_FAST = 100       # Fast EMA period
    TREND_SLOW = 200       # Slow EMA period

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.TREND_FAST)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.TREND_SLOW)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = merge_cbbi(dataframe, metadata)
        # Pre-compute all possible momentum columns for different N values
        # On 1h data, CBBI is daily — use shift(24*N) for N-day change
        for n in [2, 3, 4, 5, 6]:
            dataframe[f"cbbi_mom_{n}d"] = dataframe["cbbi"] - dataframe["cbbi"].shift(24 * n)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        # CBBI rising (confidence returning) + not already greedy + trend up
        fear_subsiding = dataframe[f"cbbi_mom_{self.ENTRY_MOM}d"] > 0
        not_euphoric = dataframe["cbbi"] < self.CB_THRESHOLD
        trend_ok = dataframe["ema_fast_1d"] > dataframe["ema_slow_1d"]

        dataframe.loc[
            fear_subsiding & not_euphoric & trend_ok & (dataframe["volume"] > 0),
            "enter_long"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit (any one):
        confidence_falling = dataframe[f"cbbi_mom_{self.EXIT_MOM}d"] < self.EXIT_THRESHOLD
        extreme_greed = dataframe["cbbi"] > self.EXIT_CBBI
        trend_broken = dataframe["ema_fast_1d"] < dataframe["ema_slow_1d"]

        dataframe.loc[
            (confidence_falling | extreme_greed | trend_broken) & (dataframe["volume"] > 0),
            "exit_long"
        ] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
