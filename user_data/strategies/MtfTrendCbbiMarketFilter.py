"""MtfTrendCbbiMarketFilter — Market State Filtered Strategy

Filters entries based on market state to avoid choppy periods.

Logic:
- Calculate BTC 30-day return
- Bull market (>+10%): Normal entry
- Choppy market (-5% to +10%): Only enter if CBBI momentum is strong (>0.02)
- Bear market (<-5%): No entry

Entry logic:
- CBBI momentum > 0 (fear subsiding)
- CBBI < 0.65 (not euphoric)
- EMA100 > EMA200 (trend up)
- Market state filter (bull or strong momentum in choppy)

Exit logic:
- CBBI momentum < -0.02 (confidence falling)
- OR CBBI > 0.80 (extreme greed)
- OR EMA100 < EMA200 (trend broken)

Parent: MtfTrendCbbiMomentumEnsemble (R105)
Created: R109 (adaptive parameter exploration)
Status: active
"""
from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
import numpy as np
from freqtrade.strategy import IStrategy
from autoq_data.cycle_bridge import merge_cbbi


class MtfTrendCbbiMarketFilter(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = False
    max_open_trades = 1
    minimal_roi = {"0": 100}
    stoploss = -0.25
    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    # ---- CBBI Parameters (proven) ----
    ENTRY_MOM = 3
    CB_THRESHOLD = 0.65
    EXIT_MOM = 3
    EXIT_THRESHOLD = -0.02
    EXIT_CBBI = 0.80

    # ---- Market Filter Parameters ----
    RETURN_PERIOD = 24 * 30      # 30 days in 1h candles
    BULL_THRESHOLD = 0.10        # >+10% = bull
    CHOPPY_THRESHOLD = -0.05     # <-5% = bear
    STRONG_MOM = 0.02            # Strong momentum threshold for choppy

    # ---- Trend Parameters ----
    TREND_FAST = 100
    TREND_SLOW = 200

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = merge_cbbi(dataframe, metadata)
        # CBBI momentum
        for n in [2, 3, 4, 5, 6]:
            dataframe[f"cbbi_mom_{n}d"] = dataframe["cbbi"] - dataframe["cbbi"].shift(24 * n)
        # Trend EMAs
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.TREND_FAST)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.TREND_SLOW)
        # Market state: 30-day BTC return
        dataframe["btc_return_30d"] = dataframe["close"].pct_change(periods=self.RETURN_PERIOD)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        fear_subsiding = dataframe[f"cbbi_mom_{self.ENTRY_MOM}d"] > 0
        not_euphoric = dataframe["cbbi"] < self.CB_THRESHOLD
        trend_ok = dataframe["ema_fast"] > dataframe["ema_slow"]
        volume_ok = dataframe["volume"] > 0

        # Market state filter
        is_bull = dataframe["btc_return_30d"] > self.BULL_THRESHOLD
        is_choppy = (dataframe["btc_return_30d"] >= self.CHOPPY_THRESHOLD) & (~is_bull)
        strong_momentum = dataframe[f"cbbi_mom_{self.ENTRY_MOM}d"] > self.STRONG_MOM

        # Allow entry in: bull market OR choppy with strong momentum
        market_ok = is_bull | (is_choppy & strong_momentum)

        dataframe.loc[
            fear_subsiding & not_euphoric & trend_ok & market_ok & volume_ok,
            "enter_long"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        confidence_falling = dataframe[f"cbbi_mom_{self.EXIT_MOM}d"] < self.EXIT_THRESHOLD
        extreme_greed = dataframe["cbbi"] > self.EXIT_CBBI
        trend_broken = dataframe["ema_fast"] < dataframe["ema_slow"]

        dataframe.loc[
            (confidence_falling | extreme_greed | trend_broken) & (dataframe["volume"] > 0),
            "exit_long"
        ] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
