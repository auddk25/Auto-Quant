"""
DailyTrendEMA -- Daily EMA crossover with DXY filter
"""

from typing import Optional

from pandas import DataFrame
import pandas as pd
import numpy as np
import talib.abstract as ta

from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade
from datetime import datetime
from pathlib import Path


class DailyTrendEMA(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "1d"
    can_short = False

    minimal_roi = {"0": 10.0}
    stoploss = -0.99

    trailing_stop = False
    process_only_new_candles = True

    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = True

    startup_candle_count: int = 100

    tp1_profit = 0.60

    def _merge_factors(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        pair = metadata.get("pair", "")
        if not pair:
            return dataframe
        root = Path("user_data/data/_cache/enriched_daily/binance")
        fname = pair.replace("/", "_") + "-1d.feather"
        path = root / fname
        if not path.exists():
            return dataframe
        factors = pd.read_feather(path)
        factors_date = factors["date"]
        factors = factors.assign(date=pd.to_datetime(factors_date, utc=True))
        keep_cols = ["date", "dxy_close"]
        avail = [c for c in keep_cols if c in factors.columns]
        sel = factors[avail].copy()
        dataframe["date"] = pd.to_datetime(dataframe["date"], utc=True)
        merged = dataframe.merge(sel, on="date", how="left")
        return merged

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["ema30"] = ta.EMA(dataframe, timeperiod=30)
        dataframe["ema100"] = ta.EMA(dataframe, timeperiod=100)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe = self._merge_factors(dataframe, metadata)
        if "dxy_close" not in dataframe.columns:
            dataframe["dxy_close"] = np.nan
        dataframe["dxy_sma7"] = dataframe["dxy_close"].rolling(7).mean()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cross_up = (dataframe["ema30"] > dataframe["ema100"]) & (dataframe["ema30"].shift(1) <= dataframe["ema100"].shift(1))
        condition = cross_up & (dataframe["adx"] > 15)
        # DXY declining: current < 7d SMA (dollar weakening = crypto bullish)
        dxy_declining = dataframe["dxy_close"] < dataframe["dxy_sma7"]
        condition &= dxy_declining | dataframe["dxy_close"].isna()
        dataframe.loc[condition, "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cross_down = (dataframe["ema30"] < dataframe["ema100"]) & (dataframe["ema30"].shift(1) >= dataframe["ema100"].shift(1))
        dataframe.loc[cross_down, "exit_long"] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, **kwargs) -> Optional[str]:
        if current_profit >= self.tp1_profit:
            return "tp1_60pct_profit"
        return None

