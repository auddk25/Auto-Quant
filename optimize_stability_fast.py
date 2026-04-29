"""optimize_stability_fast.py — Focused parameter stability optimization.

Only scans EXIT_THRESHOLD × CB_THRESHOLD (20 combos) with fixed ENTRY_MOM=3, EXIT_MOM=3.
Also runs rolling window validation on best candidates.

Usage: uv run optimize_stability_fast.py
"""
from __future__ import annotations
import sys, json
from pathlib import Path
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

# Focused grid: only the 2 most impactful parameters
EXIT_THRESHOLDS = [-0.025, -0.022, -0.020, -0.018, -0.015, -0.012, -0.010]
CB_THRESHOLDS = [0.55, 0.60, 0.65, 0.70, 0.75]

# Rolling windows for validation
ROLLING_WINDOWS = [
    ("2022-07-01", "2022-12-31", "2022 H2"),
    ("2023-01-01", "2023-03-31", "2023 Q1"),
    ("2023-04-01", "2023-06-30", "2023 Q2"),
    ("2023-07-01", "2023-09-30", "2023 Q3"),
    ("2023-10-01", "2023-12-31", "2023 Q4"),
    ("2024-01-01", "2024-03-31", "2024 Q1"),
    ("2024-04-01", "2024-06-30", "2024 Q2"),
    ("2024-07-01", "2024-09-30", "2023 Q3"),
    ("2024-10-01", "2024-12-31", "2024 Q4"),
    ("2025-01-01", "2025-03-31", "2025 Q1"),
    ("2025-04-01", "2025-06-30", "2025 Q2"),
    ("2025-07-01", "2025-12-31", "2025 H2"),
]


def run_backtest(params: dict, timerange: str = TIMERANGE) -> dict:
    """Run backtest with given params."""
    args = {
        "config": [str(CONFIG)], "user_data_dir": str(USER_DATA),
        "datadir": str(DATA), "strategy": "MtfTrendCbbiMomentumParam",
        "strategy_path": str(STRATEGIES), "timerange": timerange,
        "export": "none", "exportfilename": None, "cache": "none",
    }
    config = Configuration(args, RunMode.BACKTEST).get_config()
    bt = Backtesting(config)
    strat = bt.strategylist[0]
    for k, v in params.items():
        setattr(strat, k, v)
    bt.start()
    return bt.results


def extract_metrics(results: dict) -> dict:
    """Extract metrics from backtest results."""
    strat = results.get("strategy", {}).get("MtfTrendCbbiMomentumParam", {})
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


def rolling_window_test(params: dict) -> list[dict]:
    """Run rolling window validation."""
    results = []
    for start, end, label in ROLLING_WINDOWS:
        try:
            r = run_backtest(params, f"{start.replace('-','')}-{end.replace('-','')}")
            m = extract_metrics(r)
            results.append({"window": label, **m})
        except Exception as e:
            results.append({"window": label, "error": str(e)})
    return results


def main():
    print("=" * 80)
    print("Focused Parameter Stability Optimization")
    print("=" * 80)
    print(f"\nTimerange: {TIMERANGE}")
    print(f"EXIT_THRESHOLDS: {EXIT_THRESHOLDS}")
    print(f"CB_THRESHOLDS: {CB_THRESHOLDS}")
    print(f"Fixed: ENTRY_MOM=3, EXIT_MOM=3, EXIT_CBBI=0.80")

    total = len(EXIT_THRESHOLDS) * len(CB_THRESHOLDS)
    print(f"\nTotal combinations: {total}")

    # Phase 1: Grid search
    print("\n" + "=" * 80)
    print("Phase 1: Grid Search (EXIT_THRESHOLD x CB_THRESHOLD)")
    print("=" * 80)

    all_results = []
    count = 0
    for exit_thresh in EXIT_THRESHOLDS:
        for cb_thresh in CB_THRESHOLDS:
            count += 1
            params = {
                "ENTRY_MOM": 3, "EXIT_MOM": 3,
                "CB_THRESHOLD": cb_thresh,
                "EXIT_THRESHOLD": exit_thresh,
                "EXIT_CBBI": 0.80,
            }
            try:
                r = run_backtest(params)
                m = extract_metrics(r)
                all_results.append({"params": params, **m})
                print(f"  [{count}/{total}] EXIT={exit_thresh} CB={cb_thresh} -> {m['profit_pct']:.1f}% trades={m['trades']}")
            except Exception as e:
                all_results.append({"params": params, "error": str(e)})
                print(f"  [{count}/{total}] EXIT={exit_thresh} CB={cb_thresh} -> ERROR")

    # Filter valid
    valid = [r for r in all_results if "error" not in r and r["trades"] >= 3]
    print(f"\nValid results: {len(valid)}/{len(all_results)}")

    # Sort by profit
    valid.sort(key=lambda x: x["profit_pct"], reverse=True)

    # Show top 10
    print("\nTop 10 by profit:")
    for i, r in enumerate(valid[:10]):
        p = r["params"]
        print(f"  #{i+1}: profit={r['profit_pct']:.1f}% dd={r['max_dd_pct']:.1f}% trades={r['trades']} wr={r['win_rate']:.0f}% | EXIT={p['EXIT_THRESHOLD']} CB={p['CB_THRESHOLD']}")

    # Stability analysis by EXIT_THRESHOLD
    print("\n" + "-" * 60)
    print("Stability by EXIT_THRESHOLD:")
    exit_groups = {}
    for r in valid:
        key = r["params"]["EXIT_THRESHOLD"]
        exit_groups.setdefault(key, []).append(r["profit_pct"])

    for thresh in sorted(exit_groups.keys()):
        profits = exit_groups[thresh]
        mean_p = np.mean(profits)
        std_p = np.std(profits)
        cv = std_p / mean_p * 100 if mean_p > 0 else 0
        stable = "STABLE" if cv < 30 else "UNSTABLE"
        print(f"  EXIT={thresh}: mean={mean_p:.1f}% std={std_p:.1f}% cv={cv:.1f}% [{stable}] n={len(profits)}")

    # Stability analysis by CB_THRESHOLD
    print("\nStability by CB_THRESHOLD:")
    cb_groups = {}
    for r in valid:
        key = r["params"]["CB_THRESHOLD"]
        cb_groups.setdefault(key, []).append(r["profit_pct"])

    for thresh in sorted(cb_groups.keys()):
        profits = cb_groups[thresh]
        mean_p = np.mean(profits)
        std_p = np.std(profits)
        cv = std_p / mean_p * 100 if mean_p > 0 else 0
        stable = "STABLE" if cv < 30 else "UNSTABLE"
        print(f"  CB={thresh}: mean={mean_p:.1f}% std={std_p:.1f}% cv={cv:.1f}% [{stable}] n={len(profits)}")

    # Find best stable combination
    print("\n" + "=" * 80)
    print("Phase 2: Best Stable Parameter Selection")
    print("=" * 80)

    # Score: profit / cv (higher = better return per unit risk)
    scored = []
    for r in valid:
        # Use the group CV as a proxy for stability
        exit_cv = np.std(exit_groups[r["params"]["EXIT_THRESHOLD"]]) / np.mean(exit_groups[r["params"]["EXIT_THRESHOLD"]]) * 100 if np.mean(exit_groups[r["params"]["EXIT_THRESHOLD"]]) > 0 else 999
        cb_cv = np.std(cb_groups[r["params"]["CB_THRESHOLD"]]) / np.mean(cb_groups[r["params"]["CB_THRESHOLD"]]) * 100 if np.mean(cb_groups[r["params"]["CB_THRESHOLD"]]) > 0 else 999
        avg_cv = (exit_cv + cb_cv) / 2
        score = r["profit_pct"] / avg_cv if avg_cv > 0 else 0
        scored.append({**r, "score": score, "avg_cv": avg_cv})

    scored.sort(key=lambda x: x["score"], reverse=True)

    print("\nTop 5 by stability-adjusted score (profit/CV):")
    for i, r in enumerate(scored[:5]):
        p = r["params"]
        print(f"  #{i+1}: score={r['score']:.3f} profit={r['profit_pct']:.1f}% avg_cv={r['avg_cv']:.1f}% | EXIT={p['EXIT_THRESHOLD']} CB={p['CB_THRESHOLD']}")

    # Phase 3: Rolling window validation on top 3 candidates
    print("\n" + "=" * 80)
    print("Phase 3: Rolling Window Validation (Top 3 Candidates)")
    print("=" * 80)

    candidates = scored[:3]
    for i, cand in enumerate(candidates):
        p = cand["params"]
        print(f"\nCandidate #{i+1}: EXIT={p['EXIT_THRESHOLD']} CB={p['CB_THRESHOLD']} (full profit={cand['profit_pct']:.1f}%)")
        print("-" * 60)

        rolling = rolling_window_test(p)
        valid_rolling = [r for r in rolling if "error" not in r]
        profits = [r["profit_pct"] for r in valid_rolling]
        trades = [r["trades"] for r in valid_rolling]

        if profits:
            mean_profit = np.mean(profits)
            no_trade_windows = sum(1 for r in rolling if r.get("trades", 0) == 0)
            losing_windows = sum(1 for p in profits if p < 0)

            for r in rolling:
                status = "[NO TRADE]" if r.get("trades", 0) == 0 else f"{r['profit_pct']:+.1f}%"
                print(f"  {r['window']}: {status} (trades={r.get('trades', 0)})")

            print(f"\n  Summary: mean={mean_profit:.1f}% no_trade={no_trade_windows} losing={losing_windows}")
            print(f"  Total trades: {sum(trades)}")

    # Final recommendation
    print("\n" + "=" * 80)
    print("Recommendation")
    print("=" * 80)

    if scored:
        best = scored[0]
        p = best["params"]
        print(f"\nBest stability-adjusted parameters:")
        print(f"  ENTRY_MOM = {p['ENTRY_MOM']}")
        print(f"  EXIT_MOM = {p['EXIT_MOM']}")
        print(f"  CB_THRESHOLD = {p['CB_THRESHOLD']}")
        print(f"  EXIT_THRESHOLD = {p['EXIT_THRESHOLD']}")
        print(f"  EXIT_CBBI = {p['EXIT_CBBI']}")
        print(f"\n  Full profit: {best['profit_pct']:.1f}%")
        print(f"  Stability score: {best['score']:.3f}")
        print(f"  Avg CV: {best['avg_cv']:.1f}%")

    print("\nDone!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
