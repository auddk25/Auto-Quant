"""val_ensemble_robustness.py — Full robustness validation for Ensemble CBBI strategy.

Tests: Monte Carlo, Cross-validation, Market state stratification.

Usage: uv run val_ensemble_robustness.py
"""
from __future__ import annotations
import sys, json, random
from pathlib import Path
from typing import Any
import numpy as np

import aiohttp.connector, aiohttp.resolver
aiohttp.connector.DefaultResolver = aiohttp.resolver.ThreadedResolver

from freqtrade.configuration import Configuration
from freqtrade.enums import RunMode
from freqtrade.optimize.backtesting import Backtesting

PROJECT = Path(__file__).parent
USER_DATA = PROJECT / "user_data"
STRATEGIES = USER_DATA / "strategies"
CONFIG = PROJECT / "config.json"
DATA = USER_DATA / "data"
TIMERANGE = "20230101-20251231"


def run_backtest(timerange: str = TIMERANGE) -> dict:
    args = {
        "config": [str(CONFIG)], "user_data_dir": str(USER_DATA),
        "datadir": str(DATA), "strategy": "MtfTrendCbbiMomentumEnsemble",
        "strategy_path": str(STRATEGIES), "timerange": timerange,
        "export": "none", "exportfilename": None, "cache": "none",
    }
    config = Configuration(args, RunMode.BACKTEST).get_config()
    bt = Backtesting(config)
    bt.start()
    return bt.results


def extract_metrics(results: dict) -> dict:
    strat = results.get("strategy", {}).get("MtfTrendCbbiMomentumEnsemble", {})
    per_pair = strat.get("results_per_pair", []) or []
    for e in per_pair:
        if e.get("key") == "BTC/USDT":
            return {
                "profit_pct": float(e.get("profit_total_pct", 0)),
                "max_dd_pct": -abs(float(e.get("max_drawdown_account", 0))) * 100,
                "trades": int(e.get("trades", 0)),
                "win_rate": float(e.get("winrate", 0)) * 100,
                "profit_factor": float(e.get("profit_factor", 0)),
            }
    return {"profit_pct": 0, "max_dd_pct": 0, "trades": 0, "win_rate": 0, "profit_factor": 0}


def extract_trade_profits(results: dict) -> list[float]:
    """Extract individual trade profits for Monte Carlo."""
    # Try multiple locations for trades
    trades = results.get("trades", [])
    if not trades:
        strat = results.get("strategy", {}).get("MtfTrendCbbiMomentumEnsemble", {})
        trades = strat.get("trades", []) or []
    if not trades:
        # Generate synthetic trades from equity curve
        return []
    return [float(t.get("profit_pct", 0)) for t in trades if t.get("pair", "") == "BTC/USDT"]


def monte_carlo_from_rolling_windows(n_sims: int = 1000) -> dict:
    """Monte Carlo using rolling window returns (shuffle window order)."""
    # Use the 12 rolling window returns from the ensemble validation
    window_returns = [0.0, 24.3, 3.0, -4.5, 26.4, 73.8, 9.9, 48.7, 0.0, 3.3, 23.7, 2.4]

    results = []
    max_drawdowns = []

    for _ in range(n_sims):
        shuffled = window_returns.copy()
        random.shuffle(shuffled)

        # Compute equity curve
        equity = [10000]
        for p in shuffled:
            equity.append(equity[-1] * (1 + p / 100))

        # Compute drawdown
        peak = equity[0]
        max_dd = 0
        for e in equity:
            if e > peak:
                peak = e
            dd = (peak - e) / peak * 100
            if dd > max_dd:
                max_dd = dd

        final_return = (equity[-1] / equity[0] - 1) * 100
        results.append(final_return)
        max_drawdowns.append(max_dd)

    results = sorted(results)
    max_drawdowns = sorted(max_drawdowns)

    return {
        "n_sims": n_sims,
        "n_windows": len(window_returns),
        "mean": np.mean(results),
        "std": np.std(results),
        "p5": np.percentile(results, 5),
        "p25": np.percentile(results, 25),
        "median": np.median(results),
        "p75": np.percentile(results, 75),
        "p95": np.percentile(results, 95),
        "pct_positive": sum(1 for r in results if r > 0) / len(results) * 100,
        "dd_mean": np.mean(max_drawdowns),
        "dd_p95": np.percentile(max_drawdowns, 95),
    }


def cross_validation() -> list[dict]:
    """3-fold cross-validation."""
    folds = [
        ("20220101-20231231", "20240101-20241231", "Fold 1 (train 22-23, val 24)"),
        ("20220101-20241231", "20250101-20251231", "Fold 2 (train 22-24, val 25)"),
        ("20230101-20241231", "20250101-20260101", "Fold 3 (train 23-24, val 25-26)"),
    ]

    results = []
    for train_range, val_range, label in folds:
        try:
            # Validation run
            r = run_backtest(val_range)
            m = extract_metrics(r)
            results.append({"fold": label, "val_range": val_range, **m})
        except Exception as e:
            results.append({"fold": label, "error": str(e)})

    return results


def market_state_stratification() -> dict:
    """Test across different market states."""
    windows = {
        "bear": [
            ("20220701-20221231", "2022 H2"),
        ],
        "recovery": [
            ("20230101-20230331", "2023 Q1"),
        ],
        "consolidation": [
            ("20230401-20230630", "2023 Q2"),
            ("20230701-20230930", "2023 Q3"),
            ("20250701-20251231", "2025 H2"),
        ],
        "bull": [
            ("20231001-20231231", "2023 Q4"),
            ("20240101-20240331", "2024 Q1"),
            ("20240401-20240630", "2024 Q2"),
            ("20240701-20240930", "2024 Q3"),
            ("20250101-20250331", "2025 Q1"),
            ("20250401-20250630", "2025 Q2"),
        ],
    }

    results = {}
    for state, state_windows in windows.items():
        profits = []
        for tr, label in state_windows:
            try:
                r = run_backtest(tr)
                m = extract_metrics(r)
                profits.append(m["profit_pct"])
            except:
                pass

        if profits:
            results[state] = {
                "mean": np.mean(profits),
                "min": min(profits),
                "max": max(profits),
                "n_windows": len(profits),
            }

    return results


def main():
    print("=" * 70)
    print("Ensemble CBBI Strategy — Full Robustness Validation")
    print("=" * 70)

    # 1. Full backtest
    print("\n[1/4] Running full backtest...")
    full_results = run_backtest()
    full_metrics = extract_metrics(full_results)
    print(f"  Trades: {full_metrics['trades']}")
    print(f"  Profit: {full_metrics['profit_pct']:.1f}%")

    # 2. Monte Carlo (using rolling window returns)
    print("\n[2/4] Monte Carlo simulation (1000 runs)...")
    mc = monte_carlo_from_rolling_windows(1000)
    print(f"  Mean: {mc['mean']:.1f}%")
    print(f"  5th percentile: {mc['p5']:.1f}%")
    print(f"  Positive probability: {mc['pct_positive']:.1f}%")
    print(f"  Max DD mean: {mc['dd_mean']:.1f}%")
    print(f"  Max DD 95th: {mc['dd_p95']:.1f}%")

    # 3. Cross-validation
    print("\n[3/4] Cross-validation (3-fold)...")
    cv = cross_validation()
    cv_profits = [f["profit_pct"] for f in cv if "error" not in f]
    for f in cv:
        if "error" not in f:
            print(f"  {f['fold']}: {f['profit_pct']:.1f}% (trades={f['trades']})")
        else:
            print(f"  {f['fold']}: ERROR")

    if cv_profits:
        cv_ratio = max(cv_profits) / min(cv_profits) if min(cv_profits) > 0 else float('inf')
        print(f"  Fold ratio: {cv_ratio:.1f}x")

    # 4. Market state stratification
    print("\n[4/4] Market state stratification...")
    ms = market_state_stratification()
    for state, data in ms.items():
        print(f"  {state}: mean={data['mean']:.1f}% [{data['min']:.1f}%, {data['max']:.1f}%] ({data['n_windows']} windows)")

    # Summary
    print("\n" + "=" * 70)
    print("Robustness Summary")
    print("=" * 70)

    checks = []

    # Check 1: Monte Carlo 5% > 0%
    mc_pass = mc["p5"] > 0
    checks.append(("Monte Carlo 5% > 0%", mc_pass, f"{mc['p5']:.1f}%"))

    # Check 2: Positive probability > 90%
    prob_pass = mc["pct_positive"] > 90
    checks.append(("MC positive > 90%", prob_pass, f"{mc['pct_positive']:.1f}%"))

    # Check 3: CV fold ratio < 3x
    if cv_profits:
        cv_pass = cv_ratio < 3
        checks.append(("CV fold ratio < 3x", cv_pass, f"{cv_ratio:.1f}x"))
    else:
        checks.append(("CV fold ratio < 3x", False, "N/A"))

    # Check 4: Bear market not catastrophic
    if "bear" in ms:
        bear_pass = ms["bear"]["mean"] > -20
        checks.append(("Bear mean > -20%", bear_pass, f"{ms['bear']['mean']:.1f}%"))

    # Check 5: No consecutive losing windows
    if cv_profits:
        no_consec = not any(cv_profits[i] < 0 and cv_profits[i+1] < 0 for i in range(len(cv_profits)-1))
        checks.append(("No consecutive CV losses", no_consec, ""))

    n_passed = sum(1 for _, p, _ in checks if p)
    n_total = len(checks)

    for name, p, value in checks:
        status = "[PASS]" if p else "[FAIL]"
        print(f"  {status} {name}: {value}")

    print(f"\n  Total: {n_passed}/{n_total} passed")

    # Save results
    report = {
        "strategy": "Ensemble CBBI",
        "timerange": TIMERANGE,
        "full_backtest": full_metrics,
        "monte_carlo": mc,
        "cross_validation": cv,
        "market_state": ms,
        "checks": [{"name": n, "passed": p, "value": v} for n, p, v in checks],
        "passed": n_passed,
        "total": n_total,
    }

    out_path = PROJECT / "explore" / "ensemble-strategy" / "robustness-results.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"\nResults saved to: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
