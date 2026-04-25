"""MtfTrend17 -- The Moonshot (Leveraged Momentum)

Paradigm: Leveraged All-In Momentum
Hypothesis: If a trend is established (e.g. above 200 SMA), 
            the best way to beat BuyAndHold is to apply leverage to the leader.
            We apply 3x leverage to BTC during its primary bull phases.
Parent: MtfTrend09
Created: R41
Status: active
Uses MTF: yes (1d trend)
"""

from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative

class MtfTrend17(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # 100% allocation
    max_open_trades = 1
    
    minimal_roi = {"0": 100}
    stoploss = -0.99

    trailing_stop = False
    use_custom_stoploss = False
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    startup_candle_count: int = 1

    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str], side: str,
                 **kwargs) -> float:
        """
        Set leverage to 3.0
        """
        return 3.0

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["sma200"] = ta.SMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] == "BTC/USDT":
            trend_cond = (dataframe["close_1d"] > dataframe["sma200_1d"])
            dataframe.loc[trend_cond & (dataframe["volume"] > 0), "enter_long"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        exit_cond = (dataframe["close_1d"] < dataframe["sma200_1d"])
        dataframe.loc[exit_cond, "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
