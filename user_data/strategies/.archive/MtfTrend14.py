"""MtfTrend14 -- Macro-Enhanced Compounder (The Snowball)

Paradigm: Aggressive Macro Pyramiding
Hypothesis: Don't exit on overheating. Instead, use Macro signals to "Leverage Up"
            when risk-reward is highest.
            - Base: Always 100% BTC in SMA200 Bull market.
            - Macro Pyramiding: Add extra 50% size if:
                1. Funding is low (flush completed).
                2. Stablecoin growth is high (new liquidity).
                3. CVD is positive (buying intent).
            This maximizes the capture of the "vertical" phases of the bull run.
Parent: MtfTrend09
Created: R38
Status: active
"""

from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade
from autoq_data.strategy_bridge import merge_external_factors

class MtfTrend14(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # Position Adjustment for "Virtual Leverage"
    position_adjustment_enable = True
    max_entry_position_adjustment = 3 # Can add size 3 times
    
    max_open_trades = 1
    
    minimal_roi = {"0": 100}
    stoploss = -0.99  # Macro exit only

    process_only_new_candles = True
    use_exit_signal = True

    startup_candle_count: int = 1

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["sma200"] = ta.SMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Load factors
        dataframe = merge_external_factors(
            dataframe, metadata,
            columns=["funding_rate", "stablecoin_mcap_growth", "taker_delta_volume"],
        )
        dataframe["funding_rate"] = dataframe["funding_rate"].fillna(0)
        dataframe["stablecoin_mcap_growth"] = dataframe["stablecoin_mcap_growth"].fillna(0)
        dataframe["cvd_24h"] = dataframe["taker_delta_volume"].fillna(0).rolling(24).sum()
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] == "BTC/USDT":
            # 100% Entry on Macro Bull
            is_bull = dataframe["close_1d"] > dataframe["sma200_1d"]
            dataframe.loc[is_bull & (dataframe["volume"] > 0), "enter_long"] = 1
        return dataframe

    def adjust_trade_position(self, trade: Trade, current_time: datetime,
                              current_rate: float, current_profit: float,
                              min_stake: Optional[float], max_stake: float,
                              current_entry_rate: float, current_exit_rate: float,
                              current_entry_profit: float, current_exit_profit: float,
                              **kwargs) -> Optional[float]:
        
        # Only BTC
        if trade.pair != "BTC/USDT":
            return None

        # Check macro trend
        dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
        last_candle = dataframe[dataframe['date'] <= current_time].iloc[-1]
        
        if last_candle['close_1d'] < last_candle['sma200_1d']:
            return None

        # Macro Pyramiding Logic:
        # If we see a "flush" (Low Funding) + "Liquidity injection" (Stablecoin grow)
        # Add 25% of initial stake
        can_pyramid = (
            (last_candle["funding_rate"] < 0.01) & 
            (last_candle["stablecoin_mcap_growth"] > 0.001) &
            (last_candle["cvd_24h"] > 0)
        )

        if can_pyramid and trade.nr_of_successful_entries <= self.max_entry_position_adjustment:
            # We add 25% of initial stake per hit
            return trade.stake_amount * 0.25
            
        return None

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Only exit on macro bear market
        exit_cond = (dataframe["close_1d"] < dataframe["sma200_1d"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        # Start with 99% of wallet balance
        return self.wallets.get_total_stake_amount() * 0.99
