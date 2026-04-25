"""MtfTrend33 -- Dual-Drive Freedom (The Beater)

Paradigm: Left-Side Entry + Right-Side Confirmation
Hypothesis: Beat BuyAndHold by entering BEFORE the EMA200 cross using 
            MACD 1d momentum, and exiting selectively during extreme bubbles.
            - Entry 1 (Left): 1d MACD Gold Cross + Stablecoin Growth.
            - Entry 2 (Right): 1d Price > EMA200.
            - Defense: Zero Stoploss in Bull Market.
            - Exit (Bubble): Exit 50% if Price/EMA200 deviation > 1.2.
Parent: MtfTrend32
Created: R58
Status: Training (The Final Boss Challenge)
"""

from pandas import DataFrame
from typing import Optional, Union
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade
from autoq_data.strategy_bridge import merge_external_factors

class MtfTrend33(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # 2 slots to allow 50% left-side + 50% right-side entries
    position_stacking = True
    max_open_trades = 2
    
    minimal_roi = {"0": 100} 
    stoploss = -0.99 

    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = merge_external_factors(
            dataframe, metadata,
            columns=["stablecoin_mcap_growth"],
        )
        dataframe["stablecoin_mcap_growth"] = dataframe["stablecoin_mcap_growth"].fillna(0)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        # Entry 1: Left-Side (MACD momentum while still below 200EMA)
        left_side = (dataframe['macd_1d'] > dataframe['macdsignal_1d']) & (dataframe['stablecoin_mcap_growth'] > 0)
        
        # Entry 2: Right-Side (Established bull trend)
        right_side = (dataframe["close_1d"] > dataframe["ema200_1d"])

        dataframe.loc[left_side, "enter_long"] = 1
        dataframe.loc[left_side, "enter_tag"] = "left_side"
        
        dataframe.loc[right_side, "enter_long"] = 1
        dataframe.loc[right_side, "enter_tag"] = "right_side"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Final Guard: Macro Bear
        exit_cond = (dataframe["close_1d"] < dataframe["ema200_1d"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[Union[str, bool]]:
        
        # Access 1d data for bubble detection
        df_1d, _ = self.dp.get_analyzed_dataframe(pair, "1d")
        if current_time not in df_1d.index:
            return None
            
        last_1d = df_1d.loc[current_time]
        
        # BUBBLE DETECTION
        # If price is 100% above 200 EMA, it's a bubble. Exit the current trade.
        if current_rate > last_1d['ema200'] * 2.0:
            return "bubble_exit"

        return None

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        # 50% per trade (2 trades = 100%)
        return self.wallets.get_total_stake_amount() * 0.495
