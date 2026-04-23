from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from autoq_data.strategy_bridge import merge_external_factors


def test_merge_external_factors_joins_pair_specific_sidecar_columns(tmp_path: Path) -> None:
    enriched_root = tmp_path / "user_data" / "data" / "_cache" / "enriched" / "binance"
    enriched_root.mkdir(parents=True, exist_ok=True)
    sidecar = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2023-01-01 00:00:00+00:00", "2023-01-01 01:00:00+00:00"], utc=True
            ),
            "funding_rate": [0.001, 0.002],
            "btc_dvol": [65.0, 66.0],
        }
    )
    sidecar.to_feather(enriched_root / "BTC_USDT-1h.feather")

    base = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2023-01-01 00:00:00+00:00", "2023-01-01 01:00:00+00:00"], utc=True
            ),
            "close": [100.0, 101.0],
        }
    )

    merged = merge_external_factors(
        base,
        {"pair": "BTC/USDT"},
        columns=["funding_rate", "btc_dvol"],
        enriched_root=enriched_root,
    )

    assert merged["funding_rate"].tolist() == [0.001, 0.002]
    assert merged["btc_dvol"].tolist() == [65.0, 66.0]
    assert merged["close"].tolist() == [100.0, 101.0]


def test_merge_external_factors_returns_nan_columns_when_sidecar_missing(tmp_path: Path) -> None:
    enriched_root = tmp_path / "user_data" / "data" / "_cache" / "enriched" / "binance"
    base = pd.DataFrame(
        {
            "date": pd.to_datetime(["2023-01-01 00:00:00+00:00"], utc=True),
            "close": [100.0],
        }
    )

    merged = merge_external_factors(
        base,
        {"pair": "ETH/USDT"},
        columns=["funding_rate", "btc_dvol"],
        enriched_root=enriched_root,
    )

    assert len(merged) == 1
    assert pd.isna(merged.loc[0, "funding_rate"])
    assert pd.isna(merged.loc[0, "btc_dvol"])


def test_merge_external_factors_uses_environment_root_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    enriched_root = tmp_path / "stress" / "_cache" / "enriched" / "binance"
    enriched_root.mkdir(parents=True)
    pd.DataFrame(
        {
            "date": pd.to_datetime(["2022-01-01 00:00:00+00:00"], utc=True),
            "funding_rate": [0.003],
        }
    ).to_feather(enriched_root / "BTC_USDT-1h.feather")
    monkeypatch.setenv("AUTOQ_ENRICHED_ROOT", str(enriched_root))

    base = pd.DataFrame(
        {
            "date": pd.to_datetime(["2022-01-01 00:00:00+00:00"], utc=True),
            "close": [100.0],
        }
    )

    merged = merge_external_factors(base, {"pair": "BTC/USDT"}, columns=["funding_rate"])

    assert merged.loc[0, "funding_rate"] == 0.003
