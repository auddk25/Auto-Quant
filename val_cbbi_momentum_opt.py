"""val_cbbi_momentum_opt.py — Rolling window validation for optimized CbbiMomentum.

Tests the optimized parameters across 7 time windows to check for overfitting.

Usage:
    uv run val_cbbi_momentum_opt.py
"""
from __future__ import annotations
import sys
from pathlib import Path

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

# Optimized parameters (R104 best)
OPTIMIZED_PARAMS = {
    "ENTRY_MOM": 3,
    "EXIT_MOM": 3,
    "CB_THRESHOLD": 0.65,
    "EXIT_THRESHOLD": -0.02,
    "EXIT_CBBI": 0.80,
}

# Rolling windows (7 segments)
WINDOWS = [
    ("2023H1", "20230101-20230701"),
    ("2023H2", "20230701-20240101"),
    ("2024H1", "20240101-20240701"),
    ("2024H2", "20240701-20250101"),
    ("2025H1", "20250101-20250701"),
    ("2025H2", "20250701-20260101"),
    ("2026Q1", "20260101-20260401"),
]


def run_backtest(params: dict, timerange: str) -> dict:
    """Run backtest with given params applied to strategy instance."""
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


def extract_metrics(results: dict, name: str) -> dict:
    strat = results.get("strategy", {}).get(name, {})
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


def main():
    print("=== CbbiMomentum Optimized — Rolling Window Validation ===\n")
    print(f"Parameters: {OPTIMIZED_PARAMS}\n")

    results = []
    for label, timerange in WINDOWS:
        try:
            bt_results = run_backtest(OPTIMIZED_PARAMS, timerange)
            metrics = extract_metrics(bt_results, "MtfTrendCbbiMomentumParam")
            results.append((label, metrics))
            print(f"{label}: profit={metrics['profit_pct']:.1f}% dd={metrics['max_dd_pct']:.1f}% "
                  f"trades={metrics['trades']} wr={metrics['win_rate']:.0f}% "
                  f"pf={metrics['profit_factor']:.2f}")
        except Exception as e:
            print(f"{label}: ERROR - {e}")
            results.append((label, {"profit_pct": 0, "max_dd_pct": 0, "trades": 0, "win_rate": 0, "profit_factor": 0, "sharpe": 0}))

    # Calculate statistics
    profits = [m["profit_pct"] for _, m in results if m["trades"] > 0]
    if profits:
        avg_profit = sum(profits) / len(profits)
        min_profit = min(profits)
        max_profit = max(profits)
        print(f"\n=== Summary ===")
        print(f"Windows with trades: {len(profits)}/{len(results)}")
        print(f"Average profit: {avg_profit:.1f}%")
        print(f"Min profit: {min_profit:.1f}%")
        print(f"Max profit: {max_profit:.1f}%")
        print(f"Std dev: {(sum((p - avg_profit) ** 2 for p in profits) / len(profits)) ** 0.5:.1f}%")

        # Compare with original CbbiMomentum rolling mean (+38.0%)
        original_mean = 38.0
        if avg_profit > original_mean:
            print(f"\n*** NEW BEST ROLLING MEAN: {avg_profit:.1f}% (vs {original_mean}%) ***")
        else:
            print(f"\n*** Original rolling mean: {original_mean}% ***")

        # Compare with BuyAndHold rolling mean (+27.3%)
        bah_mean = 27.3
        if avg_profit > bah_mean:
            print(f"*** Beats BuyAndHold rolling mean: {avg_profit:.1f}% > {bah_mean}% ***")


if __name__ == "__main__":
    main()
