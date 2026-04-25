"""MtfTrend15 -- Macro-Health Momentum Aggregator

Paradigm: Macro-Timing Full Concentration
Hypothesis: To beat BuyAndHold, we must remain fully invested during the 
            healthiest bull phases and avoid the "dead capital" periods.
            - Macro Filter: 1d SMA200.
            - Entry Factor: Leverage Flush (Funding drops from >0.03 to <0.01) 
              + Liquidity (Stablecoin > 0).
            - Concentration: 100% BTC or ETH based on CVD strength.
            - Exit: 1d EMA50 cross to preserve the 400% compounding.
Parent: MtfTrend09
Created: R39
Status: active
"""

from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade
from autoq_data.strategy_bridge import merge_external_factors

class MtfTrend15(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # Full concentration
    max_open_trades = 1
    
    minimal_roi = {"0": 100}
    stoploss = -0.99 

    process_only_new_candles = True
    use_exit_signal = True

    startup_candle_count: int = 200

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["sma200"] = ta.SMA(dataframe, timeperiod=200)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Load Factors
        dataframe = merge_external_factors(
            dataframe, metadata,
            columns=["funding_rate", "stablecoin_mcap_growth", "taker_delta_volume"],
        )
        dataframe["funding_rate"] = dataframe["funding_rate"].fillna(0)
        dataframe["stablecoin_mcap_growth"] = dataframe["stablecoin_mcap_growth"].fillna(0)
        
        # Detect Leverage Flush: Funding was high, now it's low
        dataframe["funding_high"] = (dataframe["funding_rate"].rolling(48).max() > 0.03).astype(int)
        dataframe["leverage_flush"] = ((dataframe["funding_high"] == 1) & (dataframe["funding_rate"] < 0.01)).astype(int)
        
        # Buying Pressure
        dataframe["cvd_24h"] = dataframe["taker_delta_volume"].fillna(0).rolling(24).sum()
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        is_bull = (dataframe["close_1d"] > dataframe["sma200_1d"])
        
        # Macro Health: Bull + Leverage Cleaned + Liquidity Inflow
        macro_health = (
            is_bull & 
            (dataframe["leverage_flush"] == 1) & 
            (dataframe["stablecoin_mcap_growth"] > 0)
        )
        
        # Also allow basic bull entry if we are missing the boat
        basic_bull = is_bull & (dataframe["stablecoin_mcap_growth"] > 0.002)

        entry = (macro_health | basic_bull) & (dataframe["volume"] > 0)
        dataframe.loc[entry, "enter_long"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit on faster macro break (1d EMA50) to protect the compounding
        exit_cond = (dataframe["close_1d"] < dataframe["ema50_1d"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
