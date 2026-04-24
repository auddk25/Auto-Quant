from __future__ import annotations

import stress


def test_stress_runner_uses_2022_bear_market_timerange() -> None:
    assert stress.TIMERANGE == "20220101-20221231"


def test_stress_runner_uses_separate_stress_datadir() -> None:
    assert stress.STRESS_DATA_DIR.name == "data_stress"
    assert stress.STRESS_ENRICHED_ROOT == stress.STRESS_DATA_DIR / "_cache" / "enriched" / "binance"


def test_stress_runner_uses_same_active_strategy_discovery_as_run_py() -> None:
    assert stress.discover_stress_strategies() == [
        "FactorMeanRevCandidate",
        "MeanRevADX",
        "StochMeanRev",
    ]
