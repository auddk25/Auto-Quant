from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd

from autoq_data.sources import SourceClient, normalize_binance_epoch_series


def test_normalize_binance_epoch_series_handles_mixed_millisecond_and_microsecond_rows() -> None:
    values = pd.Series([1672531200000, 1764547200000000])

    parsed = normalize_binance_epoch_series(values)

    assert parsed.tolist() == [
        pd.Timestamp("2023-01-01 00:00:00+00:00"),
        pd.Timestamp("2025-12-01 00:00:00+00:00"),
    ]


def _make_funding_csv_frame(ts_ms: int, rate: float) -> pd.DataFrame:
    return pd.DataFrame({"calc_time": [ts_ms], "funding_interval_hours": [8], "last_funding_rate": [rate]})


def test_load_funding_rate_falls_back_to_daily_when_monthly_archive_missing(tmp_path: Path) -> None:
    client = SourceClient(cache_dir=tmp_path)
    start = pd.Timestamp("2026-04-01", tz="UTC")
    end = pd.Timestamp("2026-04-02", tz="UTC")

    daily_frame = _make_funding_csv_frame(int(start.timestamp() * 1000), 0.0001)

    with (
        patch.object(client, "_read_binance_funding_month", side_effect=RuntimeError("404")),
        patch.object(client, "_read_binance_funding_day", return_value=daily_frame) as mock_day,
    ):
        result = client.load_funding_rate("BTCUSDT", start, end)

    assert mock_day.called
    assert "funding_rate" in result.columns
    assert not result["funding_rate"].isna().all()


def test_load_funding_rate_raises_when_both_monthly_and_daily_unavailable(tmp_path: Path) -> None:
    client = SourceClient(cache_dir=tmp_path)
    start = pd.Timestamp("2026-04-01", tz="UTC")
    end = pd.Timestamp("2026-04-01 02:00:00", tz="UTC")

    with (
        patch.object(client, "_read_binance_funding_month", side_effect=RuntimeError("404")),
        patch.object(client, "_read_binance_funding_day", side_effect=RuntimeError("404")),
    ):
        try:
            client.load_funding_rate("BTCUSDT", start, end)
            assert False, "expected RuntimeError"
        except RuntimeError as exc:
            assert "BTCUSDT" in str(exc)
