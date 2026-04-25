"""MtfTrend39 -- Helios (SOL 1000% Moonshot)

Paradigm: High-Velocity Trend Riding
Hypothesis: To achieve >1000%, we must ride the most volatile assets (SOL) 
            with minimal filters and maximum trend persistence.
            - Entry: 1d Price > EMA20 + 1h MACD Gold Cross.
            - Exit: 1d Price < EMA10 (Ultra-fast trend exit to lock in parbolic moves).
            - Stoploss: -0.15 (To survive mid-cycle wicks).
            - Concentration: 100% SOL.
Parent: MtfTrend09
Created: R65
Status: active (The 1000% Weapon)
"""

from pandas import DataFrame
from typing import Optional, Union
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade

class MtfTrend39(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # Full concentration
    max_open_trades = 1
    
    minimal_roi = {"0": 100} 
    stoploss = -0.15 

    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema10"] = ta.EMA(dataframe, timeperiod=10)
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Entry: 1d Trend is healthy + 1h MACD gold cross
        is_bull_1d = (dataframe["close_1d"] > dataframe["ema20_1d"])
        
        entry_cond = is_bull_1d & (dataframe['macd'] > dataframe['macdsignal']) & (dataframe["volume"] > 0)
        
        dataframe.loc[entry_cond, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Fast Exit: 1d Close below EMA10 (Protects the 10x gains)
        exit_cond = (dataframe["close_1d"] < dataframe["ema10_1d"])
        
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
