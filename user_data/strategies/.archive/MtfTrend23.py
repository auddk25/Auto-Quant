"""MtfTrend23 -- The Trend Sentinel (Triple Confirmation)

Paradigm: Conservative MTF Trend Following
Hypothesis: To achieve 1000%+ compounded returns, survival in 2026 is priority #1.
            - Strategy only enters when 1h, 4h, and 1d timeframes are ALL BULLISH.
            - Uses ADX > 25 to ensure the trend is strong (not a range-bound fakeout).
            - Exits immediately if the shortest timeframe (1h) breaks support.
Parent: MtfTrend07
Created: R47
Status: active (Validation Set Defender)
"""

from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade

class MtfTrend23(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # Full concentration
    max_open_trades = 1
    
    minimal_roi = {"0": 100} # No automatic profit taking, follow the trend
    stoploss = -0.05        # Tight SL for survival

    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema150"] = ta.EMA(dataframe, timeperiod=150)
        return dataframe

    @informative("4h")
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Tech Indicators
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1. 1d Trend
        is_bull_1d = (dataframe["close_1d"] > dataframe["ema50_1d"]) & (dataframe["ema50_1d"] > dataframe["ema150_1d"])
        
        # 2. 4h Trend
        is_bull_4h = (dataframe["close_4h"] > dataframe["ema50_4h"])
        
        # 3. 1h Momentum + Strength
        is_bull_1h = (dataframe["close"] > dataframe["ema50"])
        is_strong = dataframe["adx"] > 25

        # ENTRY: Triple Confirmation + Strength
        entry_cond = is_bull_1d & is_bull_4h & is_bull_1h & is_strong & (dataframe["volume"] > 0)
        
        dataframe.loc[entry_cond, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit if any core trend breaks (starting with 1h)
        exit_cond = (dataframe["close"] < dataframe["ema20"]) | (dataframe["close_1d"] < dataframe["ema50_1d"])
        
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
