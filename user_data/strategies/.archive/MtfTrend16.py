"""MtfTrend16 -- Macro Relay Strategy (The Ultimate Beater)

Paradigm: 100% Full Concentration Relay
Hypothesis: To crush MtfTrend09 (+425%), we must leverage the period where 
            ETH outperforms BTC (Altseason relay).
            - Base: 100% Concentration.
            - Default: Hold BTC.
            - Relay: Switch to ETH ONLY if:
                1. Stablecoin growth is explosive (>0.01).
                2. ETH relative strength (30d) crosses BTC.
            - Protection: Only exit if 1d SMA200 breaks.
Parent: MtfTrend09
Created: R40
Status: active
"""

from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade
from autoq_data.strategy_bridge import merge_external_factors

class MtfTrend16(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1h"
    can_short = False

    # 100% capital concentration
    max_open_trades = 1
    
    minimal_roi = {"0": 100}
    stoploss = -0.99 

    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 1

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["sma200"] = ta.SMA(dataframe, timeperiod=200)
        dataframe["pct_change_20"] = dataframe["close"].pct_change(20)
        return dataframe

    @informative("1d", "BTC/USDT")
    def populate_indicators_btc_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["sma200"] = ta.SMA(dataframe, timeperiod=200)
        dataframe["pct_change_20"] = dataframe["close"].pct_change(20)
        return dataframe

    @informative("1d", "ETH/USDT")
    def populate_indicators_eth_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["sma200"] = ta.SMA(dataframe, timeperiod=200)
        dataframe["pct_change_20"] = dataframe["close"].pct_change(20)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = merge_external_factors(
            dataframe, metadata,
            columns=["stablecoin_mcap_growth"],
        )
        dataframe["stablecoin_mcap_growth"] = dataframe["stablecoin_mcap_growth"].fillna(0)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        is_bull = (dataframe["close_1d"] > dataframe["sma200_1d"])
        
        btc_mom = dataframe["btc_usdt_pct_change_20_1d"]
        eth_mom = dataframe["eth_usdt_pct_change_20_1d"]
        high_liquidity = dataframe["stablecoin_mcap_growth"] > 0.005

        if pair == "BTC/USDT":
            # Hold BTC unless ETH is much stronger
            eth_dominance = (eth_mom > btc_mom + 0.10) & high_liquidity
            entry = is_bull & (~eth_dominance) & (dataframe["volume"] > 0)
            dataframe.loc[entry, "enter_long"] = 1
                
        elif pair == "ETH/USDT":
            # Switch to ETH if it's showing strength
            is_stronger = (eth_mom > btc_mom + 0.05) & high_liquidity
            entry = is_bull & is_stronger & (dataframe["volume"] > 0)
            dataframe.loc[entry, "enter_long"] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata["pair"]
        is_bear = (dataframe["close_1d"] < dataframe["sma200_1d"])
        
        btc_mom = dataframe["btc_usdt_pct_change_20_1d"]
        eth_mom = dataframe["eth_usdt_pct_change_20_1d"]
        
        if pair == "BTC/USDT":
            rotation_exit = (eth_mom > btc_mom + 0.15)
            dataframe.loc[is_bear | rotation_exit, "exit_long"] = 1
        elif pair == "ETH/USDT":
            rotation_exit = (btc_mom > eth_mom)
            dataframe.loc[is_bear | rotation_exit, "exit_long"] = 1

        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
