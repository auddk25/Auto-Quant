"""MtfTrend38 -- The Compounding Demon (BTC 1000% End Game)

Paradigm: High-Velocity Reinvestment (Virtual Leverage)
Hypothesis: Since we can't run real futures, we simulate leverage by using 
            aggressive position stacking and full profit reinvestment.
            - Trading Mode: Spot (Simulated Leverage).
            - Entry: Macro Bull (SMA200) + 1h Momentum.
            - Stacking: Open up to 5 slots simultaneously for BTC.
            - Compound: custom_stake_amount forces 100% of wallet per cluster.
            - Exit: 1d EMA50 break.
Parent: MtfTrend30
Created: R63
Status: active (The Final Beater)
"""

from pandas import DataFrame
from typing import Optional, Union
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade

class MtfTrend38(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # Simulate leverage by allowing 5 slots for BTC
    position_stacking = True
    max_open_trades = 5
    
    minimal_roi = {"0": 100} 
    stoploss = -0.15 # Allow some breathing room

    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["sma200"] = ta.SMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        is_bull = (dataframe["close_1d"] > dataframe["sma200_1d"])
        momentum = (dataframe["rsi"] > 50)

        # Trigger stacking
        dataframe.loc[is_bull & momentum & (dataframe["volume"] > 0), "enter_long"] = 1
        return dataframe

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                            time_in_force: str, current_time: datetime, entry_tag: Optional[str],
                            side: str, **kwargs) -> bool:
        """
        Force 5 trades to open quickly as a cluster
        """
        trades = Trade.get_trades_proxy(pair=pair, is_open=True)
        if len(trades) >= self.max_open_trades:
            return False
            
        return True

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit whole cluster on macro break
        exit_cond = (dataframe["close_1d"] < dataframe["ema50_1d"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        # Each slot gets 20% of account. With 5 slots, we use 100% of account.
        # As profit grows, the 20% value grows automatically.
        return self.wallets.get_total_stake_amount() * 0.20
