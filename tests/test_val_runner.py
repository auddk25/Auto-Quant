from __future__ import annotations

import val


def test_val_runner_uses_2026_out_of_sample_timerange() -> None:
    assert val.TIMERANGE == "20260101-20260420"


def test_val_runner_uses_separate_val_datadir() -> None:
    assert val.VAL_DATA_DIR.name == "data_val"
    assert val.VAL_ENRICHED_ROOT == val.VAL_DATA_DIR / "_cache" / "enriched" / "binance"


def test_val_runner_uses_same_active_strategy_discovery_as_run_py() -> None:
    assert val.discover_val_strategies() == [
        "FactorMeanRevCandidate",
        "MeanRevADX",
        "StochMeanRev",
    ]
