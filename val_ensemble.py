"""val_ensemble.py — Rolling window validation for ensemble strategy."""
from __future__ import annotations
import sys
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

WINDOWS = [
    ("2022-07-01", "2022-12-31", "2022 H2"),
    ("2023-01-01", "2023-03-31", "2023 Q1"),
    ("2023-04-01", "2023-06-30", "2023 Q2"),
    ("2023-07-01", "2023-09-30", "2023 Q3"),
    ("2023-10-01", "2023-12-31", "2023 Q4"),
    ("2024-01-01", "2024-03-31", "2024 Q1"),
    ("2024-04-01", "2024-06-30", "2024 Q2"),
    ("2024-07-01", "2024-09-30", "2024 Q3"),
    ("2024-10-01", "2024-12-31", "2024 Q4"),
    ("2025-01-01", "2025-03-31", "2025 Q1"),
    ("2025-04-01", "2025-06-30", "2025 Q2"),
    ("2025-07-01", "2025-12-31", "2025 H2"),
]


def run_backtest(timerange: str):
    args = {
        "config": [str(CONFIG)], "user_data_dir": str(USER_DATA),
        "datadir": str(DATA), "strategy": "MtfTrendCbbiMomentumEnsemble",
        "strategy_path": str(STRATEGIES), "timerange": timerange,
        "export": "none", "exportfilename": None, "cache": "none",
    }
    config = Configuration(args, RunMode.BACKTEST).get_config()
    bt = Backtesting(config)
    bt.start()
    results = bt.results
    strat = results.get("strategy", {}).get("MtfTrendCbbiMomentumEnsemble", {})
    per_pair = strat.get("results_per_pair", []) or []
    for e in per_pair:
        if e.get("key") == "BTC/USDT":
            return {
                "profit": float(e.get("profit_total_pct", 0)),
                "trades": int(e.get("trades", 0)),
                "win_rate": float(e.get("winrate", 0)) * 100,
            }
    return {"profit": 0, "trades": 0, "win_rate": 0}


def main():
    print("=" * 70)
    print("Ensemble Strategy Rolling Window Validation")
    print("=" * 70)
    print(f"Strategy: MtfTrendCbbiMomentumEnsemble")
    print(f"Variants: EXIT_THRESHOLD = [-0.020, -0.018, -0.015]")
    print(f"Vote threshold: >= 2/3\n")

    results = []
    for start, end, label in WINDOWS:
        tr = f"{start.replace('-','')}-{end.replace('-','')}"
        try:
            r = run_backtest(tr)
            results.append({"window": label, **r})
            status = f"{r['profit']:+.1f}%" if r['trades'] > 0 else "NO TRADE"
            print(f"  {label}: {status} (trades={r['trades']})")
        except Exception as e:
            results.append({"window": label, "error": str(e)})
            print(f"  {label}: ERROR")

    valid = [r for r in results if "error" not in r]
    profits = [r["profit"] for r in valid if r["trades"] > 0]
    all_trades = sum(r["trades"] for r in valid)

    print(f"\n{'='*70}")
    print("Summary")
    print(f"{'='*70}")
    print(f"Windows: {len(valid)}")
    print(f"Windows with trades: {len(profits)}")
    print(f"Total trades: {all_trades}")
    if profits:
        print(f"Mean profit: {np.mean(profits):.1f}%")
        print(f"Median profit: {np.median(profits):.1f}%")
        print(f"Std: {np.std(profits):.1f}%")
        print(f"Min: {min(profits):.1f}%")
        print(f"Max: {max(profits):.1f}%")
        print(f"Losing windows: {sum(1 for p in profits if p < 0)}")
    print(f"No-trade windows: {sum(1 for r in valid if r['trades'] == 0)}")

    # Compare with single variant (EXIT=-0.02)
    print(f"\nComparison with single variant (EXIT=-0.02, CB=0.65):")
    print(f"  Ensemble mean: {np.mean(profits):.1f}%")
    print(f"  Single variant mean: 17.7%")
    print(f"  Ensemble trades: {all_trades}")
    print(f"  Single variant trades: 25")

    return 0


if __name__ == "__main__":
    sys.exit(main())
