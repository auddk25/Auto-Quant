"""MtfTrendCbbiMomentumEnsembleDSL — Ensemble CBBI with Dynamic Stoploss

Same as MtfTrendCbbiMomentumEnsemble but with ATR-based dynamic stoploss.

Dynamic stoploss logic:
- ATR(20) on 1h timeframe measures volatility
- Stoploss = max(fixed_stoploss, ATR_stoploss)
- ATR_stoploss = -2 * ATR(20) / entry_price
- Trailing stop activates after 5% profit

Parent: MtfTrendCbbiMomentumEnsemble (R105)
Created: R106 (dynamic stoploss test)
Status: active
"""
from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative, stoploss_from_open
from autoq_data.cycle_bridge import merge_cbbi


class MtfTrendCbbiMomentumEnsembleDSL(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = False
    max_open_trades = 1
    minimal_roi = {"0": 100}
    stoploss = -0.25  # Fixed stoploss as fallback
    process_only_new_candles = True
    use_exit_signal = True
    use_custom_stoploss = True
    startup_candle_count: int = 200

    # ---- Trailing stop (disabled - use custom_stoploss instead) ----
    trailing_stop = False

    # ---- Fixed parameters ----
    ENTRY_MOM = 3
    CB_THRESHOLD = 0.65
    EXIT_MOM = 3
    EXIT_CBBI = 0.80
    TREND_FAST = 100
    TREND_SLOW = 200
    ATR_PERIOD = 20
    ATR_MULTIPLIER = 3.0  # Stoploss = -3 * ATR (wider)

    # ---- Ensemble variants (EXIT_THRESHOLD only) ----
    VARIANT_THRESHOLDS = [-0.020, -0.018, -0.015]
    VOTE_THRESHOLD = 2  # Need ≥2 variants to agree

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema_fast"] = ta.EMA(dataframe, timeperiod=self.TREND_FAST)
        dataframe["ema_slow"] = ta.EMA(dataframe, timeperiod=self.TREND_SLOW)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = merge_cbbi(dataframe, metadata)
        for n in [2, 3, 4, 5, 6]:
            dataframe[f"cbbi_mom_{n}d"] = dataframe["cbbi"] - dataframe["cbbi"].shift(24 * n)
        # ATR for dynamic stoploss
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.ATR_PERIOD)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        fear_subsiding = dataframe[f"cbbi_mom_{self.ENTRY_MOM}d"] > 0
        not_euphoric = dataframe["cbbi"] < self.CB_THRESHOLD
        trend_ok = dataframe["ema_fast_1d"] > dataframe["ema_slow_1d"]
        volume_ok = dataframe["volume"] > 0

        dataframe.loc[
            fear_subsiding & not_euphoric & trend_ok & volume_ok,
            "enter_long"
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_votes = 0
        for threshold in self.VARIANT_THRESHOLDS:
            confidence_falling = dataframe[f"cbbi_mom_{self.EXIT_MOM}d"] < threshold
            extreme_greed = dataframe["cbbi"] > self.EXIT_CBBI
            trend_broken = dataframe["ema_fast_1d"] < dataframe["ema_slow_1d"]

            variant_exit = confidence_falling | extreme_greed | trend_broken
            exit_votes += variant_exit.astype(int)

        dataframe.loc[
            (exit_votes >= self.VOTE_THRESHOLD) & (dataframe["volume"] > 0),
            "exit_long"
        ] = 1
        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        """ATR-based dynamic stoploss - only tighten after profit."""
        # Only apply dynamic stoploss after 20% profit
        if current_profit < 0.20:
            return self.stoploss

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(dataframe) < 1:
            return self.stoploss

        last_candle = dataframe.iloc[-1]
        atr = last_candle.get("atr", 0)

        if atr > 0 and current_rate > 0:
            # ATR stoploss as percentage of entry price
            atr_stoploss = -(self.ATR_MULTIPLIER * atr) / trade.open_rate
            # Only tighten if ATR stoploss is tighter than fixed
            if atr_stoploss > self.stoploss:
                return atr_stoploss

        return self.stoploss

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
