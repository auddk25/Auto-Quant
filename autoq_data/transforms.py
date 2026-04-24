from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd


CORE_OHLCV_COLUMNS = ["date", "open", "high", "low", "close", "volume"]
OPTIONAL_COLUMNS = ["btc_dvol", "stablecoin_mcap", "stablecoin_mcap_growth"]


def ensure_utc_dates(frame: pd.DataFrame, column: str = "date") -> pd.DataFrame:
    normalized = frame.copy()
    normalized[column] = pd.to_datetime(normalized[column], utc=True)
    normalized = normalized.sort_values(column).reset_index(drop=True)
    return normalized


def core_ohlcv_view(frame: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in CORE_OHLCV_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Base OHLCV frame is missing columns: {missing}")
    return ensure_utc_dates(frame.loc[:, CORE_OHLCV_COLUMNS])


def add_cvd_features(spot_frame: pd.DataFrame) -> pd.DataFrame:
    enriched = ensure_utc_dates(spot_frame)
    enriched["taker_buy_base_volume"] = pd.to_numeric(
        enriched["taker_buy_base_volume"], errors="coerce"
    )
    enriched["volume"] = pd.to_numeric(enriched["volume"], errors="coerce")
    enriched["taker_sell_base_volume"] = enriched["volume"] - enriched["taker_buy_base_volume"]
    enriched["taker_delta_volume"] = (
        enriched["taker_buy_base_volume"] - enriched["taker_sell_base_volume"]
    )
    enriched["cvd"] = enriched["taker_delta_volume"].cumsum()
    return enriched


def merge_hourly_factors(
    base_frame: pd.DataFrame, factor_frame: pd.DataFrame, columns: Iterable[str]
) -> pd.DataFrame:
    merged = ensure_utc_dates(base_frame)
    factors = ensure_utc_dates(factor_frame)
    selected = ["date", *columns]
    return merged.merge(factors.loc[:, selected], on="date", how="left")


def merge_daily_factors(
    base_frame: pd.DataFrame, factor_frame: pd.DataFrame, columns: Iterable[str]
) -> pd.DataFrame:
    merged = ensure_utc_dates(base_frame)
    factors = ensure_utc_dates(factor_frame).copy()
    factors["date"] = factors["date"].dt.normalize() + pd.Timedelta(days=1)

    return pd.merge_asof(
        merged.sort_values("date"),
        factors.loc[:, ["date", *columns]].sort_values("date"),
        on="date",
        direction="backward",
    )


def fill_optional_columns(frame: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    enriched = frame.copy()
    for column in columns:
        if column not in enriched.columns:
            enriched[column] = np.nan
    return enriched


def enrich_pair_dataframe(
    base_frame: pd.DataFrame,
    spot_frame: pd.DataFrame,
    funding_frame: pd.DataFrame,
    open_interest_frame: pd.DataFrame,
    macro_frame: pd.DataFrame,
    dvol_frame: pd.DataFrame | None,
    stablecoin_frame: pd.DataFrame | None,
) -> pd.DataFrame:
    enriched = core_ohlcv_view(base_frame)

    spot_features = add_cvd_features(spot_frame)[
        [
            "date",
            "taker_buy_base_volume",
            "taker_sell_base_volume",
            "taker_delta_volume",
            "cvd",
        ]
    ]
    enriched = merge_hourly_factors(
        enriched,
        spot_features,
        [
            "taker_buy_base_volume",
            "taker_sell_base_volume",
            "taker_delta_volume",
            "cvd",
        ],
    )
    enriched = merge_hourly_factors(enriched, funding_frame, ["funding_rate"])
    enriched = merge_hourly_factors(enriched, open_interest_frame, ["open_interest"])
    enriched = merge_daily_factors(
        enriched,
        macro_frame,
        ["us10y_close", "dxy_close", "fed_net_liquidity"],
    )

    if dvol_frame is not None:
        enriched = merge_hourly_factors(enriched, dvol_frame, ["btc_dvol"])
    if stablecoin_frame is not None:
        enriched = merge_daily_factors(
            enriched, stablecoin_frame, ["stablecoin_mcap", "stablecoin_mcap_growth"]
        )

    return fill_optional_columns(enriched, OPTIONAL_COLUMNS)
