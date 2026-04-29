"""MtfTrendCbbiMultiTF2 — Multi-Timeframe CBBI Strategy v2

Uses 4h for both entry and exit signals with 1h CBBI momentum.

Entry logic:
- 4h: CBBI momentum > 0 (fear subsiding on higher TF)
- 4h: CBBI < 0.65 (not euphoric on higher TF)
- 4h: EMA100 > EMA200 (trend up on higher TF)

Exit logic:
- 4h: CBBI momentum < -0.02 (confidence falling on higher TF)
- OR 4h: CBBI > 0.80 (extreme greed on higher TF)
- OR 4h: EMA100 < EMA200 (trend broken on higher TF)

Parent: MtfTrendCbbiMultiTF (R107)
Created: R107v2 (multi-timeframe exploration)
Status: active
"""
from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from autoq_data.cycle_bridge import merge_cbbi


class MtfTrendCbbiMultiTF2(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "4h"  # Use 4h as base timeframe
    can_short = False
    max_open_trades = 1
    minimal_roi = {"0": 100}
    stoploss = -0.25
    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    # ---- Parameters ----
    ENTRY_MOM = 3
    CB_THRESHOLD = 0.65
    EXIT_MOM = 3
    EXIT_THRESHOLD = -0.02
    EXIT_CBBI = 0.80
    TREND_FAST = 100
    TREND_SLOW = 200

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """1d timeframe for reference."""
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.TREND_FAST)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.TREND_SLOW)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """4h timeframe for entry/exit signals."""
        dataframe = merge_cbbi(dataframe, metadata)
        # CBBI is daily, so we need to resample to 4h
        # For now, use the same approach as 1h but with 4h candles
        for n in [2, 3, 4, 5, 6]:
            # On 4h data, CBBI is daily — use shift(6*N) for N-day change (6 4h candles per day)
            dataframe[f"cbbi_mom_{n}d"] = dataframe["cbbi"] - dataframe["cbbi"].shift(6 * n)
        # Trend EMAs
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.TREND_FAST)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.TREND_SLOW)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        fear_subsiding = dataframe[f"cbbi_mom_{self.ENTRY_MOM}d"] > 0
        not_euphoric = dataframe["cbbi"] < self.CB_THRESHOLD
        trend_ok = dataframe["ema_fast"] > dataframe["ema_slow"]
        volume_ok = dataframe["volume"] > 0

        dataframe.loc[
            fear_subsiding & not_euphoric & trend_ok & volume_ok,
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
