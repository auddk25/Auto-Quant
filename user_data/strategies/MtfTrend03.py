"""MtfTrend03 -- BTC-only daily EMA trend + 4h crossover + macro + hold trend

Paradigm: pure trend-following, single asset, macro-confirmed
Hypothesis: Enter on structural oversold (4h EMA crossover in daily uptrend)
            ONLY when macro regime is favorable (positive funding + stablecoin
            inflow + low DVOL). Hold the trend using daily EMA, not 4h noise.
            Exit in stages at overbought levels via custom_exit.
            BTC-only, no ETH.
Parent: MtfTrend02 (fork, BTC-only)
Created: R6
Status: active
Uses MTF: yes (1d trend filter, 4h momentum entry, macro factors)
"""

from pandas import DataFrame
from datetime import datetime
from typing import Optional
import talib.abstract as ta

from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade
from autoq_data.strategy_bridge import merge_external_factors


class MtfTrend03(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

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
            columns=["funding_rate", "stablecoin_mcap_growth", "btc_dvol"],
        )
        dataframe["funding_rate"] = dataframe["funding_rate"].fillna(0)
        dataframe["stablecoin_mcap_growth"] = dataframe["stablecoin_mcap_growth"].fillna(0)
        dataframe["btc_dvol"] = dataframe["btc_dvol"].fillna(60)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        entry = (
            (dataframe["close_1d"] > dataframe["ema50_1d"])
            & (dataframe["ema50_1d"] > dataframe["ema150_1d"])
            & (dataframe["ema12_4h"] > dataframe["ema26_4h"])
            & (dataframe["ema12_prev_4h"] <= dataframe["ema26_prev_4h"])
            & (dataframe["rsi_4h"] > 40)
            & (dataframe["rsi_4h"] < 70)
            & (dataframe["funding_rate"] > 0)
            & (dataframe["stablecoin_mcap_growth"] > 0)
            & (dataframe["btc_dvol"] < 65)
            & (dataframe["volume"] > 0)
        )
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
        if current_profit >= 0.40:
            return "overbought_40pct"
        if current_profit >= 0.25 and trade.nr_of_successful_exits == 0:
            return "partial_25pct"
        return None

    def custom_stoploss(self, pair: str, trade, current_time, current_rate,
                        current_profit, **kwargs) -> float:
        if current_profit >= 0.30:
            return -0.05
        return self.stoploss
