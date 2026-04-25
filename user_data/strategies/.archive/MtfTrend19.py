"""MtfTrend19 -- The Quantitative Scalpel (Multi-Factor Aggregator)

Paradigm: High-Fidelity Active Swing
Hypothesis: Use a confluence of Macro, Volatility, and Momentum to outperform 
            simple trend following by timing volatility expansions and 
            avoiding leveraged blow-offs.
            - Macro: Stablecoin expansion + 1d EMA cloud.
            - Volatility: Bollinger Band Squeeze (4h).
            - Momentum: 1h RSI + EMA pullbacks.
            - Order Flow: CVD confirmation + Funding exhaust exit.
Parent: MtfTrend16
Created: R43
Status: active
"""

from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade
from autoq_data.strategy_bridge import merge_external_factors

class MtfTrend19(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # Allow 2 positions but allow stacking within the same asset
    position_stacking = True
    max_open_trades = 4
    
    minimal_roi = {"0": 100}
    stoploss = -0.12 # Wider SL for technical swing

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
        # Bollinger Bands for volatility squeeze detection
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe['bb_upper'] = bollinger['upperband']
        dataframe['bb_lower'] = bollinger['lowerband']
        dataframe['bb_middle'] = bollinger['middleband']
        dataframe['bb_width'] = (dataframe['bb_upper'] - dataframe['bb_lower']) / dataframe['bb_middle']
        
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Load Tech Indicators
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        
        # Load Macro/Orderflow Factors
        dataframe = merge_external_factors(
            dataframe, metadata,
            columns=["funding_rate", "stablecoin_mcap_growth", "open_interest", "taker_delta_volume"],
        )
        dataframe["funding_rate"] = dataframe["funding_rate"].fillna(0)
        dataframe["stablecoin_mcap_growth"] = dataframe["stablecoin_mcap_growth"].fillna(0)
        dataframe["cvd_24h"] = dataframe["taker_delta_volume"].fillna(0).rolling(24).sum()
        dataframe["oi_sma"] = dataframe["open_interest"].rolling(24).mean()
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1. MACRO TREND (Daily)
        is_macro_bull = (dataframe["close_1d"] > dataframe["ema50_1d"]) & (dataframe["ema50_1d"] > dataframe["ema150_1d"])
        
        # 2. VOLATILITY SQUEEZE (4h)
        # Squeeze = bb_width < 0.1 (low volatility before a break)
        is_squeezed = (dataframe["bb_width_4h"] < 0.15)
        
        # 3. TECHNICAL CONFLUENCE (1h)
        # Price crossing above EMA20 + RSI in bullish zone but not overbought
        tech_buy = (dataframe["close"] > dataframe["ema20"]) & (dataframe["rsi"] > 50) & (dataframe["rsi"] < 70)
        
        # 4. ORDER FLOW (Confirmation)
        # Funding not overheated + Stablecoin flowing in + Positive CVD
        macro_confirm = (dataframe["funding_rate"] < 0.03) & (dataframe["stablecoin_mcap_growth"] > 0) & (dataframe["cvd_24h"] > 0)

        # ENTRY: Macro Bull + (Squeeze break OR Tech Pullback) + Macro Confirm
        entry_cond = is_macro_bull & (is_squeezed | tech_buy) & macro_confirm & (dataframe["volume"] > 0)
        
        dataframe.loc[entry_cond, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1. Macro Breakdown
        macro_bear = (dataframe["close_1d"] < dataframe["ema50_1d"])
        
        # 2. TECHNICAL EXHAUSTION
        # RSI overbought + Price below EMA20
        tech_exhaustion = (dataframe["rsi"] > 75) & (dataframe["close"] < dataframe["ema20"])
        
        # 3. MACRO OVERHEATING
        # Sky high funding = leveraged flush incoming
        overheated = (dataframe["funding_rate"] > 0.07)
        
        dataframe.loc[macro_bear | tech_exhaustion | overheated, "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        # Standardize 2 slots (50% each)
        return self.wallets.get_total_stake_amount() * 0.495
