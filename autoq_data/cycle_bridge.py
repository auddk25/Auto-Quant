"""Cycle indicator bridge — AHR999 + CBBI for cycle-timing strategies.

AHR999 is computed within the strategy from daily OHLCV (no external data needed).
CBBI must be pre-fetched once via `prepare_cbbi.py` and cached as a feather file.

Usage in strategy:
    from autoq_data.cycle_bridge import compute_ahr999, merge_cbbi

    @informative("1d")
    def populate_indicators_1d(self, dataframe, metadata):
        dataframe = compute_ahr999(dataframe)  # adds 'ahr999' column
        return dataframe

    def populate_indicators(self, dataframe, metadata):
        dataframe = merge_cbbi(dataframe, metadata)  # adds 'cbbi' column
        return dataframe
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from datetime import datetime
from pathlib import Path

GENESIS_DATE = pd.Timestamp("2009-01-03", tz="UTC")
USER_DATA = Path(__file__).parent.parent / "user_data"
CBBI_CACHE = USER_DATA / "data" / "_cache" / "cbbi_daily.feather"


def compute_ahr999(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Compute AHR999 index on a daily-OHLCV dataframe.

    AHR999 = (close / SMA200) * (close / exponential_growth_line)
    Values < 0.45 indicate severe undervaluation.
    """
    dates = pd.to_datetime(dataframe["date"])
    days = (dates - GENESIS_DATE).dt.days.astype(float)
    log_growth = 10 ** (5.8450937 * np.log10(days) - 17.015931)
    sma200 = dataframe["close"].rolling(200).mean()
    dataframe["ahr999"] = (dataframe["close"] / sma200) * (dataframe["close"] / log_growth)
    return dataframe


def merge_cbbi(dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
    """Merge pre-fetched CBBI into the 1h dataframe.

    CBBI is daily — forward-filled within the day.
    If cache file is missing, CBBI column is filled with NaN.
    """
    if not CBBI_CACHE.exists():
        dataframe["cbbi"] = np.nan
        return dataframe

    cbbi = pd.read_feather(CBBI_CACHE)
    date_col = pd.to_datetime(cbbi["date"]).dt.tz_localize(None)
    cbbi = cbbi.copy()
    cbbi["_date_naive"] = date_col.dt.normalize()
    cbbi = cbbi.set_index("_date_naive")

    df_dates = pd.to_datetime(dataframe["date"]).dt.tz_localize(None)
    daily_dates = df_dates.dt.normalize()
    mapped = daily_dates.map(cbbi["cbbi"])
    dataframe["cbbi"] = mapped.ffill().values
    return dataframe


AHR999_CACHE = USER_DATA / "data" / "_cache" / "ahr999_daily.feather"


def merge_ahr999(dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
    """Merge pre-computed AHR999 into the 1h dataframe.

    AHR999 is daily — forward-filled within the day.
    If cache file is missing, use a simple close/SMA200 proxy.
    """
    if not AHR999_CACHE.exists():
        close_d = dataframe["close_1d"].ffill()
        sma200_d = dataframe["sma200_1d"].ffill()
        dataframe["ahr999"] = close_d / sma200_d
        return dataframe

    ahr = pd.read_feather(AHR999_CACHE)
    date_col = pd.to_datetime(ahr["date"]).dt.tz_localize(None)
    ahr = ahr.copy()
    ahr["_date_naive"] = date_col.dt.normalize()
    ahr = ahr.set_index("_date_naive")

    df_dates = pd.to_datetime(dataframe["date"]).dt.tz_localize(None)
    daily_dates = df_dates.dt.normalize()
    mapped = daily_dates.map(ahr["ahr999"])
    dataframe["ahr999"] = mapped.ffill().values
    return dataframe
