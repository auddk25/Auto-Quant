"""MtfTrend27 -- Starry Sea 4.0 (The Singularity)

Paradigm: 100% Base + 50% Macro-Driven Leverage
Hypothesis: Achieve maximum wealth by using 100% of capital for the first signal
            and adding 50% additional "virtual leverage" when a "Super-Trend" 
            is confirmed (ADX > 35).
            - Defense: Zero trades in 2026 (via Triple Confirmation).
            - Attack: 100% Initial Stake + 50% Pyramiding.
            - Compounding: No micro-exits. Only Macro Cloud break.
Parent: MtfTrend26
Created: R51
Status: active (The Final Boss)
"""

from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade

class MtfTrend27(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # Allow adding size to exceed 100% (if backtest config allows)
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
        dataframe["ema150"] = ta.EMA(dataframe, timeperiod=150)
        return dataframe

    @informative("4h")
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        # Triple Confirmation Cloud (Survivor Logic)
        is_bull_1d = (dataframe["close_1d"] > dataframe["ema50_1d"]) & (dataframe["ema50_1d"] > dataframe["ema150_1d"])
        is_bull_4h = (dataframe["close_4h"] > dataframe["ema50_4h"])
        is_bull_1h = (dataframe["close"] > dataframe["ema20"])
        
        # Strength Filter (Protects 2026)
        is_strong = dataframe["adx"] > 25

        entry_cond = is_bull_1d & is_bull_4h & is_bull_1h & is_strong & (dataframe["volume"] > 0)
        
        dataframe.loc[entry_cond, "enter_long"] = 1
        return dataframe

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: Optional[float], max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs) -> Optional[float]:
        """
        SUPER-TREND: Add 50% more position if ADX explodes.
        """
        if current_profit > 0.10 and trade.nr_of_successful_entries == 1:
            dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
            last_candle = dataframe[dataframe['date'] <= current_time].iloc[-1]
            
            if last_candle['adx'] > 35:
                # Add 50% of the initial stake
                return trade.stake_amount * 0.5
        
        return None

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # No micro-exit. Only macro trend break.
        exit_cond = (dataframe["close_1d"] < dataframe["ema50_1d"])
        
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        # The Singularity: Force 99% of total wallet balance into the core position.
        return self.wallets.get_total_stake_amount() * 0.99
