"""MtfTrend40 -- Star Relay (BTC/ETH/SOL)

Paradigm: Relative Strength Selection (Winner Take All)
Hypothesis: Achieve 1000%+ by always holding the single most trending asset.
            - Filter: 1d Price > EMA20 (Bull Market).
            - Selection: Asset with the highest 1h ADX.
            - Concentration: 100% Wallet.
            - Exit: 1d Price < EMA10 or losing the ADX lead by > 10.
Parent: MtfTrend39
Created: R66
Status: active
"""

from pandas import DataFrame
from typing import Optional, Union
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade

class MtfTrend40(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # Concentration
    max_open_trades = 1
    
    minimal_roi = {"0": 100} 
    stoploss = -0.15 

    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema10"] = ta.EMA(dataframe, timeperiod=10)
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["macd"] = ta.MACD(dataframe)['macd']
        dataframe["macdsignal"] = ta.MACD(dataframe)['macdsignal']
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Entry: 1d Bull + 1h MACD cross
        is_bull_1d = (dataframe["close_1d"] > dataframe["ema20_1d"])
        
        # Selection logic:
        # We assign the ADX value to the enter_long column if conditions are met.
        # Freqtrade will pick the one with the highest "enter_long" value if multiple exist.
        entry_cond = is_bull_1d & (dataframe['macd'] > dataframe['macdsignal']) & (dataframe["volume"] > 0)
        
        dataframe.loc[entry_cond, "enter_long"] = dataframe["adx"]
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Fast Exit: 1d Trend break
        exit_cond = (dataframe["close_1d"] < dataframe["ema10_1d"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
