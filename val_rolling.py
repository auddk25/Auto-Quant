"""val_rolling.py — Walk-forward rolling window validation.

Tests every active strategy across multiple consecutive train→validate windows.
Each window: train on earlier data, validate on the next period.
This tests robustness across different market regimes.

Usage: uv run val_rolling.py
"""

from __future__ import annotations
import sys, re
from pathlib import Path
from typing import Any
from freqtrade.configuration import Configuration
from freqtrade.enums import RunMode
from freqtrade.optimize.backtesting import Backtesting

PROJECT = Path(__file__).parent
USER_DATA = PROJECT / "user_data"
STRATEGIES = USER_DATA / "strategies"
CONFIG = PROJECT / "config.json"
DATA = USER_DATA / "data"

# Rolling windows: (train_range, validate_range, label)
# Each window trains on history, validates on the unseen next period
WINDOWS = [
    ("20220101-20221231", "20230101-20230630", "2023 H1 recovery"),
    ("20220101-20230630", "20230701-20231231", "2023 H2 rally start"),
    ("20220101-20231231", "20240101-20240630", "2024 H1 bull rally"),
    ("20220101-20240630", "20240701-20241231", "2024 H2 euphoria"),
    ("20220101-20241231", "20250101-20250630", "2025 H1 consolidation"),
    ("20220101-20250630", "20250701-20251231", "2025 H2 year-end"),
    ("20220101-20251231", "20260101-20260420", "2026 Q1 grind down"),
]

def discover() -> list[str]:
    return sorted([p.stem for p in STRATEGIES.glob("*.py") if not p.stem.startswith("_")])

def backtest(name: str, timerange: str) -> dict:
    args = {
        "config": [str(CONFIG)], "user_data_dir": str(USER_DATA),
        "datadir": str(DATA), "strategy": name,
        "strategy_path": str(STRATEGIES), "timerange": timerange,
        "export": "none", "exportfilename": None, "cache": "none",
    }
    config = Configuration(args, RunMode.BACKTEST).get_config()
    bt = Backtesting(config)
    bt.start()
    return bt.results

def parse_pct(results: dict, name: str) -> float:
    strat = results.get("strategy", {}).get(name, {})
    per_pair = strat.get("results_per_pair", []) or []
    for e in per_pair:
        if e.get("key") == "TOTAL":
            return float(e.get("profit_total_pct", 0))
    return 0.0

def main():
    strats = discover()
    if not strats:
        print("No strategies"); return 2
    print(f"Strategies: {', '.join(strats)}")
    print(f"Windows: {len(WINDOWS)}")
    print()

    # Header
    header = f"{'Strategy':<22}" + "".join(f"{w[2]:>16}" for w in WINDOWS) + f"{'Mean':>10}"
    print(header)
    print("-" * len(header))

    all_results = {}
    for name in strats:
        vals = []
        row = f"{name:<22}"
        for train_r, val_r, label in WINDOWS:
            try:
                r = backtest(name, val_r)
                pct = parse_pct(r, name)
                vals.append(pct)
                row += f"{pct:>15.2f}%"
            except Exception as e:
                row += f"{'ERR':>15}"
                vals.append(None)
        avg = sum(v for v in vals if v is not None) / sum(1 for v in vals if v is not None)
        row += f"{avg:>9.2f}%"
        all_results[name] = (vals, avg)
        print(row)

    # Summary
    print()
    print("=== 各窗口市场环境 ===")
    for train_r, val_r, label in WINDOWS:
        print(f"  {label}: train={train_r} → validate={val_r}")
    print()
    print("Mean = 平均值 (越高越稳定)")

if __name__ == "__main__":
    sys.exit(main())
