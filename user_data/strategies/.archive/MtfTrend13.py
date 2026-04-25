"""MtfTrend13 -- Macro-Driven Alpha Aggregator

Paradigm: Dynamic Macro-Timing Swing
Hypothesis: Macro factors (Stablecoin growth, Funding, CVD) can predict 
            short-term "blow-off tops" and "leveraged flushes".
            Strategy maintains a 50% core position during SMA200 bull trends
            and uses the other 50% for "Macro Swings" triggered by:
            - Entry: Negative/Low Funding + Positive Stablecoin Flow + Rising CVD.
            - Exit: Extreme Funding (>0.05%) OR Stablecoin Outflow.
Parent: MtfTrend09
Created: R37
Status: active
"""

from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade
from autoq_data.strategy_bridge import merge_external_factors

class MtfTrend13(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # Dynamic Stacking: Max 5 trades (1 core + 4 satellite swings)
    position_stacking = True
    max_open_trades = 5
    
    minimal_roi = {"0": 100}
    stoploss = -0.99  # No traditional stoploss, macro-driven exits only

    process_only_new_candles = True
    use_exit_signal = True

    startup_candle_count: int = 200

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["sma200"] = ta.SMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Load all macro factors
        dataframe = merge_external_factors(
            dataframe, metadata,
            columns=["funding_rate", "stablecoin_mcap_growth", "btc_dvol", "open_interest", "taker_delta_volume"],
        )
        dataframe["funding_rate"] = dataframe["funding_rate"].fillna(0)
        dataframe["stablecoin_mcap_growth"] = dataframe["stablecoin_mcap_growth"].fillna(0)
        dataframe["btc_dvol"] = dataframe["btc_dvol"].fillna(60)
        dataframe["cvd_24h"] = dataframe["taker_delta_volume"].fillna(0).rolling(24).sum()
        
        # Funding rate smoothed
        dataframe["funding_sma"] = dataframe["funding_rate"].rolling(24).mean()
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        is_bull = dataframe["close_1d"] > dataframe["sma200_1d"]
        
        # 1. CORE Position: Long term bull
        core_signal = is_bull & (dataframe["volume"] > 0)
        
        # 2. SWING Position: Macro Alpha
        # Low funding (not overheated) + Stablecoin inflow + Buying pressure (CVD)
        macro_swing = (
            (dataframe["funding_sma"] < 0.02) & 
            (dataframe["stablecoin_mcap_growth"] > 0) & 
            (dataframe["cvd_24h"] > 0)
        )
        
        # We use enter_tag to distinguish positions
        dataframe.loc[core_signal, "enter_long"] = 1
        dataframe.loc[core_signal, "enter_tag"] = "core"
        
        # Higher priority for swing when conditions are perfect
        dataframe.loc[is_bull & macro_swing, "enter_long"] = 1
        dataframe.loc[is_bull & macro_swing, "enter_tag"] = "macro_swing"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Global macro exit
        is_bear = dataframe["close_1d"] < dataframe["sma200_1d"]
        
        # Local overheating exit
        # High funding (>0.06%) indicates imminent leveraged flush
        overheated = dataframe["funding_sma"] > 0.06
        
        # Liquidity drain
        liquidity_drain = dataframe["stablecoin_mcap_growth"] < -0.01
        
        dataframe.loc[is_bear, "exit_long"] = 1
        dataframe.loc[is_bear, "exit_tag"] = "bear_market"
        
        # Only swing positions exit on overheating (keep core)
        # Note: Freqtrade's populate_exit_trend affects all trades.
        # We will use custom_exit for finer control.
        
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe[dataframe['date'] <= current_time].iloc[-1]
        
        # CORE stays until bear market
        if trade.enter_tag == "core":
            if last_candle['close_1d'] < last_candle['sma200_1d']:
                return "bear_market_core"
            return None
            
        # MACO_SWING exits on overheating OR macro bear
        if last_candle['close_1d'] < last_candle['sma200_1d']:
            return "bear_market_swing"
            
        if last_candle['funding_sma'] > 0.05:
            return "overheated_swing"
            
        if last_candle['stablecoin_mcap_growth'] < -0.005:
            return "liquidity_drain_swing"
            
        return None

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        total_balance = self.wallets.get_total_stake_amount()
        
        # Core gets 50%
        if entry_tag == "core":
            return total_balance * 0.50
            
        # Macro swings get 12.5% each (up to 4 positions = 50%)
        return total_balance * 0.125
