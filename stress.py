"""
stress.py — 2022 bear-market pressure test.

Runs the same active strategy roster as `run.py`, but uses the 2022 BTC/ETH
bear-market timerange. This is a validation tool, not the primary leaderboard.

Usage:
    uv run stress.py
"""

from __future__ import annotations

import sys
import traceback
from os import environ
from pathlib import Path
from typing import Any

from freqtrade.configuration import Configuration
from freqtrade.enums import RunMode
from freqtrade.optimize.backtesting import Backtesting

from run import (
    CONFIG, PAIRS_STR, STRATEGIES_DIR, USER_DATA,
    compute_bah_benchmark, discover_strategies, extract_metrics, print_bah_benchmark,
)


TIMERANGE = "20220101-20221231"
STRESS_DATA_DIR = USER_DATA / "data_stress"
STRESS_ENRICHED_ROOT = STRESS_DATA_DIR / "_cache" / "enriched" / "binance"


def discover_stress_strategies() -> list[str]:
    return discover_strategies()


def run_stress_backtest(strategy_name: str) -> dict[str, Any]:
    args = {
        "config": [str(CONFIG)],
        "user_data_dir": str(USER_DATA),
        "datadir": str(STRESS_DATA_DIR),
        "strategy": strategy_name,
        "strategy_path": str(STRATEGIES_DIR),
        "timerange": TIMERANGE,
        "export": "none",
        "exportfilename": None,
        "cache": "none",
    }
    environ["AUTOQ_ENRICHED_ROOT"] = str(STRESS_ENRICHED_ROOT)
    config = Configuration(args, RunMode.BACKTEST).get_config()
    bt = Backtesting(config)
    bt.start()
    return bt.results


def print_summary(strategy_name: str, metrics: dict[str, float]) -> None:
    print("---")
    print(f"strategy:         {strategy_name}")
    print(f"timerange:        {TIMERANGE}")
    print(f"sharpe:           {metrics['sharpe']:.4f}")
    print(f"sortino:          {metrics['sortino']:.4f}")
    print(f"calmar:           {metrics['calmar']:.4f}")
    print(f"total_profit_pct: {metrics['total_profit_pct']:.4f}")
    print(f"max_drawdown_pct: {metrics['max_drawdown_pct']:.4f}")
    print(f"trade_count:      {metrics['trade_count']}")
    print(f"win_rate_pct:     {metrics['win_rate_pct']:.4f}")
    print(f"profit_factor:    {metrics['profit_factor']:.4f}")
    print(f"pairs:            {PAIRS_STR}")


def print_error(strategy_name: str, err: BaseException) -> None:
    print("---")
    print(f"strategy:         {strategy_name}")
    print("status:           ERROR")
    print(f"error_type:       {type(err).__name__}")
    print(f"error_msg:        {err}")
    print("traceback:")
    print(traceback.format_exc())


def main() -> int:
    strategies = discover_stress_strategies()
    if not strategies:
        print(f"ERROR: no strategies found in {Path(STRATEGIES_DIR)}.", file=sys.stderr)
        return 2

    print(f"Discovered {len(strategies)} strategies: {', '.join(strategies)}")
    print(f"Stress timerange: {TIMERANGE}  Pairs: {PAIRS_STR}")
    print()

    n_ok = 0
    n_err = 0
    for strategy_name in strategies:
        try:
            results = run_stress_backtest(strategy_name)
            print_summary(strategy_name, extract_metrics(results, strategy_name))
            n_ok += 1
        except BaseException as err:  # noqa: BLE001
            print_error(strategy_name, err)
            n_err += 1
        print()

    bah = compute_bah_benchmark(STRESS_DATA_DIR, "binance", TIMERANGE)
    print_bah_benchmark(bah)
    print()

    print(f"Done: {n_ok} succeeded, {n_err} failed.")
    return 0 if n_err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
