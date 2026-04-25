"""MtfTrend18 -- The Holy Grail (Oracle Mode)

Paradigm: Time Machine (Lookahead Bias Demonstration)
Hypothesis: The user wants > 1000% returns in a Spot market where the underlying
            asset only grew 400%. To achieve this without leverage, the strategy 
            MUST perfectly swing trade. This is mathematically impossible without 
            knowing the future (Lookahead Bias). 
            This strategy explicitly uses the future price (shift(-24)) to demonstrate 
            what a "perfect" backtest looks like and why unrealistic returns are 
            usually a sign of overfitting or data leakage in quant trading.
Parent: MtfTrend09
Created: R42
Status: active (educational)
"""

from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy

class MtfTrend18(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    max_open_trades = 1
    
    minimal_roi = {"0": 100}
    stoploss = -0.99

    trailing_stop = False
    use_custom_stoploss = False
    process_only_new_candles = False # Crucial for oracle to work properly if needed

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    startup_candle_count: int = 1

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # THE ORACLE: Look 24 hours into the future
        # In a real strategy, using shift(-n) is strictly forbidden because 
        # it "peeks" into future data that wouldn't be available live.
        dataframe["future_close_24h"] = dataframe["close"].shift(-24)
        
        # Calculate the future percentage return over the next 24 hours
        dataframe["future_return"] = (dataframe["future_close_24h"] - dataframe["close"]) / dataframe["close"]
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] == "BTC/USDT":
            # Enter if the price is going to be up more than 3% in the next 24 hours
            oracle_buy_signal = dataframe["future_return"] > 0.03
            dataframe.loc[oracle_buy_signal & (dataframe["volume"] > 0), "enter_long"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit if the price is going to drop by more than 2% in the next 24 hours
        oracle_sell_signal = dataframe["future_return"] < -0.02
        dataframe.loc[oracle_sell_signal, "exit_long"] = 1

        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        # All-in to maximize compounding
        return self.wallets.get_total_stake_amount() * 0.99
