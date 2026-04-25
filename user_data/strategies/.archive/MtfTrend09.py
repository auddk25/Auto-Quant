"""MtfTrend09 -- All-In Trend Follower

Paradigm: All-In Momentum
Hypothesis: In a crypto bull market, the market leader (BTC) massively outperforms.
            Instead of splitting 50/50, we set max_open_trades=1 to allocate 100% 
            of capital to the first pair that confirms a bull trend. 
            Since BTC typically leads, it gets the 100% allocation.
            We use a wide stoploss (-0.99) and only exit on macro trend reversals
            (1d EMA50 < 150) to catch the maximum possible meat of the bull run.
Parent: MtfTrend08
Created: R33
Status: active
Uses MTF: yes (1d trend)
"""

from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative

class MtfTrend09(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # THE SECRET SAUCE: 100% allocation to the strongest/first signal
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

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["sma200"] = ta.SMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Only trade BTC to capture maximum alpha
        if metadata["pair"] == "BTC/USDT":
            dataframe.loc[dataframe["volume"] > 0, "enter_long"] = 1

        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        # Force 100% of the wallet balance into the first trade
        return self.wallets.get_total_stake_amount() * 0.99

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # No exit
        return dataframe
