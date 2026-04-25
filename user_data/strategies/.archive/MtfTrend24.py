"""MtfTrend24 -- Starry Sea 1.0 (The Ultimate Hybrid)

Paradigm: Aggressive Trend + Conservative Filter
Hypothesis: Achieve >1000% by combining MtfTrend09's concentration 
            with MtfTrend23's triple-confirmation survival.
            - Bull: Price > 1d EMA50/150 + 4h EMA50 + 1h EMA50.
            - Strength: Only enter if ADX > 25.
            - Aggression: If ADX > 35 (Vertical Move), allow 1.5x position.
            - Defense: Exit on 1h EMA20 break or 1d Trend break.
Parent: MtfTrend23 + MtfTrend09
Created: R48
Status: active (The 1000% Candidate)
"""

from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade

class MtfTrend24(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # Full concentration + Pyramiding
    position_adjustment_enable = True
    max_entry_position_adjustment = 2 
    max_open_trades = 1
    
    minimal_roi = {"0": 100} 
    stoploss = -0.07        # Balanced SL

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
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Only BTC to ensure maximum alpha capture
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        # Triple Confirmation Cloud
        is_bull_1d = (dataframe["close_1d"] > dataframe["ema50_1d"]) & (dataframe["ema50_1d"] > dataframe["ema150_1d"])
        is_bull_4h = (dataframe["close_4h"] > dataframe["ema50_4h"])
        is_bull_1h = (dataframe["close"] > dataframe["ema50"])
        
        # Strength Filter
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
        Hyper-Drive: Add 50% more if ADX hits extreme levels (>40) 
        while already in profit.
        """
        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        last_candle = dataframe[dataframe['date'] <= current_time].iloc[-1]
        
        if last_candle['adx'] > 35 and current_profit > 0.05:
            if trade.nr_of_successful_entries <= self.max_entry_position_adjustment:
                return trade.stake_amount * 0.5
        
        return None

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit on 1h weakness or 1d bear
        exit_cond = (dataframe["close"] < dataframe["ema20"]) | (dataframe["close_1d"] < dataframe["ema50_1d"])
        
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        # Start with 60% to leave room for the 50% hyper-drive加仓
        return self.wallets.get_total_stake_amount() * 0.60
