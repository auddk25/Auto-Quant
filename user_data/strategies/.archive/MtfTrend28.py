"""MtfTrend28 -- The Dynamic Scalpel (Training Phase)

Paradigm: Tech-Heavy Active Swing + Dynamic Exits
Hypothesis: Achieve >1000% by maximizing compound interest during the bull run.
            - Training Set: 2023-2025.
            - Entry: MACD + RSI + EMA Confluence + CVD.
            - Dynamic Exit: 
                1. RSI Overbought (>80).
                2. Bollinger Band piercing (Price > Upper BB * 1.1).
                3. EMA20 distance (Price/EMA20 > 1.2).
            - Stoploss: ATR-based dynamic trailing.
Parent: MtfTrend27
Created: R52
Status: Training (2023-2025)
"""

from pandas import DataFrame
from typing import Optional, Union
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade
from autoq_data.strategy_bridge import merge_external_factors

class MtfTrend28(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # High efficiency position management
    position_stacking = True
    max_open_trades = 2
    
    minimal_roi = {"0": 100} # Exits are purely signal-driven
    stoploss = -0.10

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

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Tech Indicators
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        
        # MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        
        # Macro/Orderflow
        dataframe = merge_external_factors(
            dataframe, metadata,
            columns=["funding_rate", "stablecoin_mcap_growth", "taker_delta_volume"],
        )
        dataframe["cvd_24h"] = dataframe["taker_delta_volume"].fillna(0).rolling(24).sum()
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Complex Tech Entry
        # 1. MACD Cross above signal
        # 2. Price > EMA50
        # 3. RSI > 50 (Positive Momentum)
        # 4. CVD Confirmation
        
        entry_cond = (
            (dataframe['macd'] > dataframe['macdsignal']) &
            (dataframe['close'] > dataframe['ema50']) &
            (dataframe['rsi'] > 50) &
            (dataframe['cvd_24h'] > 0) &
            (dataframe['stablecoin_mcap_growth'] >= 0) &
            (dataframe["volume"] > 0)
        )
        
        dataframe.loc[entry_cond, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Signals are handled in custom_exit
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[Union[str, bool]]:
        
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe[dataframe['date'] <= current_time].iloc[-1]
        
        # 1. DYNAMIC RSI OVERBOUGHT
        if last_candle['rsi'] > 82:
            return "dynamic_rsi_overbought"
        
        # 2. BOLLINGER PIERCING (Mean Reversion Risk)
        # Check 4h Bollinger for macro exhaustion
        df_4h, _ = self.dp.get_analyzed_dataframe(pair, "4h")
        last_4h = df_4h[df_4h['date'] <= current_time].iloc[-1]
        if current_rate > last_4h['bb_upper'] * 1.05:
            return "bb_upper_stretch"
            
        # 3. VERTICAL DEVIATION
        # Price is more than 20% away from EMA20 (Blow-off Top)
        if current_rate > last_candle['ema20'] * 1.20:
            return "ema_blowoff"
            
        # 4. TREND WEAKNESS
        if last_candle['close'] < last_candle['ema20'] and current_profit > 0.05:
            return "trend_weakness"

        return None

    def custom_stoploss(self, pair: str, trade, current_time, current_rate,
                        current_profit, **kwargs) -> float:
        # Dynamic Trailing based on ATR
        # Tighten stoploss as we gain profit
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe[dataframe['date'] <= current_time].iloc[-1]
        
        atr = last_candle['atr']
        # If profit > 10%, move stoploss to 2*ATR below current price
        if current_profit > 0.10:
            atr_dist_pct = (2 * atr) / current_rate
            return -max(atr_dist_pct, 0.03) # Never tighter than 3%
            
        return self.stoploss

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        # Use 100% of available wallet for each trade to maximize compound interest
        return self.wallets.get_total_stake_amount() * 0.495
