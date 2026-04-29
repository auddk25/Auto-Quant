"""screen_cbbi_momentum.py — CbbiMomentum 参数优化筛选.

Tests different parameter combinations for CbbiMomentum strategy.

Usage:
    uv run screen_cbbi_momentum.py              # parameter scan
    uv run screen_cbbi_momentum.py --optimize   # combination optimization
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
CONFIG = PROJECT / "config.json"
DATA = USER_DATA / "data"
TIMERANGE = "20230101-20251231"

# Parameter definitions for scan
MOMENTUM_PARAMS = {
    "entry_mom": [2, 3, 4, 5],
    "exit_mom": [3, 4, 5, 6],
}

CBBI_THRESHOLD_PARAMS = {
    "cb_threshold": [0.50, 0.55, 0.60, 0.65, 0.70, 0.75],
}

EXIT_PARAMS = {
    "exit_threshold": [-0.02, -0.03, -0.04, -0.05],
    "exit_cbbi": [0.75, 0.80, 0.85],
}

TREND_PARAMS = {
    "trend_fast": [50, 100],
    "trend_slow": [100, 200],
}

# Combination optimization: Top-3 from each scan
OPTIMIZE_COMBOS = []
for entry_mom in [2, 3, 4]:
    for exit_mom in [3, 4, 5]:
        for cb_threshold in [0.55, 0.60, 0.65]:
            for exit_threshold in [-0.02, -0.03, -0.04]:
                for exit_cbbi in [0.75, 0.80, 0.85]:
                    OPTIMIZE_COMBOS.append({
                        "ENTRY_MOM": entry_mom,
                        "EXIT_MOM": exit_mom,
                        "CB_THRESHOLD": cb_threshold,
                        "EXIT_THRESHOLD": exit_threshold,
                        "EXIT_CBBI": exit_cbbi,
                    })


def run_backtest(params: dict) -> dict:
    """Run backtest with given params applied to strategy instance."""
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


def extract_metrics(results: dict, name: str) -> dict:
    strat = results.get("strategy", {}).get(name, {})
    if not strat:
        # Debug: print available strategy names
        print(f"  DEBUG: strategy '{name}' not found. Available: {list(results.get('strategy', {}).keys())}")
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


def format_params(params: dict) -> str:
    """Compact param string for display."""
    parts = []
    for k, v in sorted(params.items()):
        parts.append(f"{k}={v}")
    return " | ".join(parts)


def main():
    optimize_mode = "--optimize" in sys.argv

    if optimize_mode:
        combos = OPTIMIZE_COMBOS
        print(f"=== CbbiMomentum Optimization ({len(combos)} combos) ===\n")
    else:
        # Parameter scan mode
        combos = []
        # Momentum scan
        for entry_mom in MOMENTUM_PARAMS["entry_mom"]:
            for exit_mom in MOMENTUM_PARAMS["exit_mom"]:
                combos.append({"ENTRY_MOM": entry_mom, "EXIT_MOM": exit_mom})
        # CBBI threshold scan
        for cb_threshold in CBBI_THRESHOLD_PARAMS["cb_threshold"]:
            combos.append({"CB_THRESHOLD": cb_threshold})
        # Exit threshold scan
        for exit_threshold in EXIT_PARAMS["exit_threshold"]:
            combos.append({"EXIT_THRESHOLD": exit_threshold})
        # Exit CBBI scan
        for exit_cbbi in EXIT_PARAMS["exit_cbbi"]:
            combos.append({"EXIT_CBBI": exit_cbbi})
        # Trend filter scan
        for trend_fast in TREND_PARAMS["trend_fast"]:
            for trend_slow in TREND_PARAMS["trend_slow"]:
                if trend_fast < trend_slow:
                    combos.append({"TREND_FAST": trend_fast, "TREND_SLOW": trend_slow})
        print(f"=== CbbiMomentum Parameter Scan ({len(combos)} combos) ===\n")

    results = []
    for i, params in enumerate(combos):
        label = format_params(params)
        try:
            bt_results = run_backtest(params)
            metrics = extract_metrics(bt_results, "MtfTrendCbbiMomentumParam")
            results.append((params, metrics))
            print(f"[{i+1}/{len(combos)}] {label}")
            print(f"  profit={metrics['profit_pct']:.1f}% dd={metrics['max_dd_pct']:.1f}% "
                  f"trades={metrics['trades']} wr={metrics['win_rate']:.0f}% "
                  f"pf={metrics['profit_factor']:.2f} sharpe={metrics['sharpe']:.4f}")
        except Exception as e:
            print(f"[{i+1}/{len(combos)}] {label}")
            print(f"  ERROR: {e}")
        print()

    # Rank by profit
    valid = [(p, m) for p, m in results if m["trades"] >= 5]
    valid.sort(key=lambda x: x[1]["profit_pct"], reverse=True)

    print("=== Results (trades >= 5, sorted by profit) ===")
    for i, (p, m) in enumerate(valid[:10]):
        print(f"#{i+1}: profit={m['profit_pct']:.1f}% dd={m['max_dd_pct']:.1f}% "
              f"trades={m['trades']} wr={m['win_rate']:.0f}% pf={m['profit_factor']:.2f}")
        print(f"     {format_params(p)}")

    # Compare with current best
    current_best = 732.7
    if valid and valid[0][1]["profit_pct"] > current_best:
        print(f"\n*** NEW BEST: {valid[0][1]['profit_pct']:.1f}% (vs {current_best}%) ***")
    else:
        print(f"\n*** Current best: {current_best}% ***")


if __name__ == "__main__":
    main()
