"""MtfTrend10 -- Alpha Rotation Strategy (BTC/ETH)

Paradigm: Relative Strength Rotation
Hypothesis: BTC and ETH take turns leading the bull market. 
            By rotating capital to the asset with higher 30-day momentum, 
            we can compound gains from both cycles.
            Macro Filter: Only trade if asset is above SMA200 (1d).
            Rotation: Switch if the other asset's 30d momentum is > 5% higher.
Parent: MtfTrend09
Created: R34
Status: active
"""

from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative

class MtfTrend10(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # 100% allocation to the leading asset
    max_open_trades = 1
    
    minimal_roi = {"0": 100}
    stoploss = -0.99

    trailing_stop = False
    use_custom_stoploss = False
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    startup_candle_count: int = 200

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Macro Trend
        dataframe["sma200"] = ta.SMA(dataframe, timeperiod=200)
        # Momentum (30-day return)
        dataframe["pct_change_30"] = dataframe["close"].pct_change(30)
        return dataframe

    @informative("1d", "BTC/USDT")
    def populate_indicators_btc_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["sma200"] = ta.SMA(dataframe, timeperiod=200)
        dataframe["pct_change_30"] = dataframe["close"].pct_change(30)
        return dataframe

    @informative("1d", "ETH/USDT")
    def populate_indicators_eth_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["sma200"] = ta.SMA(dataframe, timeperiod=200)
        dataframe["pct_change_30"] = dataframe["close"].pct_change(30)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        
        # Bull market filter
        is_bull = dataframe["close_1d"] > dataframe["sma200_1d"]
        
        # Relative strength
        btc_mom = dataframe["btc_usdt_pct_change_30_1d"]
        eth_mom = dataframe["eth_usdt_pct_change_30_1d"]
        
        if pair == "BTC/USDT":
            # Enter BTC if bull AND BTC >= ETH - 5% (buffer to prevent too many flips)
            is_stronger = btc_mom >= (eth_mom - 0.05)
            dataframe.loc[is_bull & is_stronger & (dataframe["volume"] > 0), "enter_long"] = 1
            
        elif pair == "ETH/USDT":
            # Enter ETH if bull AND ETH > BTC + 5%
            is_stronger = eth_mom > (btc_mom + 0.05)
            dataframe.loc[is_bull & is_stronger & (dataframe["volume"] > 0), "enter_long"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        
        # Exit if macro bear
        is_bear = dataframe["close_1d"] < dataframe["sma200_1d"]
        
        # Exit for rotation
        btc_mom = dataframe["btc_usdt_pct_change_30_1d"]
        eth_mom = dataframe["eth_usdt_pct_change_30_1d"]
        
        rotation_exit = False
        if pair == "BTC/USDT":
            # Exit BTC if ETH is significantly stronger
            rotation_exit = eth_mom > (btc_mom + 0.07) # Higher threshold to exit to avoid noise
        elif pair == "ETH/USDT":
            # Exit ETH if BTC is significantly stronger
            rotation_exit = btc_mom > (eth_mom + 0.07)

        dataframe.loc[is_bear | rotation_exit, "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
