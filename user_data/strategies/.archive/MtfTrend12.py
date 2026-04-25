"""MtfTrend12 -- Leveraged Pyramiding (The Bull Run Maximizer)

Paradigm: Aggressive Compounding (Pyramiding)
Hypothesis: In a proven macro bull market (SMA200), the safest move is to 
            increase size as the trade becomes profitable.
            Strategy starts with 100% allocation.
            Every time the trade hits +25% profit, we add another 25% 
            of the INITIAL balance to the position, effectively using 
            "virtual leverage" to maximize the vertical move.
Parent: MtfTrend09
Created: R36
Status: active
"""

from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade

class MtfTrend12(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # Enable position adjustment for pyramiding
    position_adjustment_enable = True
    max_entry_position_adjustment = 5  # Allow up to 5 add-ons
    
    max_open_trades = 1
    
    minimal_roi = {"0": 100}
    stoploss = -0.15 # Tighter SL for leveraged positions

    trailing_stop = False
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    startup_candle_count: int = 1

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["sma200"] = ta.SMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] == "BTC/USDT":
            # Initial entry
            is_bull = dataframe["close_1d"] > dataframe["sma200_1d"]
            dataframe.loc[is_bull & (dataframe["volume"] > 0), "enter_long"] = 1
        return dataframe

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: Optional[float], max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs) -> Optional[float]:
        """
        Pyramiding: Add more when in profit.
        For every 25% profit, add 25% more of the current total balance.
        """
        # Limit to BTC
        if trade.pair != "BTC/USDT":
            return None

        # Only pyramid if macro trend is still intact
        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        last_candle = dataframe[dataframe['date'] <= current_time].iloc[-1]
        if last_candle['close_1d'] < last_candle['sma200_1d']:
            return None

        # How many times have we added?
        count_adj = trade.nr_of_successful_entries
        
        # Pyramid every 20% profit gain
        target_profit = count_adj * 0.20
        
        if current_profit > target_profit and count_adj <= self.max_entry_position_adjustment:
            # Add one unit of initial stake
            return trade.stake_amount
            
        return None

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Macro exit
        exit_cond = (dataframe["close_1d"] < dataframe["sma200_1d"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        # Use only 30% of wallet initially to leave room for 5x pyramiding
        # (30% + 30%*5 = 180% virtual leverage)
        return self.wallets.get_total_stake_amount() * 0.30
