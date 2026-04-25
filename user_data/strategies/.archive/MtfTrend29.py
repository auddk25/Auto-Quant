"""MtfTrend29 -- The Morphological Titan (Training Phase)

Paradigm: Morphological Entry + Asymmetric Exit
Hypothesis: Use price action (Bollinger Stretch) and technical momentum (MACD/RSI)
            to capture 1000%+ compounded gains.
            - Defense: Use 1d EMA Cloud as the "Iron Shield".
            - Attack: 1h MACD Cross + RSI 50 recovery.
            - Profit: 
                - Take 50% profit on extreme 4h BB stretch.
                - Hold 50% for the macro moonshot.
Parent: MtfTrend28
Created: R53
Status: Training (2023-2025)
"""

from pandas import DataFrame
from typing import Optional, Union
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade
from autoq_data.strategy_bridge import merge_external_factors

class MtfTrend29(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    position_stacking = True
    max_open_trades = 2
    
    minimal_roi = {"0": 100} 
    stoploss = -0.15 # Broaden SL to avoid being washed out

    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    @informative("4h")
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_upper'] = bollinger['upperband']
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        return dataframe

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema150"] = ta.EMA(dataframe, timeperiod=150)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Tech
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        
        # MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Macro Bull
        is_bull_1d = (dataframe["close_1d"] > dataframe["ema50_1d"]) & (dataframe["ema50_1d"] > dataframe["ema150_1d"])
        
        # Morphological Entry
        entry_cond = (
            is_bull_1d &
            (dataframe['macd'] > dataframe['macdsignal']) &
            (dataframe['rsi'] > 50) &
            (dataframe["volume"] > 0)
        )
        
        dataframe.loc[entry_cond, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Macro Exit Only
        exit_cond = (dataframe["close_1d"] < dataframe["ema50_1d"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[Union[str, bool]]:
        
        # 1. Morphological Profit Taking (BB Stretch)
        # We check the 4h indicators provided by informative
        df_4h, _ = self.dp.get_analyzed_dataframe(pair, "4h")
        
        # Fix: correctly access the row by date without assuming 'date' is a column
        # Freqtrade DataFrames in backtesting have datetime index
        if current_time in df_4h.index:
            last_4h = df_4h.loc[current_time]
            
            # If price is 10% above 4h BB Upper -> Strategic Take Profit
            if current_rate > last_4h['bb_upper'] * 1.10:
                # We can't do partial exits easily here, so we exit if RSI is also high
                if last_4h['rsi'] > 75:
                    return "morphological_top"
        
        # 2. Extreme RSI protection
        df_1h, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if current_time in df_1h.index:
            last_1h = df_1h.loc[current_time]
            if last_1h['rsi'] > 88:
                return "rsi_exhaustion"

        return None

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        # Concentrate 99% of total wallet into the first position
        return self.wallets.get_total_stake_amount() * 0.99
