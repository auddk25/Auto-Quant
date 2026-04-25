"""MtfTrend34 -- BTC Momentum Aggregator (The 1000% Sprint)

Paradigm: Core/Satellite Compounding
Hypothesis: Achieve >1000% by staying fully invested in the BTC bull market 
            and adding 50% technical leverage during the steepest parts of the trend.
            - Base: 100% BTC on SMA200 Bull.
            - Satellite: Add 50% extra if 4h RSI recovers + ADX is strong.
            - Exit: 
                - Satellite exits on RSI Exhaustion (>88).
                - Core exits only on 1d EMA50 break.
Parent: MtfTrend33
Created: R59
Status: Training (BTC Focus)
"""

from pandas import DataFrame
from typing import Optional, Union
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade
from autoq_data.strategy_bridge import merge_external_factors

class MtfTrend34(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # Force 2 slots at strategy level to allow 150% virtual position
    max_open_trades = 2
    position_stacking = True
    
    minimal_roi = {"0": 100} 
    stoploss = -0.99 

    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    @informative("4h")
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        return dataframe

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["sma200"] = ta.SMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe = merge_external_factors(
            dataframe, metadata,
            columns=["funding_rate", "stablecoin_mcap_growth"],
        )
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        # REGIME 1: CORE (Macro Bull)
        is_bull = (dataframe["close_1d"] > dataframe["sma200_1d"])
        
        # REGIME 2: SATELLITE (Acceleration)
        # 4h RSI recovers from 40s to > 55 + ADX > 35 + Liquid Market
        is_accelerating = (dataframe["rsi_4h"] > 55) & (dataframe["adx_4h"] > 35) & (dataframe["stablecoin_mcap_growth"] > 0)

        # Core Entry
        dataframe.loc[is_bull & (dataframe["volume"] > 0), "enter_long"] = 1
        dataframe.loc[is_bull & (dataframe["volume"] > 0), "enter_tag"] = "core"
        
        # Satellite Entry (can happen multiple times if stacking allows)
        dataframe.loc[is_bull & is_accelerating, "enter_long"] = 1
        dataframe.loc[is_bull & is_accelerating, "enter_tag"] = "satellite"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Core Exit: Macro breakdown
        exit_cond = (dataframe["close_1d"] < dataframe["ema50_1d"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[Union[str, bool]]:
        
        # SATELLITE EXIT: Short-term exhaustion
        if trade.enter_tag == "satellite":
            dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
            last_candle = dataframe[dataframe['date'] <= current_time].iloc[-1]
            
            if last_candle['rsi'] > 85:
                return "satellite_exhaustion"
                
            # Or if it fails to perform after 7 days
            if (current_time - trade.open_date_utc).days > 7 and current_profit < 0.05:
                return "satellite_slow_exit"

        return None

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        # Core uses 99% of total wallet. 
        # Satellite uses another 50% (simulating virtual leverage)
        total_balance = self.wallets.get_total_stake_amount()
        if entry_tag == "core":
            return total_balance * 0.99
        return total_balance * 0.50
