from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = PROJECT_ROOT / "user_data" / "strategies" / "StochMeanRev.py"


def _load_strategy_class():
    spec = importlib.util.spec_from_file_location("StochMeanRev", STRATEGY_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.StochMeanRev


def test_stoch_mean_rev_uses_022_entry_threshold() -> None:
    strategy_cls = _load_strategy_class()
    strategy = strategy_cls(config={})

    assert strategy.stoch_entry_threshold == 0.22


def test_stoch_mean_rev_entry_threshold_is_applied() -> None:
    strategy_cls = _load_strategy_class()
    strategy = strategy_cls(config={})
    ready = pd.DataFrame(
        {
            "close": [100.0, 100.0],
            "ema200": [90.0, 90.0],
            "adx": [25.0, 25.0],
            "bb_lower": [105.0, 105.0],
            "stoch_k": [0.21, 0.23],
        }
    )

    entries = strategy.populate_entry_trend(ready, {"pair": "BTC/USDT"})

    assert entries["enter_long"].fillna(0).tolist() == [1.0, 0.0]
