"""MtfTrendCbbiMacdFusion — CBBI + MACD Fusion Strategy

Combines CBBI momentum with MACD for trend confirmation.

Entry logic:
- CBBI momentum > 0 (fear subsiding)
- CBBI < 0.65 (not euphoric)
- EMA100 > EMA200 (trend up)
- MACD > MACD signal (momentum confirming)

Exit logic:
- CBBI momentum < -0.02 (confidence falling)
- OR CBBI > 0.80 (extreme greed)
- OR EMA100 < EMA200 (trend broken)
- OR MACD < MACD signal (momentum reversing)

Parent: MtfTrendCbbiMomentumEnsemble (R105)
Created: R108 (multi-indicator fusion exploration)
Status: active
"""
from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy
from autoq_data.cycle_bridge import merge_cbbi


class MtfTrendCbbiMacdFusion(IStrategy):
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

    # ---- MACD Parameters (new) ----
    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9

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
        # MACD
        macd = ta.MACD(dataframe, fastperiod=self.MACD_FAST,
                       slowperiod=self.MACD_SLOW, signalperiod=self.MACD_SIGNAL)
        dataframe["macd"] = macd["macd"]
        dataframe["macd_signal"] = macd["macdsignal"]
        dataframe["macd_hist"] = macd["macdhist"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        fear_subsiding = dataframe[f"cbbi_mom_{self.ENTRY_MOM}d"] > 0
        not_euphoric = dataframe["cbbi"] < self.CB_THRESHOLD
        trend_ok = dataframe["ema_fast"] > dataframe["ema_slow"]
        macd_bullish = dataframe["macd"] > dataframe["macd_signal"]
        volume_ok = dataframe["volume"] > 0

        dataframe.loc[
            fear_subsiding & not_euphoric & trend_ok & macd_bullish & volume_ok,
            "enter_long"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        confidence_falling = dataframe[f"cbbi_mom_{self.EXIT_MOM}d"] < self.EXIT_THRESHOLD
        extreme_greed = dataframe["cbbi"] > self.EXIT_CBBI
        trend_broken = dataframe["ema_fast"] < dataframe["ema_slow"]
        macd_bearish = dataframe["macd"] < dataframe["macd_signal"]

        dataframe.loc[
            (confidence_falling | extreme_greed | trend_broken | macd_bearish) & (dataframe["volume"] > 0),
            "exit_long"
        ] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
