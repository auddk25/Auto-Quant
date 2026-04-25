"""
val.py — OOS validation runner.

Runs active strategies against a validation window outside the training timerange.
Supports custom data directory via VAL_DATA_DIR env var.

Prerequisites:
    uv run prepare.py (base data)
    uv run prepare_cbbi.py (CBBI for cycle strategies)
    uv run prepare_ahr999.py (AHR999 for cycle strategies)

Usage:
    uv run val.py [timerange]  # default: 20260101-20260420
"""
from __future__ import annotations

import sys
import traceback
from os import environ
from pathlib import Path
from typing import Any
import pandas as pd
import shutil

from freqtrade.configuration import Configuration
from freqtrade.enums import RunMode
from freqtrade.optimize.backtesting import Backtesting

PROJECT_DIR = Path(__file__).parent.resolve()
USER_DATA = PROJECT_DIR / "user_data"
STRATEGIES_DIR = USER_DATA / "strategies"
CONFIG = PROJECT_DIR / "config.json"
PAIRS = ["BTC/USDT", "ETH/USDT"]
PAIRS_STR = ",".join(PAIRS)


def discover_strategies() -> list[str]:
    if not STRATEGIES_DIR.exists():
        return []
    names = []
    for path in sorted(STRATEGIES_DIR.glob("*.py")):
        if path.stem.startswith("_"):
            continue
        names.append(path.stem)
    return names


def run_val(key: str, timerange: str, datadir: Path) -> dict[str, Any]:
    args = {
        "config": [str(CONFIG)],
        "user_data_dir": str(USER_DATA),
        "datadir": str(datadir),
        "strategy": key,
        "strategy_path": str(STRATEGIES_DIR),
        "timerange": timerange,
        "export": "none",
        "exportfilename": None,
        "cache": "none",
    }
    config = Configuration(args, RunMode.BACKTEST).get_config()
    bt = Backtesting(config)
    bt.start()
    return bt.results


def _merge_train_into_val(train_dir: Path, val_dir: Path, tail_days: int = 300) -> None:
    """Copy tail of training data into val dir so long-lookback indicators work."""
    for tf in ["1d", "4h", "1h"]:
        for pair in ["BTC_USDT", "ETH_USDT"]:
            train_file = train_dir / f"{pair}-{tf}.feather"
            val_file = val_dir / f"{pair}-{tf}.feather"
            if not train_file.exists():
                continue
            train_df = pd.read_feather(train_file)
            train_df["date"] = pd.to_datetime(train_df["date"])
            tail = train_df[train_df["date"] >= train_df["date"].max() - pd.Timedelta(days=tail_days)]
            if val_file.exists():
                val_df = pd.read_feather(val_file)
                val_df["date"] = pd.to_datetime(val_df["date"])
                merged = pd.concat([tail, val_df], ignore_index=True)
                merged = merged.drop_duplicates(subset=["date"]).sort_values("date")
            else:
                merged = tail
            merged.reset_index(drop=True).to_feather(str(val_file))


def main() -> int:
    timerange = sys.argv[1] if len(sys.argv) > 1 else "20260101-20260420"
    val_dir = PROJECT_DIR / "user_data" / "data_val"
    # Merge validation data with training data for indicator warmup.
    # SMA200 needs 200 days of history; we copy training data into val dir.
    train_dir = USER_DATA / "data"
    if val_dir.exists() and train_dir.exists():
        _merge_train_into_val(train_dir, val_dir)
    elif not val_dir.exists():
        val_dir = train_dir
        print(f"VAL: {val_dir} not found, using training data")

    strats = discover_strategies()
    if not strats:
        print("No strategies found", file=sys.stderr)
        return 2

    print(f"VAL: {len(strats)} strategies, {timerange}")
    for name in strats:
        try:
            results = run_val(name, timerange, val_dir)
            strat = results.get("strategy", {}).get(name, {})
            per_pair = strat.get("results_per_pair", []) or []
            total = {}
            for e in per_pair:
                if e.get("key") == "TOTAL":
                    total = e
                    break
            pct = total.get("profit_total_pct", 0)
            trades = total.get("trades", 0)
            print(f"  {name}: profit={pct:.2f}% trades={trades}")
        except Exception as err:
            print(f"  {name}: ERROR - {err}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
