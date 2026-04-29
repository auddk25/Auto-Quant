"""MtfTrendCbbiMultiTF — Multi-Timeframe CBBI Strategy

Uses 1h for entry signals and 4h for trend confirmation.

Entry logic:
- 1h: CBBI momentum > 0 (fear subsiding)
- 1h: CBBI < 0.65 (not euphoric)
- 4h: EMA100 > EMA200 (higher timeframe trend up)

Exit logic:
- 1h: CBBI momentum < -0.02 (confidence falling)
- OR 1h: CBBI > 0.80 (extreme greed)
- OR 4h: EMA100 < EMA200 (higher timeframe trend broken)

Parent: MtfTrendCbbiMomentumEnsemble (R105)
Created: R107 (multi-timeframe exploration)
Status: active
"""
from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from autoq_data.cycle_bridge import merge_cbbi


class MtfTrendCbbiMultiTF(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
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

    @informative("4h")
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """4h timeframe for trend confirmation."""
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.TREND_FAST)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.TREND_SLOW)
        return dataframe

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """1d timeframe for reference."""
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.TREND_FAST)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.TREND_SLOW)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """1h timeframe for entry signals."""
        dataframe = merge_cbbi(dataframe, metadata)
        for n in [2, 3, 4, 5, 6]:
            dataframe[f"cbbi_mom_{n}d"] = dataframe["cbbi"] - dataframe["cbbi"].shift(24 * n)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        # 1h conditions (entry signals)
        fear_subsiding = dataframe[f"cbbi_mom_{self.ENTRY_MOM}d"] > 0
        not_euphoric = dataframe["cbbi"] < self.CB_THRESHOLD
        volume_ok = dataframe["volume"] > 0

        # 4h condition (trend confirmation)
        trend_ok_4h = dataframe["ema_fast_4h"] > dataframe["ema_slow_4h"]

        dataframe.loc[
            fear_subsiding & not_euphoric & trend_ok_4h & volume_ok,
            "enter_long"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1h exit conditions
        confidence_falling = dataframe[f"cbbi_mom_{self.EXIT_MOM}d"] < self.EXIT_THRESHOLD
        extreme_greed = dataframe["cbbi"] > self.EXIT_CBBI

        # 4h exit condition
        trend_broken_4h = dataframe["ema_fast_4h"] < dataframe["ema_slow_4h"]

        dataframe.loc[
            (confidence_falling | extreme_greed | trend_broken_4h) & (dataframe["volume"] > 0),
            "exit_long"
        ] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
