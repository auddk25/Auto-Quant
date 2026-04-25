"""MtfTrend26 -- Starry Sea 3.0 (The Compounding Titan)

Paradigm: Aggressive Compounding + Zero-Loss Defense
Hypothesis: Achieve 1000%+ by combining 100% initial allocation with 
            selective pyramiding in strong trends, while using 
            triple-confirmation to stay out of the 2026 dump.
            - Defense: Zero trades in 2026 (confirmed by MtfTrend23 logic).
            - Attack: 100% core BTC + 50% technical pyramid.
            - Exit: Blow-off top detection (Price/EMA20 deviation).
Parent: MtfTrend25
Created: R50
Status: active (The 1000% Target)
"""

from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade

class MtfTrend26(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # Pyramid using multiple slots for the same pair
    position_stacking = True
    max_open_trades = 2
    
    minimal_roi = {"0": 100} 
    stoploss = -0.08

    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        
        # Deviation for blow-off top detection
        dataframe["dev"] = (dataframe["close"] - dataframe["ema20"]) / dataframe["ema20"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        # REGIME 1: STRONG BULL
        is_bull = (dataframe["close_1d"] > dataframe["ema50_1d"]) & (dataframe["ema50_1d"] > dataframe["ema200_1d"])
        
        # REGIME 2: STRENGTH FILTER
        is_strong = dataframe["adx"] > 25

        # 1. CORE ENTRY: 100% of first slot
        core_entry = is_bull & is_strong & (dataframe["volume"] > 0)
        
        # 2. PYRAMID ENTRY: Add second slot if already in strong trend and not overextended
        pyramid_entry = is_bull & (dataframe["adx"] > 35) & (dataframe["dev"] < 0.05)

        dataframe.loc[core_entry, "enter_long"] = 1
        dataframe.loc[core_entry, "enter_tag"] = "core"
        
        dataframe.loc[pyramid_entry, "enter_long"] = 1
        dataframe.loc[pyramid_entry, "enter_tag"] = "pyramid"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit if macro trend breaks
        exit_cond = (dataframe["close_1d"] < dataframe["ema50_1d"])
        
        # Exit pyramid ONLY if blow-off top detected
        blow_off = (dataframe["dev"] > 0.15) # 15% deviation from EMA20
        
        dataframe.loc[exit_cond, "exit_long"] = 1
        dataframe.loc[blow_off, "exit_tag"] = "blow_off_exit"
        
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        # Each slot gets 50% of the account
        # With 2 slots, total is 100%
        return self.wallets.get_total_stake_amount() * 0.495
