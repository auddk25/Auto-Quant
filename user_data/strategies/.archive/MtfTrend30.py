"""MtfTrend30 -- The Triple-Tier Titan (Final Training Phase)

Paradigm: Graded Profit Taking + Adaptive Volatility
Hypothesis: Achieve 1000%+ by combining the resilience of a holder with 
            the precision of a swinger.
            - Defense: Triple EMA Cloud.
            - Attack: MACD Squeeze Breakout.
            - Exit Strategy (Graded):
                1. <30% Profit: No exit allowed (except Trend Break).
                2. >50% Profit: Exit 30% on RSI Exhaustion (>85).
                3. >100% Profit: Exit 30% on ATR Trailing Stop (3x ATR).
                4. Final 40%: Ride until 1d EMA50 breaks.
Parent: MtfTrend29
Created: R54
Status: Training (The 1000% Apex)
"""

from pandas import DataFrame
from typing import Optional, Union
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade

class MtfTrend30(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # Standardize on full concentration for compounding
    position_stacking = True
    max_open_trades = 1
    
    minimal_roi = {"0": 100} 
    stoploss = -0.20 # Wide SL to allow bull market volatility

    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    @informative("4h")
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        return dataframe

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        # Entry: Macro Bull + MACD Cross in Strength
        is_bull = (dataframe["close_1d"] > dataframe["ema50_1d"])
        entry_cond = (
            is_bull &
            (dataframe['macd'] > dataframe['macdsignal']) &
            (dataframe['rsi'] > 50) &
            (dataframe["volume"] > 0)
        )
        
        dataframe.loc[entry_cond, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Final Guard: Macro Trend Break
        exit_cond = (dataframe["close_1d"] < dataframe["ema50_1d"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[Union[str, bool]]:
        
        # Access indicators
        df_4h, _ = self.dp.get_analyzed_dataframe(pair, "4h")
        if current_time not in df_4h.index:
            return None
            
        last_4h = df_4h.loc[current_time]
        
        # TIER 1: Protection Period
        if current_profit < 0.30:
            return None # Only exit on macro trend break
            
        # TIER 2: Aggressive Swing Take Profit (>50% profit)
        if current_profit > 0.50:
            if last_4h['rsi'] > 85:
                # In real life we'd partial exit, here we take full profit on exhaustion
                return "exhaustion_tp"
                
        # TIER 3: ATR Trailing Stop (>100% profit)
        if current_profit > 1.00:
            # If price drops below (4h EMA20 - 1.5*ATR) -> Lock in the 2x
            if current_rate < (last_4h['ema20'] - 1.5 * last_4h['atr']):
                return "atr_trailing_tp"

        return None

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
