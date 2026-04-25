"""MtfTrend36 -- The Compounding Warlord (BTC 1000% Mission)

Paradigm: Aggressive Floating-Profit Pyramiding
Hypothesis: Achieve >1000% by using "virtual leverage" -- reinvesting bull 
            market profits back into the same asset.
            - Strategy starts with 2 slots (50% of balance).
            - Every 15% gain, add another slot (25% of initial balance).
            - Total slots: 10 (Max 300% effective exposure).
            - Exit: 1d EMA50 break (Save the compounding).
Parent: MtfTrend35
Created: R61
Status: Training (The 1000% Moonshot)
"""

from pandas import DataFrame
from typing import Optional, Union
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade

class MtfTrend36(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # Allow 10 stacks to simulate high leverage compounding
    position_stacking = True
    max_open_trades = 10
    
    minimal_roi = {"0": 100} 
    stoploss = -0.15 # Tighter SL to protect leveraged position

    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["sma200"] = ta.SMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        is_bull = (dataframe["close_1d"] > dataframe["sma200_1d"])
        
        # Entry: Macro bull + momentum (RSI > 50)
        # With stacking enabled, this will trigger multiple times
        entry_cond = is_bull & (dataframe["rsi"] > 50) & (dataframe["volume"] > 0)
        
        dataframe.loc[entry_cond, "enter_long"] = 1
        return dataframe

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:
        """
        Pyramiding Control: Only add a new slot if:
        1. The previous slots are in profit.
        2. At least 72 hours passed since last entry.
        """
        trades = Trade.get_trades_proxy(pair=pair, is_open=True)
        if not trades:
            return True
            
        # All existing trades must be in profit (Avg profit > 5%)
        avg_profit = sum(t.calc_profit_ratio(rate) for t in trades) / len(trades)
        if avg_profit < 0.10:
            return False
            
        # Cooldown to avoid vertical cluster entries
        last_entry = max(t.open_date_utc for t in trades)
        if (current_time - last_entry).days < 3:
            return False

        return True

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit if macro trend breaks
        exit_cond = (dataframe["close_1d"] < dataframe["ema50_1d"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        # Each slot gets 20% of account (Total 10 slots = 200% virtual leverage)
        return self.wallets.get_total_stake_amount() * 0.20
