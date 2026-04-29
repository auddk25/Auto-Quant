"""optimize_stability.py — Parameter stability optimization for CbbiMomentumOpt.

Goal: Find parameter region where returns are stable (CV < 30%)
Method: Grid search + stability analysis

Usage: uv run optimize_stability.py
"""
from __future__ import annotations
import sys, json, random
from pathlib import Path
from typing import Any
import numpy as np

# Fix Windows aiodns DNS resolution failure
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

# Parameter grid for stability search
PARAM_GRID = {
    "ENTRY_MOM": [2, 3, 4],
    "EXIT_MOM": [2, 3, 4],
    "CB_THRESHOLD": [0.55, 0.60, 0.65, 0.70, 0.75],
    "EXIT_THRESHOLD": [-0.025, -0.020, -0.015, -0.010],
    "EXIT_CBBI": [0.70, 0.75, 0.80, 0.85],
}


def run_backtest(params: dict) -> dict:
    """Run backtest with given params."""
    args = {
        "config": [str(CONFIG)], "user_data_dir": str(USER_DATA),
        "datadir": str(DATA), "strategy": "MtfTrendCbbiMomentumParam",
        "strategy_path": str(STRATEGIES), "timerange": TIMERANGE,
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
                "sharpe": float(e.get("sharpe", 0) or 0),
            }
    return {"profit_pct": 0, "max_dd_pct": 0, "trades": 0, "win_rate": 0, "profit_factor": 0, "sharpe": 0}


def analyze_stability(results: list[dict]) -> dict:
    """Analyze parameter stability across results."""
    if not results:
        return {}

    profits = [r["profit_pct"] for r in results]
    trades = [r["trades"] for r in results]

    return {
        "count": len(results),
        "profit_mean": np.mean(profits),
        "profit_std": np.std(profits),
        "profit_cv": np.std(profits) / np.mean(profits) * 100 if np.mean(profits) > 0 else 0,
        "profit_min": np.min(profits),
        "profit_max": np.max(profits),
        "profit_median": np.median(profits),
        "trades_mean": np.mean(trades),
        "pct_above_800": sum(1 for p in profits if p > 800) / len(profits) * 100,
    }


def main():
    print("=" * 80)
    print("Parameter Stability Optimization")
    print("=" * 80)
    print(f"\nTimerange: {TIMERANGE}")
    print(f"Parameter grid: {json.dumps(PARAM_GRID, indent=2)}")

    # Generate all combinations
    combos = []
    for entry_mom in PARAM_GRID["ENTRY_MOM"]:
        for exit_mom in PARAM_GRID["EXIT_MOM"]:
            for cb_threshold in PARAM_GRID["CB_THRESHOLD"]:
                for exit_threshold in PARAM_GRID["EXIT_THRESHOLD"]:
                    for exit_cbbi in PARAM_GRID["EXIT_CBBI"]:
                        combos.append({
                            "ENTRY_MOM": entry_mom,
                            "EXIT_MOM": exit_mom,
                            "CB_THRESHOLD": cb_threshold,
                            "EXIT_THRESHOLD": exit_threshold,
                            "EXIT_CBBI": exit_cbbi,
                        })

    print(f"\nTotal combinations: {len(combos)}")
    print("\nRunning backtests...")

    # Run all backtests
    all_results = []
    for i, params in enumerate(combos):
        try:
            r = run_backtest(params)
            m = extract_metrics(r)
            all_results.append({"params": params, **m})
            if (i + 1) % 50 == 0:
                print(f"  Completed {i+1}/{len(combos)}...")
        except Exception as e:
            all_results.append({"params": params, "error": str(e)})

    # Filter valid results
    valid_results = [r for r in all_results if "error" not in r and r["trades"] >= 5]
    print(f"\nValid results: {len(valid_results)}/{len(all_results)}")

    # Group by EXIT_THRESHOLD (the most sensitive parameter)
    print("\n" + "=" * 80)
    print("Analysis by EXIT_THRESHOLD")
    print("=" * 80)

    threshold_groups = {}
    for r in valid_results:
        threshold = r["params"]["EXIT_THRESHOLD"]
        if threshold not in threshold_groups:
            threshold_groups[threshold] = []
        threshold_groups[threshold].append(r)

    for threshold, group in sorted(threshold_groups.items()):
        stability = analyze_stability(group)
        print(f"\nEXIT_THRESHOLD = {threshold}:")
        print(f"  Count: {stability['count']}")
        print(f"  Profit: {stability['profit_mean']:.1f}% ± {stability['profit_std']:.1f}% (CV: {stability['profit_cv']:.1f}%)")
        print(f"  Range: [{stability['profit_min']:.1f}%, {stability['profit_max']:.1f}%]")
        print(f"  Trades: {stability['trades_mean']:.1f}")
        print(f"  >800%: {stability['pct_above_800']:.1f}%")

    # Group by CB_THRESHOLD
    print("\n" + "=" * 80)
    print("Analysis by CB_THRESHOLD")
    print("=" * 80)

    cb_groups = {}
    for r in valid_results:
        cb = r["params"]["CB_THRESHOLD"]
        if cb not in cb_groups:
            cb_groups[cb] = []
        cb_groups[cb].append(r)

    for cb, group in sorted(cb_groups.items()):
        stability = analyze_stability(group)
        print(f"\nCB_THRESHOLD = {cb}:")
        print(f"  Count: {stability['count']}")
        print(f"  Profit: {stability['profit_mean']:.1f}% ± {stability['profit_std']:.1f}% (CV: {stability['profit_cv']:.1f}%)")
        print(f"  Range: [{stability['profit_min']:.1f}%, {stability['profit_max']:.1f}%]")
        print(f"  Trades: {stability['trades_mean']:.1f}")
        print(f"  >800%: {stability['pct_above_800']:.1f}%")

    # Find stable regions (CV < 30%)
    print("\n" + "=" * 80)
    print("Stable Regions (CV < 30%)")
    print("=" * 80)

    # Group by parameter combinations
    param_groups = {}
    for r in valid_results:
        key = (r["params"]["ENTRY_MOM"], r["params"]["EXIT_MOM"])
        if key not in param_groups:
            param_groups[key] = []
        param_groups[key].append(r)

    stable_regions = []
    for (entry, exit), group in param_groups.items():
        stability = analyze_stability(group)
        if stability["profit_cv"] < 30 and stability["profit_mean"] > 500:
            stable_regions.append({
                "entry_mom": entry,
                "exit_mom": exit,
                **stability,
            })

    stable_regions.sort(key=lambda x: x["profit_mean"], reverse=True)

    if stable_regions:
        print(f"\nFound {len(stable_regions)} stable regions:")
        for i, region in enumerate(stable_regions[:10]):
            print(f"\n#{i+1}: ENTRY_MOM={region['entry_mom']}, EXIT_MOM={region['exit_mom']}")
            print(f"  Profit: {region['profit_mean']:.1f}% ± {region['profit_std']:.1f}% (CV: {region['profit_cv']:.1f}%)")
            print(f"  Range: [{region['profit_min']:.1f}%, {region['profit_max']:.1f}%]")
            print(f"  Trades: {region['trades_mean']:.1f}")
            print(f"  >800%: {region['pct_above_800']:.1f}%")
    else:
        print("\nNo stable regions found with CV < 30% and profit > 500%")
        print("Trying relaxed criteria (CV < 40% and profit > 400%)...")

        for (entry, exit), group in param_groups.items():
            stability = analyze_stability(group)
            if stability["profit_cv"] < 40 and stability["profit_mean"] > 400:
                stable_regions.append({
                    "entry_mom": entry,
                    "exit_mom": exit,
                    **stability,
                })

        stable_regions.sort(key=lambda x: x["profit_mean"], reverse=True)

        if stable_regions:
            print(f"\nFound {len(stable_regions)} stable regions (relaxed):")
            for i, region in enumerate(stable_regions[:10]):
                print(f"\n#{i+1}: ENTRY_MOM={region['entry_mom']}, EXIT_MOM={region['exit_mom']}")
                print(f"  Profit: {region['profit_mean']:.1f}% ± {region['profit_std']:.1f}% (CV: {region['profit_cv']:.1f}%)")
                print(f"  Range: [{region['profit_min']:.1f}%, {region['profit_max']:.1f}%]")
                print(f"  Trades: {region['trades_mean']:.1f}")
                print(f"  >800%: {region['pct_above_800']:.1f}%")

    # Find best overall parameters
    print("\n" + "=" * 80)
    print("Top 20 Parameter Combinations")
    print("=" * 80)

    valid_results.sort(key=lambda x: x["profit_pct"], reverse=True)

    for i, r in enumerate(valid_results[:20]):
        print(f"\n#{i+1}: profit={r['profit_pct']:.1f}% dd={r['max_dd_pct']:.1f}% trades={r['trades']} wr={r['win_rate']:.0f}%")
        print(f"  Params: {json.dumps(r['params'])}")

    # Find parameters that are both high and stable
    print("\n" + "=" * 80)
    print("Recommended Parameters (High + Stable)")
    print("=" * 80)

    # Filter for high returns and reasonable stability
    high_stable = [r for r in valid_results if r["profit_pct"] > 800]

    if high_stable:
        # Group by similar parameter sets
        param_sets = {}
        for r in high_stable:
            # Create a key based on the most important parameters
            key = (r["params"]["EXIT_THRESHOLD"], r["params"]["CB_THRESHOLD"])
            if key not in param_sets:
                param_sets[key] = []
            param_sets[key].append(r)

        # Find the most stable high-return region
        best_region = None
        best_score = 0

        for (exit_thresh, cb_thresh), group in param_sets.items():
            if len(group) >= 3:  # Need at least 3 samples
                stability = analyze_stability(group)
                # Score = mean profit / CV (higher is better)
                if stability["profit_cv"] > 0:
                    score = stability["profit_mean"] / stability["profit_cv"]
                    if score > best_score:
                        best_score = score
                        best_region = {
                            "exit_threshold": exit_thresh,
                            "cb_threshold": cb_thresh,
                            "score": score,
                            **stability,
                            "samples": group[:5],  # Keep top 5 samples
                        }

        if best_region:
            print(f"\nBest stable region:")
            print(f"  EXIT_THRESHOLD: {best_region['exit_threshold']}")
            print(f"  CB_THRESHOLD: {best_region['cb_threshold']}")
            print(f"  Score: {best_region['score']:.2f}")
            print(f"  Profit: {best_region['profit_mean']:.1f}% ± {best_region['profit_std']:.1f}% (CV: {best_region['profit_cv']:.1f}%)")
            print(f"  Range: [{best_region['profit_min']:.1f}%, {best_region['profit_max']:.1f}%]")
            print(f"  Trades: {best_region['trades_mean']:.1f}")

            print(f"\n  Top samples from this region:")
            for i, sample in enumerate(best_region["samples"]):
                print(f"    #{i+1}: profit={sample['profit_pct']:.1f}% trades={sample['trades']}")
                print(f"      Params: {json.dumps(sample['params'])}")

    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)

    print(f"\nTotal combinations tested: {len(combos)}")
    print(f"Valid results (trades >= 5): {len(valid_results)}")
    print(f"Results > 800%: {sum(1 for r in valid_results if r['profit_pct'] > 800)}")
    print(f"Results > 1000%: {sum(1 for r in valid_results if r['profit_pct'] > 1000)}")

    if stable_regions:
        print(f"\nStable regions found: {len(stable_regions)}")
        print(f"Best stable profit: {stable_regions[0]['profit_mean']:.1f}% (CV: {stable_regions[0]['profit_cv']:.1f}%)")
    else:
        print("\nNo stable regions found")

    print("\nDone!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
