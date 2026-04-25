"""MtfTrend37 -- The Futures Warlord (3x Leverage + Long/Short)

Paradigm: Leveraged Trend Following + Dynamic Profit Taking
Hypothesis: Achieve 1000%+ by leveraging the macro bull and shorting the bear.
            - Trading Mode: Futures (Margin 3.0x).
            - Long: 1d Price > EMA200 + 1h MACD Gold Cross.
            - Short: 1d Price < EMA200 + 1h MACD Death Cross.
            - Exit (Long): RSI Exhaustion (>85) or 1d EMA50 break.
            - Exit (Short): RSI Oversold (<15) or 1d EMA50 recovery.
Parent: MtfTrend30
Created: R62
Status: Training (The 1000% Futures Mission)
"""

from pandas import DataFrame
from typing import Optional, Union
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade

class MtfTrend37(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False  # Spot market only, short signals will be ignored

    # Concentration for maximal leveraged compounding
    max_open_trades = 1
    
    minimal_roi = {"0": 100} 
    stoploss = -0.15 # 15% drop on 3x leverage = 45% account hit. High risk.

    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str], side: str,
                 **kwargs) -> float:
        # Fixed 3x leverage
        return 3.0

    @informative("4h")
    def populate_indicators_4h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        # MACRO Filter
        is_bull = (dataframe["close_1d"] > dataframe["ema200_1d"])
        is_bear = (dataframe["close_1d"] < dataframe["ema200_1d"])

        # LONG ENTRY: Bull market + Momentum Cross
        long_cond = is_bull & (dataframe['macd'] > dataframe['macdsignal']) & (dataframe['rsi'] > 50)
        
        # SHORT ENTRY: Bear market + Momentum Cross
        short_cond = is_bear & (dataframe['macd'] < dataframe['macdsignal']) & (dataframe['rsi'] < 50)

        dataframe.loc[long_cond, "enter_long"] = 1
        dataframe.loc[long_cond, "enter_tag"] = "long_trend"
        
        dataframe.loc[short_cond, "enter_short"] = 1
        dataframe.loc[short_cond, "enter_tag"] = "short_trend"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Global Exit: Macro regime reversal
        exit_long = (dataframe["close_1d"] < dataframe["ema50_1d"])
        exit_short = (dataframe["close_1d"] > dataframe["ema50_1d"])
        
        dataframe.loc[exit_long, "exit_long"] = 1
        dataframe.loc[exit_short, "exit_short"] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime,
                    current_rate: float, current_profit: float, **kwargs) -> Optional[Union[str, bool]]:
        
        df_4h, _ = self.dp.get_analyzed_dataframe(pair, "4h")
        if current_time not in df_4h.index:
            return None
        last_4h = df_4h.loc[current_time]
        
        # DYNAMIC TAKE PROFIT
        if trade.is_short:
            # Short TP: Oversold recovery
            if last_4h['rsi'] < 15:
                return "short_oversold_tp"
        else:
            # Long TP: Overbought exhaustion
            if last_4h['rsi'] > 85:
                return "long_overbought_tp"

        return None

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
