"""MtfTrend22 -- The 2026 Sniper (Adaptive Regime Strategy)

Paradigm: Dual-Regime (Trend + Mean Reversion)
Hypothesis: To beat BuyAndHold and survive 2026, we must switch behaviors.
            - Bull Regime (Price > 1d EMA50): Hold 100% BTC to capture growth.
            - Bear Regime (Price < 1d EMA50): Long-only Sniper. 
              Only enter on extreme 1h RSI oversold + BB Bottom.
            - Objective: Avoid the 16% drawdown of 2026 while catching 
              the 2023-2025 multi-bagger move.
Parent: MtfTrend19
Created: R46
Status: active (Validation Set Challenger)
"""

from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade

class MtfTrend22(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # Full concentration
    max_open_trades = 1
    
    minimal_roi = {
        "0": 0.15,      # Bear regime: quick 15% 
        "1440": 0.05,   # Bear regime: exit if after 24h still in profit
        "10080": 100    # Bull regime: hold long
    }
    
    stoploss = -0.10 # Standard SL to prevent catastrophic drops in 2026

    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Tech Indicators
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_lower'] = bollinger['lowerband']
        dataframe['bb_middle'] = bollinger['middleband']
        
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Determine Regime
        is_bull = (dataframe["close_1d"] > dataframe["ema50_1d"])
        
        # 1. BULL ENTRY (Trend Following)
        # Re-enter if price crosses above 1h EMA20 while in a 1d bull market
        bull_entry = is_bull & (dataframe["close"] > dataframe["ema20"]) & (dataframe["rsi"] > 50)
        
        # 2. BEAR ENTRY (Sniper Mean Reversion)
        # Extreme oversold in a macro downtrend
        bear_entry = (~is_bull) & (dataframe["rsi"] < 25) & (dataframe["close"] < dataframe["bb_lower"])

        dataframe.loc[bull_entry, "enter_long"] = 1
        dataframe.loc[bull_entry, "enter_tag"] = "bull_trend"
        
        dataframe.loc[bear_entry, "enter_long"] = 1
        dataframe.loc[bear_entry, "enter_tag"] = "bear_sniper"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        is_bull = (dataframe["close_1d"] > dataframe["ema50_1d"])
        
        # Exit for Bull Trend: Only if 1d EMA50 breaks
        bull_exit = is_bull & (dataframe["close_1d"] < dataframe["ema50_1d"])
        
        # Exit for Bear Sniper: Touch of 1h EMA20 or BB Middle
        bear_exit = (~is_bull) & (dataframe["close"] > dataframe["bb_middle"])

        dataframe.loc[bull_exit, "exit_long"] = 1
        dataframe.loc[bull_exit, "exit_tag"] = "bull_exit"
        
        dataframe.loc[bear_exit, "exit_long"] = 1
        dataframe.loc[bear_exit, "exit_tag"] = "bear_exit"

        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
