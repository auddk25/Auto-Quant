"""MtfTrend07 -- MTF trend + macro + symmetric position stacking

Paradigm: position stacking in confirmed trend (symmetric)
Hypothesis: Use position stacking to allow up to 2 trades for the same pair
            if the other pair has no signal. This maximizes utilization
            of the 2 available slots. 
            Both BTC and ETH can enter on crossover OR pullback recovery.
            Cooldown: 72h between entries for the same pair.
Parent: MtfTrend05 R15 (fork)
Created: R23, evolved R26 (BEST)
Status: active
Uses MTF: yes (1d trend, 4h entry, macro factors)
"""

from pandas import DataFrame
from datetime import datetime, timedelta, timezone
from typing import Optional
import talib.abstract as ta
import numpy as np

from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade
from autoq_data.strategy_bridge import merge_external_factors


class MtfTrend07(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # Enable stacking with 2 slots
    position_stacking = True
    max_open_trades = 2

    minimal_roi = {"0": 100}
    stoploss = -0.08

    trailing_stop = False
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    startup_candle_count: int = 200

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema150"] = ta.EMA(dataframe, timeperiod=150)
        return dataframe

    @informative("1d", "BTC/USDT")
    def populate_indicators_1d_btc(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["close_above_ema"] = (dataframe["close"] > dataframe["ema50"]).astype(int)
        return dataframe

    @informative("4h")
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema12"] = ta.EMA(dataframe, timeperiod=12)
        dataframe["ema26"] = ta.EMA(dataframe, timeperiod=26)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema12_prev"] = dataframe["ema12"].shift(1)
        dataframe["ema26_prev"] = dataframe["ema26"].shift(1)
        dataframe["rsi_prev"] = dataframe["rsi"].shift(1)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = merge_external_factors(
            dataframe, metadata,
            columns=["funding_rate", "stablecoin_mcap_growth", "btc_dvol", "open_interest", "taker_delta_volume"],
        )
        dataframe["funding_rate"] = dataframe["funding_rate"].fillna(0)
        dataframe["stablecoin_mcap_growth"] = dataframe["stablecoin_mcap_growth"].fillna(0)
        dataframe["btc_dvol"] = dataframe["btc_dvol"].fillna(60)
        dataframe["open_interest"] = dataframe["open_interest"].ffill()
        dataframe["oi_rising"] = (
            dataframe["open_interest"] > dataframe["open_interest"].shift(24)
        ).astype(int)
        dataframe["taker_delta_volume"] = dataframe["taker_delta_volume"].fillna(0)
        dataframe["cvd_24h"] = dataframe["taker_delta_volume"].rolling(24).sum()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        is_btc = metadata["pair"] == "BTC/USDT"

        trend_cond = (
            (dataframe["close_1d"] > dataframe["ema50_1d"])
            & (dataframe["ema50_1d"] > dataframe["ema150_1d"])
        )
        momentum_cond = (
            (dataframe["ema12_4h"] > dataframe["ema26_4h"])
        )
        macro_cond = (
            (dataframe["funding_rate"] > 0)
            & (dataframe["stablecoin_mcap_growth"] > 0)
            & (dataframe["btc_dvol"] < 65)
            & (dataframe["oi_rising"] == 1)
        )
        volume_cond = dataframe["volume"] > 0
        cvd_cond = dataframe["cvd_24h"] > 0

        # Pullback recovery signal (symmetric)
        pullback_recovery = (dataframe["rsi_prev_4h"] < 50) & (dataframe["rsi_4h"] >= 50)

        if is_btc:
            # BTC: crossover OR pullback recovery
            crossover = dataframe["ema12_prev_4h"] <= dataframe["ema26_prev_4h"]
            rsi_range = (dataframe["rsi_4h"] > 40) & (dataframe["rsi_4h"] < 70)
            entry = trend_cond & momentum_cond & (crossover | pullback_recovery) & macro_cond & rsi_range & cvd_cond & volume_cond
            dataframe.loc[entry, "enter_long"] = 1
        else:
            # ETH: standard rules from MtfTrend05 + pullback recovery
            rsi_cond = (dataframe["rsi_4h"] > 30) & (dataframe["rsi_4h"] < 60)
            btc_gate = dataframe["btc_usdt_close_above_ema_1d"] == 1
            entry = trend_cond & momentum_cond & macro_cond & (rsi_cond | pullback_recovery) & btc_gate & volume_cond
            dataframe.loc[entry, "enter_long"] = 1

        return dataframe

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:
        """
        Implement 72h cooldown for stacking.
        """
        trades = Trade.get_trades_proxy(pair=pair, is_open=True)
        if not trades:
            return True
            
        last_entry = max(t.open_date_utc for t in trades)
        if (current_time - last_entry).total_seconds() < 72 * 3600:
            return False

        return True

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe["ema50_1d"] < dataframe["ema150_1d"]),
            "exit_long",
        ] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        if current_profit >= 0.30:
            return "overbought_40pct"
        if current_profit >= 0.25 and trade.nr_of_successful_exits == 0:
            return "partial_25pct"
        return None

    def custom_stoploss(self, pair: str, trade, current_time, current_rate,
                        current_profit, **kwargs) -> float:
        if current_profit >= 0.30:
            return -0.05
        if pair == "ETH/USDT":
            return -0.06
        return self.stoploss
