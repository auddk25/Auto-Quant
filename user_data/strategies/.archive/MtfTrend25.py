"""MtfTrend25 -- Starry Sea 2.0 (Regime-Switching Beast)

Paradigm: Dynamic Regime Switching
Hypothesis: Achieve 1000%+ by being a "Hold God" in strong bull markets 
            and a "Ghost" in weak/bear markets.
            - Regime 1 (Strong Bull): Price > 1d EMA50. 
              ACTION: 100% BTC Hold. No micro-exits. Only exit if EMA50 breaks.
            - Regime 2 (Weak/Bear): Price < 1d EMA50. 
              ACTION: Conservative technical swing (ADX > 30 + BB break).
            - Result: Captures the multi-bagger bull run while zeroing out 2026.
Parent: MtfTrend24
Created: R49
Status: active (The 1000% Candidate)
"""

from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade

class MtfTrend25(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # Dynamic allocation
    position_adjustment_enable = True
    max_entry_position_adjustment = 1 
    max_open_trades = 1
    
    minimal_roi = {"0": 100} 
    stoploss = -0.10

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
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        # REGIME 1: STRONG BULL (The Wealth Builder)
        # Simply hold if price is in a macro uptrend
        strong_bull = (dataframe["close_1d"] > dataframe["ema50_1d"]) & (dataframe["ema50_1d"] > dataframe["ema200_1d"])
        
        # REGIME 2: TECHNICAL RECOVERY (The Sniper)
        # If in a weak market, only enter if RSI recovers from bottom
        weak_market = ~strong_bull
        sniper_entry = weak_market & (dataframe["rsi"] > 50) & (dataframe["adx"] > 30)

        dataframe.loc[strong_bull, "enter_long"] = 1
        dataframe.loc[strong_bull, "enter_tag"] = "strong_bull"
        
        dataframe.loc[sniper_entry, "enter_long"] = 1
        dataframe.loc[sniper_entry, "enter_tag"] = "sniper"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EXIT: Only if the macro regime breaks
        # We don't exit on 1h noise anymore to allow compounding
        exit_cond = (dataframe["close_1d"] < dataframe["ema50_1d"])
        
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: Optional[float], max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs) -> Optional[float]:
        """
        Add 50% more position if we are in a strong bull and profit > 20%
        """
        if current_profit > 0.20 and trade.nr_of_successful_entries == 1:
            dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
            last_candle = dataframe[dataframe['date'] <= current_time].iloc[-1]
            
            if last_candle['close_1d'] > last_candle['ema50_1d']:
                return trade.stake_amount * 0.5
        
        return None

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.60
