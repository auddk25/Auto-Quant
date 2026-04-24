from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

from run import discover_strategies


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STRATEGY_PATH = PROJECT_ROOT / "user_data" / "strategies" / "FactorMeanRevCandidate.py"


def _load_candidate_class():
    spec = importlib.util.spec_from_file_location("_FactorMeanRevCandidate", STRATEGY_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FactorMeanRevCandidate


def _sample_ohlcv(rows: int = 260) -> pd.DataFrame:
    dates = pd.date_range("2023-01-01", periods=rows, freq="h", tz="UTC")
    close = pd.Series([110.0] * rows)
    close.iloc[-40:] = 100.0
    close.iloc[-5:] = [95.0, 94.0, 93.0, 92.0, 90.0]
    return pd.DataFrame(
        {
            "date": dates,
            "open": close + 0.2,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": [100.0] * rows,
        }
    )


def test_factor_candidate_is_active_in_default_run_discovery() -> None:
    assert "FactorMeanRevCandidate" in discover_strategies()
    assert "_FactorMeanRevCandidate" not in discover_strategies()


def test_factor_candidate_merges_sidecar_and_blocks_hot_funding(tmp_path: Path) -> None:
    enriched_root = tmp_path / "enriched" / "binance"
    enriched_root.mkdir(parents=True)
    base = _sample_ohlcv()
    sidecar = pd.DataFrame(
        {
            "date": base["date"],
            "funding_rate": [-0.0002] * (len(base) - 1) + [0.0012],
            "stablecoin_mcap_growth": [0.001] * len(base),
            "fed_net_liquidity": [6_000_000_000_000.0] * len(base),
        }
    )
    sidecar.to_feather(enriched_root / "BTC_USDT-1h.feather")

    candidate_cls = _load_candidate_class()
    strategy = candidate_cls(config={})
    strategy.enriched_root = enriched_root

    with_indicators = strategy.populate_indicators(base.copy(), {"pair": "BTC/USDT"})
    with_entries = strategy.populate_entry_trend(with_indicators, {"pair": "BTC/USDT"})

    assert {"funding_rate", "stablecoin_mcap_growth", "fed_net_liquidity"}.issubset(
        with_entries.columns
    )
    assert with_entries["enter_long"].fillna(0).iloc[-1] == 0


def test_factor_candidate_thresholds_are_configurable(tmp_path: Path) -> None:
    ready = pd.DataFrame(
        {
            "close": [100.0],
            "ema200": [90.0],
            "adx": [25.0],
            "bb_lower": [105.0],
            "stoch_k": [0.10],
            "funding_rate": [-0.0002],
            "stablecoin_mcap_growth": [0.001],
            "fed_net_liquidity": [6_000_000_000_000.0],
        }
    )

    candidate_cls = _load_candidate_class()
    permissive = candidate_cls(config={})
    permissive.max_funding_rate = 0.0005
    permissive.min_stablecoin_mcap_growth = -0.002
    permissive_entries = permissive.populate_entry_trend(ready.copy(), {"pair": "BTC/USDT"})

    restrictive = candidate_cls(config={})
    restrictive.max_funding_rate = -0.001
    restrictive.min_stablecoin_mcap_growth = -0.002
    restrictive_entries = restrictive.populate_entry_trend(ready.copy(), {"pair": "BTC/USDT"})

    assert permissive_entries["enter_long"].fillna(0).sum() > 0
    assert restrictive_entries["enter_long"].fillna(0).sum() == 0


def test_factor_candidate_defaults_use_positive_stablecoin_growth_gate() -> None:
    ready = pd.DataFrame(
        {
            "close": [100.0],
            "ema200": [90.0],
            "adx": [25.0],
            "bb_lower": [105.0],
            "stoch_k": [0.10],
            "funding_rate": [0.0002],
            "stablecoin_mcap_growth": [-0.0001],
            "fed_net_liquidity": [6_000_000_000_000.0],
        }
    )

    candidate_cls = _load_candidate_class()
    strategy = candidate_cls(config={})
    entries = strategy.populate_entry_trend(ready.copy(), {"pair": "BTC/USDT"})

    assert entries["enter_long"].fillna(0).sum() == 0


def test_factor_candidate_defaults_to_25_period_stoch_rsi() -> None:
    candidate_cls = _load_candidate_class()
    strategy = candidate_cls(config={})

    assert strategy.stoch_rsi_period == 25


def test_factor_candidate_uses_stoch_rules_without_factor_gate_for_eth() -> None:
    ready = pd.DataFrame(
        {
            "close": [100.0],
            "ema200": [90.0],
            "adx": [25.0],
            "bb_lower": [105.0],
            "stoch_k": [0.99],
            "stoch_factor_k": [0.99],
            "stoch_stable_k": [0.21],
            "funding_rate": [0.01],
            "stablecoin_mcap_growth": [-0.01],
            "fed_net_liquidity": [pd.NA],
        }
    )

    candidate_cls = _load_candidate_class()
    strategy = candidate_cls(config={})
    entries = strategy.populate_entry_trend(ready.copy(), {"pair": "ETH/USDT"})

    assert entries["enter_long"].fillna(0).tolist() == [1.0]


def test_factor_candidate_requires_positive_btc_stablecoin_7d_impulse() -> None:
    ready = pd.DataFrame(
        {
            "close": [100.0, 100.0],
            "ema200": [90.0, 90.0],
            "adx": [25.0, 25.0],
            "bb_lower": [105.0, 105.0],
            "stoch_k": [0.10, 0.10],
            "stoch_factor_k": [0.10, 0.10],
            "funding_rate": [0.0001, 0.0001],
            "stablecoin_mcap_growth": [0.001, 0.001],
            "stablecoin_mcap_growth_7d": [-0.001, 0.001],
            "fed_net_liquidity": [6_000_000_000_000.0, 6_000_000_000_000.0],
        }
    )

    candidate_cls = _load_candidate_class()
    strategy = candidate_cls(config={})
    entries = strategy.populate_entry_trend(ready.copy(), {"pair": "BTC/USDT"})

    assert entries["enter_long"].fillna(0).tolist() == [0.0, 1.0]
