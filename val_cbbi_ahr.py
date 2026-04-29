"""val_cbbi_ahr.py — Validate CbbiAhr999Daily with best parameters.

Runs rolling window validation and OOS test for the top-3 parameter
combinations from fine screening.

Usage: uv run val_cbbi_ahr.py
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Any

# Fix Windows aiodns DNS resolution failure
import aiohttp.connector, aiohttp.resolver
aiohttp.connector.DefaultResolver = aiohttp.resolver.ThreadedResolver

from freqtrade.configuration import Configuration
from freqtrade.enums import RunMode
from freqtrade.optimize.backtesting import Backtesting

PROJECT = Path(__file__).parent
USER_DATA = PROJECT / "user_data"
STRATEGIES = USER_DATA / "strategies"
CONFIG = PROJECT / "config_daily.json"
DATA = USER_DATA / "data"

# Rolling windows
WINDOWS = [
    ("20220101-20221231", "20230101-20230630", "2023 H1"),
    ("20220101-20230630", "20230701-20231231", "2023 H2"),
    ("20220101-20231231", "20240101-20240630", "2024 H1"),
    ("20220101-20240630", "20240701-20241231", "2024 H2"),
    ("20220101-20241231", "20250101-20250630", "2025 H1"),
    ("20220101-20250630", "20250701-20251231", "2025 H2"),
    ("20220101-20251231", "20260101-20260420", "2026 Q1"),
]

# OOS window
OOS_RANGE = "20260101-20260420"

# Top-3 from fine screening
BEST_PARAMS = [
    {"label": "Top-1: N=3, AHR=1.3, CB=0.75",
     "params": {"ENTRY_MODE": "momentum", "EXIT_MODE": "high_estimate",
                "MOMENTUM_N": 3, "EXIT_CB": 0.75, "EXIT_AHR": 1.3}},
    {"label": "Top-2: N=7, AHR=1.3, CB=0.75",
     "params": {"ENTRY_MODE": "momentum", "EXIT_MODE": "high_estimate",
                "MOMENTUM_N": 7, "EXIT_CB": 0.75, "EXIT_AHR": 1.3}},
    {"label": "Top-3: N=7, AHR=1.1, CB=0.75",
     "params": {"ENTRY_MODE": "momentum", "EXIT_MODE": "high_estimate",
                "MOMENTUM_N": 7, "EXIT_CB": 0.75, "EXIT_AHR": 1.1}},
]


def run_backtest(params: dict, timerange: str) -> dict:
    args = {
        "config": [str(CONFIG)], "user_data_dir": str(USER_DATA),
        "datadir": str(DATA), "strategy": "CbbiAhr999Daily",
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
    strat = results.get("strategy", {}).get("CbbiAhr999Daily", {})
    per_pair = strat.get("results_per_pair", []) or []
    for e in per_pair:
        if e.get("key") == "BTC/USDT":
            return {
                "profit_pct": float(e.get("profit_total_pct", 0)),
                "trades": int(e.get("trades", 0)),
                "win_rate": float(e.get("winrate", 0)) * 100,
            }
    return {"profit_pct": 0, "trades": 0, "win_rate": 0}


def main():
    print("=== CbbiAhr999Daily Rolling Window Validation ===\n")

    for bp in BEST_PARAMS:
        print(f"\n{'='*60}")
        print(f"  {bp['label']}")
        print(f"{'='*60}")

        # Rolling windows
        profits = []
        header = f"{'Window':<16} {'Profit':>10} {'Trades':>8} {'Win%':>8}"
        print(header)
        print("-" * len(header))

        for train_r, val_r, label in WINDOWS:
            try:
                r = run_backtest(bp["params"], val_r)
                m = extract_metrics(r)
                profits.append(m["profit_pct"])
                print(f"{label:<16} {m['profit_pct']:>+9.1f}% {m['trades']:>8} {m['win_rate']:>7.0f}%")
            except Exception as e:
                profits.append(0)
                print(f"{label:<16} ERROR: {e}")

        mean_profit = sum(profits) / len(profits) if profits else 0
        print("-" * len(header))
        print(f"{'Mean':<16} {mean_profit:>+9.1f}%")

        # Full period backtest
        print(f"\n--- Full Period (2023-2025) ---")
        try:
            r = run_backtest(bp["params"], "20230101-20251231")
            m = extract_metrics(r)
            print(f"Profit: {m['profit_pct']:+.1f}%  Trades: {m['trades']}  Win%: {m['win_rate']:.0f}%")
        except Exception as e:
            print(f"ERROR: {e}")

    # Baseline comparison
    print(f"\n{'='*60}")
    print(f"  Baselines (from STRATEGY_MAP)")
    print(f"{'='*60}")
    print(f"  BuyAndHold:     +88.5%")
    print(f"  CbbiMomentum:   +732.7%  (14 trades, -2.9% DD)")
    print(f"  Bear01:         +107.7%  (15 trades, -18.2% DD)")
    print(f"  SmartHold:      +92.8%   (3 trades, -43.3% DD)")


if __name__ == "__main__":
    main()
