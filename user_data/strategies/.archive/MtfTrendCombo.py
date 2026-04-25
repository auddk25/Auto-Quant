"""MtfTrendCombo -- Cycle + Trend Composite Strategy

Paradigm: Combine AHR999 cycle timing with EMA trend following.
Hypothesis: Neither pure cycle timing nor pure trend following is optimal.
            - Use AHR999 < 0.80 (undervaluation) as aggressive entry signal
            - Use EMA50 > EMA200 (golden cross) as confirmatory bull signal
            - Exit only when BOTH conditions reverse:
              AHR999 > 1.50 AND EMA50 < EMA200 (death cross)
            - This means: enter early on undervaluation, hold through trend,
              only exit when overvalued AND trend broken.
Parent: MtfTrendCycle01 + MtfTrendGoldenCross
Created: R89
Status: active
"""
from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy, informative
from autoq_data.cycle_bridge import merge_ahr999, merge_cbbi


class MtfTrendCombo(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = False
    max_open_trades = 1
    minimal_roi = {"0": 100}
    stoploss = -0.25
    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    @informative("1d")
    def populate_indicators_1d(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = merge_ahr999(dataframe, metadata)
        dataframe = merge_cbbi(dataframe, metadata)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        # Entry: undervalued (AHR999 < 0.80 AND CBBI < 0.5) OR golden cross
        undervalued = (
            (dataframe["ahr999"] < 0.80)
            & (dataframe["cbbi"] < 0.5)
        )
        golden_cross = dataframe["ema50_1d"] > dataframe["ema200_1d"]
        buy_cond = (undervalued | golden_cross) & (dataframe["volume"] > 0)
        dataframe.loc[buy_cond, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit: overvalued AND trend broken (both must confirm)
        overvalued = dataframe["ahr999"] > 1.50
        death_cross = dataframe["ema50_1d"] < dataframe["ema200_1d"]
        dataframe.loc[overvalued & death_cross, "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
