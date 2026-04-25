"""MtfTrend32 -- Macro Dynamic Compounder (Starry Sea 6.0)

Paradigm: High-Stakes Trend Rider + Regime-Based Defense
Hypothesis: Achieve 1000%+ by being a "Strong-Hand Holder" during the parabolic 
            phases and a "Disciplined Trader" during the mid-cycle wobbles.
            - Initial State: 100% Allocation to the leader (BTC).
            - Strong Bull (Price > 1d EMA50): Zero Stoploss. Faith mode.
            - Warning Zone (Price < 1d EMA50 but > EMA200): Dynamic 15% Trailing SL.
            - Ultimate Exit: 1d EMA200 Break.
Parent: MtfTrend31
Created: R57
Status: Training (The 1000% Final Push)
"""

from pandas import DataFrame
from typing import Optional, Union
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade

class MtfTrend32(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # Full concentration to maximize compounding from day 1
    position_stacking = False
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
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        # Macro Entry: Confirmed uptrend (Price > 200 EMA)
        entry_cond = (dataframe["close_1d"] > dataframe["ema200_1d"]) & (dataframe["volume"] > 0)
        
        dataframe.loc[entry_cond, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Ultimate Exit: Bear Market confirmed
        exit_cond = (dataframe["close_1d"] < dataframe["ema200_1d"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[Union[str, bool]]:
        
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe[dataframe['date'] <= current_time].iloc[-1]
        
        # 1. Blow-off Top Protection (Extreme Overbought)
        if last_candle['rsi'] > 90:
            return "blowoff_exit"
            
        #  Regimes:
        is_strong_bull = last_candle['close_1d'] > last_candle['ema50_1d']
        
        # 2. Dynamic Defense in Warning Zone
        if not is_strong_bull:
            # We are in the EMA50-EMA200 sandwich.
            # If we drop more than 15% from the highest point in this zone, exit.
            # (Using a simplified profit-based proxy here)
            if current_profit < -0.15: # Standard SL becomes active in warning zone
                return "warning_zone_sl"

        return None

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        # ALL-IN: Maximum alpha
        return self.wallets.get_total_stake_amount() * 0.99
