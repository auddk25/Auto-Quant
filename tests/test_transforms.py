from __future__ import annotations

import pandas as pd

from autoq_data.transforms import (
    add_cvd_features,
    merge_daily_factors,
    merge_hourly_factors,
)


def test_merge_daily_factors_shifts_one_day_and_never_looks_ahead() -> None:
    base = pd.DataFrame(
        {
            "date": pd.to_datetime(
                [
                    "2023-01-02 00:00:00+00:00",
                    "2023-01-02 12:00:00+00:00",
                    "2023-01-03 00:00:00+00:00",
                    "2023-01-03 12:00:00+00:00",
                ],
                utc=True,
            ),
            "close": [100.0, 101.0, 102.0, 103.0],
        }
    )
    daily = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2023-01-01 00:00:00+00:00", "2023-01-02 00:00:00+00:00"], utc=True
            ),
            "us10y_close": [3.80, 3.90],
        }
    )

    merged = merge_daily_factors(base, daily, ["us10y_close"])

    assert merged["us10y_close"].tolist() == [3.80, 3.80, 3.90, 3.90]


def test_merge_hourly_factors_only_matches_exact_hour() -> None:
    base = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2023-01-01 00:00:00+00:00", "2023-01-01 01:00:00+00:00"], utc=True
            ),
            "close": [10.0, 11.0],
        }
    )
    hourly = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2023-01-01 01:00:00+00:00", "2023-01-01 02:00:00+00:00"], utc=True
            ),
            "funding_rate": [0.001, 0.002],
        }
    )

    merged = merge_hourly_factors(base, hourly, ["funding_rate"])

    assert pd.isna(merged.loc[0, "funding_rate"])
    assert merged.loc[1, "funding_rate"] == 0.001


def test_add_cvd_features_derives_buy_sell_delta_and_cumsum() -> None:
    spot = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2023-01-01 00:00:00+00:00", "2023-01-01 01:00:00+00:00"], utc=True
            ),
            "volume": [10.0, 12.0],
            "taker_buy_base_volume": [7.0, 4.0],
        }
    )

    enriched = add_cvd_features(spot)

    assert enriched["taker_sell_base_volume"].tolist() == [3.0, 8.0]
    assert enriched["taker_delta_volume"].tolist() == [4.0, -4.0]
    assert enriched["cvd"].tolist() == [4.0, 0.0]
