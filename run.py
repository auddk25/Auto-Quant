"""
run.py — READ-ONLY. The oracle. Do not modify.

Discovers every `.py` file in `user_data/strategies/` (except those starting
with `_`), runs FreqTrade's Backtesting in-process for each, and prints one
`---` summary block per strategy to stdout.

The agent reads these blocks to decide keep/evolve/fork/kill actions on each
strategy. A single strategy's crash produces an error block for that
strategy but does NOT abort the others.

Usage:
    uv run run.py > run.log 2>&1
    grep "^---\\|^strategy:\\|^sharpe:\\|^trade_count:" run.log
"""

from __future__ import annotations

import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any

from freqtrade.configuration import Configuration
from freqtrade.enums import RunMode
from freqtrade.optimize.backtesting import Backtesting

# ---------------------------------------------------------------------------
# Fixed constants. Do not modify.
# ---------------------------------------------------------------------------
PROJECT_DIR = Path(__file__).parent.resolve()
USER_DATA = PROJECT_DIR / "user_data"
STRATEGIES_DIR = USER_DATA / "strategies"
CONFIG = PROJECT_DIR / "config.json"
TIMERANGE = "20230101-20251231"
PAIRS_STR = "BTC/USDT,ETH/USDT"


def get_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(PROJECT_DIR),
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def discover_strategies() -> list[str]:
    """Return class names for every strategy file in strategies/, skipping
    files that start with `_` (reserved for templates, etc.)."""
    if not STRATEGIES_DIR.exists():
        return []
    names = []
    for path in sorted(STRATEGIES_DIR.glob("*.py")):
        if path.stem.startswith("_"):
            continue
        # FreqTrade's StrategyResolver assumes class name == file stem
        names.append(path.stem)
    return names


def run_backtest(strategy_name: str) -> dict[str, Any]:
    args = {
        "config": [str(CONFIG)],
        "user_data_dir": str(USER_DATA),
        "datadir": str(USER_DATA / "data"),
        "strategy": strategy_name,
        "strategy_path": str(STRATEGIES_DIR),
        "timerange": TIMERANGE,
        "export": "none",
        "exportfilename": None,
        "cache": "none",
    }
    config = Configuration(args, RunMode.BACKTEST).get_config()
    bt = Backtesting(config)
    bt.start()
    return bt.results


def _get(d: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except (TypeError, ValueError):
                continue
    return default


def extract_metrics(results: dict[str, Any], strategy_name: str) -> dict[str, float]:
    strat = results.get("strategy", {}).get(strategy_name, {}) or {}
    return {
        "sharpe": _get(strat, "sharpe", "sharpe_ratio"),
        "sortino": _get(strat, "sortino", "sortino_ratio"),
        "calmar": _get(strat, "calmar", "calmar_ratio"),
        "total_profit_pct": _get(strat, "profit_total_pct", "profit_total") * (
            1 if "profit_total_pct" in strat else 100
        ),
        "max_drawdown_pct": -abs(
            _get(strat, "max_drawdown_account", "max_drawdown", "max_drawdown_abs")
        )
        * (100 if "max_drawdown_account" in strat else 1),
        "trade_count": int(_get(strat, "total_trades", "trades")),
        "win_rate_pct": _get(strat, "winrate", "wins_rate") * 100,
        "profit_factor": _get(strat, "profit_factor"),
    }


def print_summary(strategy_name: str, commit: str, metrics: dict[str, float]) -> None:
    print("---")
    print(f"strategy:         {strategy_name}")
    print(f"commit:           {commit}")
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


def print_error(strategy_name: str, commit: str, err: BaseException) -> None:
    print("---")
    print(f"strategy:         {strategy_name}")
    print(f"commit:           {commit}")
    print(f"status:           ERROR")
    print(f"error_type:       {type(err).__name__}")
    print(f"error_msg:        {err}")
    print("traceback:")
    print(traceback.format_exc())


def main() -> int:
    strategies = discover_strategies()
    if not strategies:
        print(
            f"ERROR: no strategies found in {STRATEGIES_DIR}.\n"
            "Create at least one `.py` file under user_data/strategies/ "
            "(see user_data/strategies/_template.py.example for the skeleton).",
            file=sys.stderr,
        )
        return 2

    commit = get_commit()
    print(f"Discovered {len(strategies)} strategies: {', '.join(strategies)}")
    print(f"Timerange: {TIMERANGE}  Pairs: {PAIRS_STR}")
    print()

    n_ok = 0
    n_err = 0
    for name in strategies:
        try:
            results = run_backtest(name)
            metrics = extract_metrics(results, name)
            print_summary(name, commit, metrics)
            n_ok += 1
        except BaseException as err:  # catch everything incl. SystemExit
            print_error(name, commit, err)
            n_err += 1
        print()  # blank line between strategy blocks

    print(f"Done: {n_ok} succeeded, {n_err} failed.")
    return 0 if n_err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
