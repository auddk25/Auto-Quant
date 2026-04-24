from __future__ import annotations

from run import discover_strategies


def test_active_strategy_roster_promotes_factor_candidate_and_archives_hybrid() -> None:
    assert discover_strategies() == [
        "FactorMeanRevCandidate",
        "MeanRevADX",
        "StochMeanRev",
    ]
