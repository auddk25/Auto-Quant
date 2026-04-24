"""
run_daily.py — Daily timeframe backtest runner.

Discovers every `.py` file in `user_data/strategies_daily/` (except those starting
with `_`), runs FreqTrade's Backtesting in-process for each, and prints one
`---` summary block per strategy to stdout.

The agent reads these blocks to decide keep/evolve/fork/kill actions on each
strategy. A single strategy's crash produces an error block for that
strategy but does NOT abort the others.

Usage:
    uv run run_daily.py > run_daily.log 2>&1
    grep "^---\\|^strategy:\\|^sharpe:\\|^trade_count:" run.log
"""

from __future__ import annotations

import math
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from freqtrade.configuration import Configuration
from freqtrade.enums import RunMode
from freqtrade.optimize.backtesting import Backtesting

# ---------------------------------------------------------------------------
# Fixed constants. Do not modify.
# ---------------------------------------------------------------------------
PROJECT_DIR = Path(__file__).parent.resolve()
USER_DATA = PROJECT_DIR / "user_data"
STRATEGIES_DIR = USER_DATA / "strategies_daily"
CONFIG = PROJECT_DIR / "config_daily.json"
TIMERANGE = "20230101-20260423"
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


def compute_bah_benchmark(
    data_dir: Path, exchange: str, timerange: str
) -> dict[str, dict[str, float]]:
    """Buy-and-hold stats from the OHLCV feather files for the given timerange.

    Sharpe is computed from daily log-returns annualised with sqrt(365).
    This is the standard time-series Sharpe, NOT the trade-based Sharpe that
    Freqtrade reports for strategies — the two are not directly comparable, but
    both give a useful sense of risk-adjusted return.
    """
    parts = timerange.split("-")
    ts = pd.Timestamp(parts[0], tz="UTC")
    te = pd.Timestamp(parts[1], tz="UTC") + pd.Timedelta(hours=23)

    results: dict[str, dict[str, float]] = {}
    all_log_returns: list[pd.Series] = []

    for pair in ["BTC/USDT", "ETH/USDT"]:
        path = data_dir / exchange / f"{pair.replace('/', '_')}-1h.feather"
        if not path.exists():
            return {}
        df = pd.read_feather(path).sort_values("date")
        df = df[(df["date"] >= ts) & (df["date"] <= te)]
        if len(df) < 2:
            return {}

        daily = df.set_index("date")["close"].resample("1D").last().dropna()
        log_ret = np.log(daily / daily.shift(1)).dropna()

        total_return = (daily.iloc[-1] / daily.iloc[0] - 1) * 100
        sharpe = (
            log_ret.mean() / log_ret.std() * math.sqrt(365)
            if log_ret.std() > 0 else 0.0
        )
        max_dd = ((daily - daily.cummax()) / daily.cummax()).min() * 100

        results[pair] = {
            "total_return_pct": total_return,
            "sharpe_approx": sharpe,
            "max_drawdown_pct": max_dd,
        }
        all_log_returns.append(log_ret)

    if len(all_log_returns) == 2:
        combined = pd.concat(all_log_returns, axis=1).mean(axis=1)
        avg_return = sum(v["total_return_pct"] for v in results.values()) / 2
        port_sharpe = (
            combined.mean() / combined.std() * math.sqrt(365)
            if combined.std() > 0 else 0.0
        )
        pair_dfs = []
        for pair in ["BTC/USDT", "ETH/USDT"]:
            path = data_dir / exchange / f"{pair.replace('/', '_')}-1h.feather"
            df = pd.read_feather(path).sort_values("date")
            df = df[(df["date"] >= ts) & (df["date"] <= te)]
            daily = df.set_index("date")["close"].resample("1D").last().dropna()
            pair_dfs.append(daily / daily.iloc[0])
        port_equity = pd.concat(pair_dfs, axis=1).mean(axis=1)
        port_dd = ((port_equity - port_equity.cummax()) / port_equity.cummax()).min() * 100
        results["50%BTC+50%ETH"] = {
            "total_return_pct": avg_return,
            "sharpe_approx": port_sharpe,
            "max_drawdown_pct": port_dd,
        }

    return results


def print_bah_benchmark(bah: dict[str, dict[str, float]]) -> None:
    if not bah:
        return
    print("---")
    print("benchmark:        buy-and-hold (same pairs, same timerange)")
    for label, s in bah.items():
        print(
            f"  {label:<22}  return: {s['total_return_pct']:>8.1f}%"
            f"  sharpe*: {s['sharpe_approx']:.4f}"
            f"  dd: {s['max_drawdown_pct']:.1f}%"
        )
    print(
        "  *sharpe: daily log-returns x sqrt(365); methodology differs from"
        " strategy trade-based sharpe -- treat as directional reference only"
    )


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

    bah = compute_bah_benchmark(USER_DATA / "data", "binance", TIMERANGE)
    print_bah_benchmark(bah)
    print()

    print(f"Done: {n_ok} succeeded, {n_err} failed.")
    return 0 if n_err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
