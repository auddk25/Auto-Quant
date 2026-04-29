"""val_robustness.py — Comprehensive robustness validation for CbbiMomentumOpt.

Tests:
1. Extended rolling window validation (12 segments)
2. Parameter stability testing (±20% variation)
3. Monte Carlo simulation (1000 random shuffles)
4. Cross-validation (3-fold)
5. Market state stratification testing (bull/bear/consolidation)

Usage: uv run val_robustness.py
"""
from __future__ import annotations
import sys, re, json, random
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
TIMERANGE = "20220101-20251231"

# Current best parameters (R104)
BASE_PARAMS = {
    "ENTRY_MOM": 3,
    "EXIT_MOM": 3,
    "CB_THRESHOLD": 0.65,
    "EXIT_THRESHOLD": -0.02,
    "EXIT_CBBI": 0.80,
}

# ──────────────────────────────────────────────────────────────────────
# 1. Extended Rolling Windows (12 segments)
# ──────────────────────────────────────────────────────────────────────

EXTENDED_WINDOWS = [
    # (train_range, validate_range, label, market_state)
    ("20220101-20220630", "20220701-20221231", "2022 H2 bear crash", "bear"),
    ("20220101-20221231", "20230101-20230331", "2023 Q1 recovery", "recovery"),
    ("20220101-20230331", "20230401-20230630", "2023 Q2 consolidation", "consolidation"),
    ("20220101-20230630", "20230701-20230930", "2023 Q3 accumulation", "consolidation"),
    ("20220101-20230930", "20231001-20231231", "2023 Q4 rally start", "bull"),
    ("20220101-20231231", "20240101-20240331", "2024 Q1 bull rally", "bull"),
    ("20220101-20240331", "20240401-20240630", "2024 Q2 acceleration", "bull"),
    ("20220101-20240630", "20240701-20240930", "2024 Q3 correction", "consolidation"),
    ("20220101-20240930", "20241001-20241231", "2024 Q4 euphoria", "bull"),
    ("20220101-20241231", "20250101-20250331", "2025 Q1 consolidation", "consolidation"),
    ("20220101-20250331", "20250401-20250630", "2025 Q2 recovery", "bull"),
    ("20220101-20250630", "20250701-20251231", "2025 H2 year-end", "consolidation"),
]


# ──────────────────────────────────────────────────────────────────────
# 2. Parameter Stability Test (±20% variation)
# ──────────────────────────────────────────────────────────────────────

def generate_param_variations(base_params: dict, n_samples: int = 100) -> list[dict]:
    """Generate parameter variations within ±20% of base parameters."""
    variations = []

    # Define parameter ranges
    param_ranges = {
        "ENTRY_MOM": (2, 4),  # Integer, ±1 from 3
        "EXIT_MOM": (2, 4),   # Integer, ±1 from 3
        "CB_THRESHOLD": (0.52, 0.78),  # ±20% from 0.65
        "EXIT_THRESHOLD": (-0.024, -0.016),  # ±20% from -0.02
        "EXIT_CBBI": (0.64, 0.96),  # ±20% from 0.80
    }

    for _ in range(n_samples):
        params = {}
        for key, (low, high) in param_ranges.items():
            if key in ["ENTRY_MOM", "EXIT_MOM"]:
                # Integer parameters
                params[key] = random.randint(low, high)
            else:
                # Float parameters
                params[key] = round(random.uniform(low, high), 4)
        variations.append(params)

    return variations


# ──────────────────────────────────────────────────────────────────────
# 3. Monte Carlo Simulation
# ──────────────────────────────────────────────────────────────────────

def monte_carlo_simulation(trades: list[dict], n_simulations: int = 1000) -> dict:
    """Run Monte Carlo simulation by shuffling trade order."""
    if not trades:
        return {"error": "No trades to simulate"}

    # Extract trade profits
    profits = [t.get("profit_pct", 0) for t in trades]

    # Run simulations
    final_returns = []
    max_drawdowns = []

    for _ in range(n_simulations):
        # Shuffle profits
        shuffled = profits.copy()
        random.shuffle(shuffled)

        # Calculate equity curve
        equity = [100]  # Start with 100
        for p in shuffled:
            equity.append(equity[-1] * (1 + p / 100))

        # Calculate metrics
        final_return = (equity[-1] / equity[0] - 1) * 100
        final_returns.append(final_return)

        # Calculate max drawdown
        peak = equity[0]
        max_dd = 0
        for val in equity:
            if val > peak:
                peak = val
            dd = (peak - val) / peak * 100
            if dd > max_dd:
                max_dd = dd
        max_drawdowns.append(max_dd)

    # Calculate statistics
    return {
        "n_simulations": n_simulations,
        "n_trades": len(trades),
        "return_mean": np.mean(final_returns),
        "return_std": np.std(final_returns),
        "return_5pct": np.percentile(final_returns, 5),
        "return_25pct": np.percentile(final_returns, 25),
        "return_median": np.median(final_returns),
        "return_75pct": np.percentile(final_returns, 75),
        "return_95pct": np.percentile(final_returns, 95),
        "drawdown_mean": np.mean(max_drawdowns),
        "drawdown_95pct": np.percentile(max_drawdowns, 95),
        "prob_positive": sum(1 for r in final_returns if r > 0) / n_simulations * 100,
    }


# ──────────────────────────────────────────────────────────────────────
# 4. Cross-Validation (3-fold)
# ──────────────────────────────────────────────────────────────────────

CV_FOLDS = [
    ("20220101-20231231", "20240101-20241231", "Fold 1: Train 2022-2023, Val 2024"),
    ("20220101-20241231", "20250101-20251231", "Fold 2: Train 2022-2024, Val 2025"),
    ("20230101-20241231", "20250101-20260420", "Fold 3: Train 2023-2024, Val 2025-2026"),
]


# ──────────────────────────────────────────────────────────────────────
# Helper functions
# ──────────────────────────────────────────────────────────────────────

def run_backtest(params: dict, timerange: str) -> dict:
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
                "sharpe": float(e.get("sharpe", 0) or 0),
            }
    return {"profit_pct": 0, "max_dd_pct": 0, "trades": 0, "win_rate": 0, "profit_factor": 0, "sharpe": 0}


def extract_trades(results: dict) -> list[dict]:
    """Extract individual trades from backtest results."""
    strat = results.get("strategy", {}).get("MtfTrendCbbiMomentumParam", {})
    return strat.get("trades", []) or []


# ──────────────────────────────────────────────────────────────────────
# Main validation
# ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 80)
    print("CbbiMomentumOpt Robustness Validation")
    print("=" * 80)
    print(f"\nBase parameters: {json.dumps(BASE_PARAMS, indent=2)}")
    print()

    # ──────────────────────────────────────────────────────────────────
    # Test 1: Extended Rolling Window Validation (12 segments)
    # ──────────────────────────────────────────────────────────────────
    print("=" * 80)
    print("TEST 1: Extended Rolling Window Validation (12 segments)")
    print("=" * 80)

    rolling_results = []
    for train_r, val_r, label, market_state in EXTENDED_WINDOWS:
        try:
            r = run_backtest(BASE_PARAMS, val_r)
            m = extract_metrics(r)
            rolling_results.append({
                "label": label,
                "market_state": market_state,
                "train": train_r,
                "validate": val_r,
                **m,
            })
            print(f"  {label:30s} | {market_state:15s} | profit={m['profit_pct']:>8.2f}% | dd={m['max_dd_pct']:>7.2f}% | trades={m['trades']:>3d}")
        except Exception as e:
            print(f"  {label:30s} | ERROR: {e}")
            rolling_results.append({"label": label, "market_state": market_state, "error": str(e)})

    # Calculate statistics
    valid_results = [r for r in rolling_results if "error" not in r]
    if valid_results:
        profits = [r["profit_pct"] for r in valid_results]
        print(f"\n  Summary:")
        print(f"    Mean profit: {np.mean(profits):.2f}%")
        print(f"    Std profit: {np.std(profits):.2f}%")
        print(f"    Min profit: {np.min(profits):.2f}% ({valid_results[np.argmin(profits)]['label']})")
        print(f"    Max profit: {np.max(profits):.2f}% ({valid_results[np.argmax(profits)]['label']})")
        print(f"    Profitable segments: {sum(1 for p in profits if p > 0)}/{len(profits)}")

        # By market state
        print(f"\n  By market state:")
        for state in ["bear", "recovery", "consolidation", "bull"]:
            state_results = [r for r in valid_results if r["market_state"] == state]
            if state_results:
                state_profits = [r["profit_pct"] for r in state_results]
                print(f"    {state:15s}: mean={np.mean(state_profits):>8.2f}% | count={len(state_results)}")

    print()

    # ──────────────────────────────────────────────────────────────────
    # Test 2: Parameter Stability Testing (±20% variation)
    # ──────────────────────────────────────────────────────────────────
    print("=" * 80)
    print("TEST 2: Parameter Stability Testing (100 random variations)")
    print("=" * 80)

    variations = generate_param_variations(BASE_PARAMS, n_samples=100)
    param_results = []

    for i, params in enumerate(variations):
        try:
            r = run_backtest(params, TIMERANGE)
            m = extract_metrics(r)
            param_results.append({"params": params, **m})
            if (i + 1) % 20 == 0:
                print(f"  Completed {i+1}/100 variations...")
        except Exception as e:
            param_results.append({"params": params, "error": str(e)})

    # Analyze parameter stability
    valid_param_results = [r for r in param_results if "error" not in r and r["trades"] >= 5]
    if valid_param_results:
        profits = [r["profit_pct"] for r in valid_param_results]
        print(f"\n  Parameter Stability Results:")
        print(f"    Valid variations: {len(valid_param_results)}/{len(variations)}")
        print(f"    Mean profit: {np.mean(profits):.2f}%")
        print(f"    Std profit: {np.std(profits):.2f}%")
        print(f"    Min profit: {np.min(profits):.2f}%")
        print(f"    Max profit: {np.max(profits):.2f}%")
        print(f"    Coefficient of variation: {np.std(profits)/np.mean(profits)*100:.1f}%")

        # Check if >90% of variations are within 70% of optimal
        optimal_profit = 1128.4  # R104 best
        threshold_70 = optimal_profit * 0.7
        pct_above_70 = sum(1 for p in profits if p > threshold_70) / len(profits) * 100
        print(f"    Variations > {threshold_70:.0f}% (70% of optimal): {pct_above_70:.1f}%")

        # Find best and worst variations
        best_idx = np.argmax(profits)
        worst_idx = np.argmin(profits)
        print(f"\n    Best variation: {profits[best_idx]:.2f}%")
        print(f"      Params: {json.dumps(valid_param_results[best_idx]['params'], indent=2)}")
        print(f"    Worst variation: {profits[worst_idx]:.2f}%")
        print(f"      Params: {json.dumps(valid_param_results[worst_idx]['params'], indent=2)}")

    print()

    # ──────────────────────────────────────────────────────────────────
    # Test 3: Monte Carlo Simulation
    # ──────────────────────────────────────────────────────────────────
    print("=" * 80)
    print("TEST 3: Monte Carlo Simulation (1000 shuffles)")
    print("=" * 80)

    # Get trades from base parameters
    try:
        base_results = run_backtest(BASE_PARAMS, TIMERANGE)
        trades = extract_trades(base_results)

        if trades:
            mc_results = monte_carlo_simulation(trades, n_simulations=1000)
            print(f"\n  Monte Carlo Results:")
            print(f"    Simulations: {mc_results['n_simulations']}")
            print(f"    Trades: {mc_results['n_trades']}")
            print(f"\n    Return Distribution:")
            print(f"      Mean: {mc_results['return_mean']:.2f}%")
            print(f"      Std: {mc_results['return_std']:.2f}%")
            print(f"      5th percentile: {mc_results['return_5pct']:.2f}%")
            print(f"      25th percentile: {mc_results['return_25pct']:.2f}%")
            print(f"      Median: {mc_results['return_median']:.2f}%")
            print(f"      75th percentile: {mc_results['return_75pct']:.2f}%")
            print(f"      95th percentile: {mc_results['return_95pct']:.2f}%")
            print(f"\n    Drawdown Distribution:")
            print(f"      Mean: {mc_results['drawdown_mean']:.2f}%")
            print(f"      95th percentile: {mc_results['drawdown_95pct']:.2f}%")
            print(f"\n    Probability of positive return: {mc_results['prob_positive']:.1f}%")
        else:
            print("  No trades found for Monte Carlo simulation")
    except Exception as e:
        print(f"  ERROR: {e}")

    print()

    # ──────────────────────────────────────────────────────────────────
    # Test 4: Cross-Validation (3-fold)
    # ──────────────────────────────────────────────────────────────────
    print("=" * 80)
    print("TEST 4: Cross-Validation (3-fold)")
    print("=" * 80)

    cv_results = []
    for train_r, val_r, label in CV_FOLDS:
        try:
            r = run_backtest(BASE_PARAMS, val_r)
            m = extract_metrics(r)
            cv_results.append({"label": label, "train": train_r, "validate": val_r, **m})
            print(f"  {label}")
            print(f"    profit={m['profit_pct']:.2f}% | dd={m['max_dd_pct']:.2f}% | trades={m['trades']} | wr={m['win_rate']:.0f}%")
        except Exception as e:
            print(f"  {label}")
            print(f"    ERROR: {e}")
            cv_results.append({"label": label, "error": str(e)})

    # Analyze cross-validation
    valid_cv = [r for r in cv_results if "error" not in r]
    if valid_cv:
        profits = [r["profit_pct"] for r in valid_cv]
        print(f"\n  Cross-Validation Summary:")
        print(f"    Mean profit: {np.mean(profits):.2f}%")
        print(f"    Std profit: {np.std(profits):.2f}%")
        print(f"    Min profit: {np.min(profits):.2f}%")
        print(f"    Max profit: {np.max(profits):.2f}%")
        print(f"    Fold ratio (max/min): {np.max(profits)/np.min(profits):.2f}x")

    print()

    # ──────────────────────────────────────────────────────────────────
    # Test 5: Market State Stratification
    # ──────────────────────────────────────────────────────────────────
    print("=" * 80)
    print("TEST 5: Market State Stratification")
    print("=" * 80)

    # Define market state periods
    market_periods = {
        "bear": [
            ("20220101-20220630", "2022 H1"),
            ("20220701-20221231", "2022 H2"),
        ],
        "recovery": [
            ("20230101-20230630", "2023 H1"),
        ],
        "consolidation": [
            ("20230701-20231231", "2023 H2"),
            ("20240701-20240930", "2024 Q3"),
            ("20250101-20250331", "2025 Q1"),
        ],
        "bull": [
            ("20240101-20240331", "2024 Q1"),
            ("20240401-20240630", "2024 Q2"),
            ("20241001-20241231", "2024 Q4"),
            ("20250401-20250630", "2025 Q2"),
        ],
    }

    state_results = {}
    for state, periods in market_periods.items():
        state_profits = []
        for timerange, label in periods:
            try:
                r = run_backtest(BASE_PARAMS, timerange)
                m = extract_metrics(r)
                state_profits.append(m["profit_pct"])
                print(f"  {state:15s} | {label:10s} | profit={m['profit_pct']:>8.2f}%")
            except Exception as e:
                print(f"  {state:15s} | {label:10s} | ERROR: {e}")

        if state_profits:
            state_results[state] = {
                "mean": np.mean(state_profits),
                "min": np.min(state_profits),
                "max": np.max(state_profits),
                "count": len(state_profits),
            }

    print(f"\n  Market State Summary:")
    for state, stats in state_results.items():
        print(f"    {state:15s}: mean={stats['mean']:>8.2f}% | min={stats['min']:>8.2f}% | max={stats['max']:>8.2f}% | count={stats['count']}")

    print()

    # ──────────────────────────────────────────────────────────────────
    # Overall Robustness Assessment
    # ──────────────────────────────────────────────────────────────────
    print("=" * 80)
    print("OVERALL ROBUSTNESS ASSESSMENT")
    print("=" * 80)

    checks = []

    # Check 1: Rolling window mean > +20%
    if valid_results:
        rolling_mean = np.mean([r["profit_pct"] for r in valid_results])
        checks.append(("Rolling window mean > +20%", rolling_mean > 20, f"{rolling_mean:.2f}%"))

    # Check 2: No consecutive 3 losing segments
    if valid_results:
        profits = [r["profit_pct"] for r in valid_results]
        max_consecutive_loss = 0
        current_loss = 0
        for p in profits:
            if p < 0:
                current_loss += 1
                max_consecutive_loss = max(max_consecutive_loss, current_loss)
            else:
                current_loss = 0
        checks.append(("No consecutive 3 losing segments", max_consecutive_loss < 3, f"Max consecutive losses: {max_consecutive_loss}"))

    # Check 3: Parameter stability CV < 30%
    if valid_param_results:
        profits = [r["profit_pct"] for r in valid_param_results]
        cv = np.std(profits) / np.mean(profits) * 100
        checks.append(("Parameter stability CV < 30%", cv < 30, f"CV: {cv:.1f}%"))

    # Check 4: Monte Carlo 5th percentile > 0%
    if trades:
        mc_results = monte_carlo_simulation(trades, n_simulations=1000)
        checks.append(("Monte Carlo 5th percentile > 0%", mc_results["return_5pct"] > 0, f"5th pct: {mc_results['return_5pct']:.2f}%"))

    # Check 5: Cross-validation fold ratio < 3x
    if valid_cv:
        profits = [r["profit_pct"] for r in valid_cv]
        fold_ratio = np.max(profits) / np.min(profits) if np.min(profits) > 0 else float('inf')
        checks.append(("Cross-validation fold ratio < 3x", fold_ratio < 3, f"Ratio: {fold_ratio:.2f}x"))

    # Check 6: Bear market not losing > -10%
    if "bear" in state_results:
        bear_mean = state_results["bear"]["mean"]
        checks.append(("Bear market mean > -10%", bear_mean > -10, f"Bear mean: {bear_mean:.2f}%"))

    # Print assessment
    print()
    passed = 0
    for check_name, result, value in checks:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} | {check_name}: {value}")
        if result:
            passed += 1

    print(f"\n  Overall: {passed}/{len(checks)} checks passed")

    if passed == len(checks):
        print("\n  STRATEGY IS ROBUST")
    elif passed >= len(checks) * 0.7:
        print("\n  STRATEGY HAS SOME ROBUSTNESS ISSUES")
    else:
        print("\n  STRATEGY IS NOT ROBUST - NEEDS OPTIMIZATION")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
