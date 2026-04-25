"""MtfTrendSmartHold -- Instant Entry + Bear-Aware Exit

Paradigm: Hold by default, only exit on confirmed danger.
Hypothesis: The biggest mistake active strategies make is staying out too much.
            BuyAndHold wins because it's ALWAYS in. We replicate this by:
            - Entering immediately (like BuyAndHold)
            - Exiting ONLY on extreme bear confirmation:
              1. Death cross (EMA50 < EMA200) AND
              2. Price below SMA200
            - Re-entering when bull trend resumes
            This should capture virtually all of the bull run while avoiding
            the worst bear markets.
Parent: MtfTrendGoldenCross + MtfTrendBear01
Created: R90
Status: active
"""
from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative


class MtfTrendSmartHold(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = False
    max_open_trades = 1
    minimal_roi = {"0": 100}
    stoploss = -0.99
    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["sma200"] = ta.SMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        # Enter when: bull market confirmed (EMA50 > EMA200 AND close > SMA200)
        # OR immediately on start (to capture early recovery)
        is_bull = (
            (dataframe["ema50_1d"] > dataframe["ema200_1d"])
            & (dataframe["close_1d"] > dataframe["sma200_1d"])
        )
        # Also enter if both EMAs and SMA are NaN (startup period) — just get in
        no_data = dataframe["ema50_1d"].isna()
        buy_cond = (is_bull | no_data) & (dataframe["volume"] > 0)
        dataframe.loc[buy_cond, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit ONLY when: death cross AND below SMA200 (both required)
        death_cross = dataframe["ema50_1d"] < dataframe["ema200_1d"]
        below_sma = dataframe["close_1d"] < dataframe["sma200_1d"]
        # Only exit when BOTH confirm — this is very rare
        dataframe.loc[death_cross & below_sma, "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
