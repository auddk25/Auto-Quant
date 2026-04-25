"""MtfTrend31 -- Ultimate Faith (The 1000% Challenger)

Paradigm: Pure Trend Rider + EMA200 Absolute Exit
Hypothesis: Achieve maximum compounding by removing all micro-stoplosses. 
            Bull markets have 20-30% "fakes" that break active traders.
            - Defense: Only exit when 1d EMA200 is lost (Bear Market).
            - Attack: 100% BTC initial allocation.
            - Pyramiding: Add 50% extra size when trend accelerates (ADX > 35).
            - Dynamic TP: 1h Blow-off detection to cycle the pyramid portion.
Parent: MtfTrend30 + User Hint
Created: R56
Status: Training (Target 1000%)
"""

from pandas import DataFrame
from typing import Optional, Union
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade

class MtfTrend31(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # Leverage the stacking to go > 100%
    position_stacking = True
    max_open_trades = 2
    
    minimal_roi = {"0": 100} 
    stoploss = -0.99 # NO STOPLOSS as per user instruction

    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["dev"] = (dataframe["close"] - dataframe["ema20"]) / dataframe["ema20"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        # Macro Bull: Above 200 EMA
        is_bull = (dataframe["close_1d"] > dataframe["ema200_1d"])
        
        # 1. CORE ENTRY: Full 100% of first slot
        core_entry = is_bull & (dataframe["volume"] > 0)
        
        # 2. PYRAMID: Add 50% more if trend is vertical
        pyramid_entry = is_bull & (dataframe["adx"] > 35) & (dataframe["dev"] < 0.05)

        dataframe.loc[core_entry, "enter_long"] = 1
        dataframe.loc[core_entry, "enter_tag"] = "core"
        
        dataframe.loc[pyramid_entry, "enter_long"] = 1
        dataframe.loc[pyramid_entry, "enter_tag"] = "pyramid"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ABSOLUTE EXIT: 1d Close below 200 EMA
        exit_cond = (dataframe["close_1d"] < dataframe["ema200_1d"])
        
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[Union[str, bool]]:
        
        # Dynamic Swing Exit for Pyramid only
        if trade.enter_tag == "pyramid":
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            last_candle = dataframe[dataframe['date'] <= current_time].iloc[-1]
            
            # If price is 15% away from 1h EMA20 -> Blow-off Top
            if current_rate > last_candle['ema20'] * 1.15:
                return "pyramid_blowoff"

        return None

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        # Each trade uses 50% of account. With 2 trades (core+pyramid) = 100%
        # If we want to test leverage, we could return more.
        return self.wallets.get_total_stake_amount() * 0.495
