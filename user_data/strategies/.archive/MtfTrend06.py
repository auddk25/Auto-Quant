"""MtfTrend06 -- MTF trend + macro regime filter + hold trend + scaled exit

Paradigm: trend-state persistent entry for max position utilization
Hypothesis: Enter whenever daily trend + macro are favorable (no crossover needed). Stay in trend.
            ONLY when macro regime is favorable (positive funding + stablecoin
            inflow + low DVOL). Hold the trend using daily EMA, not 4h noise.
            Exit in stages at overbought levels via custom_exit.
            ETH requires BTC gate.
Parent: MtfTrend05 R21 (fork)
Created: R22
Status: active
Uses MTF: yes (1d trend, 4h entry, macro factors, cross-pair BTC for ETH)
"""

from pandas import DataFrame
from datetime import datetime
from typing import Optional
import talib.abstract as ta
import numpy as np

from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade
from autoq_data.strategy_bridge import merge_external_factors


class MtfTrend06(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    minimal_roi = {"0": 100}
    stoploss = -0.15

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

        if is_btc:
            rsi_cond = (dataframe["rsi_4h"] > 30) & (dataframe["rsi_4h"] < 80)
            crossover = dataframe["ema12_prev_4h"] <= dataframe["ema26_prev_4h"]
            cvd_cond = dataframe["cvd_24h"] > 0
            entry = trend_cond & momentum_cond & crossover & macro_cond & rsi_cond & cvd_cond & volume_cond
            dataframe.loc[entry, "enter_long"] = 1
        else:
            rsi_cond = (dataframe["rsi_4h"] > 25) & (dataframe["rsi_4h"] < 75)
            btc_gate = dataframe["btc_usdt_close_above_ema_1d"] == 1
            entry = trend_cond & momentum_cond & macro_cond & rsi_cond & btc_gate & volume_cond
            dataframe.loc[entry, "enter_long"] = 1

        return dataframe

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
        return self.stoploss
