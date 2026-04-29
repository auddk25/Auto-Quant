"""run_futures_test.py — Test futures long/short strategy.

Usage: uv run run_futures_test.py
"""
from __future__ import annotations
import sys
from pathlib import Path

import aiohttp.connector, aiohttp.resolver
aiohttp.connector.DefaultResolver = aiohttp.resolver.ThreadedResolver

from freqtrade.configuration import Configuration
from freqtrade.enums import RunMode
from freqtrade.optimize.backtesting import Backtesting

PROJECT = Path(__file__).parent
USER_DATA = PROJECT / "user_data"
STRATEGIES = USER_DATA / "strategies"
CONFIG = PROJECT / "config_futures.json"
DATA = USER_DATA / "data"
TIMERANGE = "20230101-20251231"


def run_backtest(strategy: str, config_path: str) -> dict:
    args = {
        "config": [config_path], "user_data_dir": str(USER_DATA),
        "datadir": str(DATA), "strategy": strategy,
        "strategy_path": str(STRATEGIES), "timerange": TIMERANGE,
        "export": "none", "exportfilename": None, "cache": "none",
    }
    config = Configuration(args, RunMode.BACKTEST).get_config()
    bt = Backtesting(config)
    bt.start()
    return bt.results


def extract_metrics(results: dict, strategy: str) -> dict:
    strat = results.get("strategy", {}).get(strategy, {})
    per_pair = strat.get("results_per_pair", []) or []
    for e in per_pair:
        if "BTC" in e.get("key", ""):
            return {
                "profit_pct": float(e.get("profit_total_pct", 0)),
                "max_dd_pct": -abs(float(e.get("max_drawdown_account", 0))) * 100,
                "trades": int(e.get("trades", 0)),
                "win_rate": float(e.get("winrate", 0)) * 100,
                "profit_factor": float(e.get("profit_factor", 0)),
            }
    return {"profit_pct": 0, "max_dd_pct": 0, "trades": 0, "win_rate": 0, "profit_factor": 0}


def main():
    print("=" * 80)
    print("Futures Long/Short Strategy Test")
    print("=" * 80)

    # Test 1: Spot baseline (Ensemble)
    print("\n[1/2] Spot Ensemble (baseline)...")
    r1 = run_backtest("MtfTrendCbbiMomentumEnsemble", str(PROJECT / "config.json"))
    m1 = extract_metrics(r1, "MtfTrendCbbiMomentumEnsemble")
    print(f"  Profit: {m1['profit_pct']:.1f}%")
    print(f"  Max DD: {m1['max_dd_pct']:.1f}%")
    print(f"  Trades: {m1['trades']}")
    print(f"  Win rate: {m1['win_rate']:.1f}%")
    print(f"  Profit factor: {m1['profit_factor']:.2f}")

    # Test 2: Futures Long/Short
    print("\n[2/2] Futures Long/Short (MtfTrendLongShort)...")
    try:
        r2 = run_backtest("MtfTrendLongShort", str(CONFIG))
        m2 = extract_metrics(r2, "MtfTrendLongShort")
        print(f"  Profit: {m2['profit_pct']:.1f}%")
        print(f"  Max DD: {m2['max_dd_pct']:.1f}%")
        print(f"  Trades: {m2['trades']}")
        print(f"  Win rate: {m2['win_rate']:.1f}%")
        print(f"  Profit factor: {m2['profit_factor']:.2f}")
    except Exception as e:
        print(f"  ERROR: {e}")
        m2 = {"profit_pct": 0, "max_dd_pct": 0, "trades": 0, "win_rate": 0, "profit_factor": 0}

    # Comparison
    print("\n" + "=" * 80)
    print("Comparison")
    print("=" * 80)
    print(f"{'Metric':<16} {'Spot Ensemble':<18} {'Futures L/S':<18}")
    print("-" * 52)
    for metric_name, key in [("Profit %", "profit_pct"), ("Max DD %", "max_dd_pct"),
                              ("Trades", "trades"), ("Win Rate %", "win_rate"),
                              ("Profit Factor", "profit_factor")]:
        v1, v2 = m1[key], m2[key]
        if key == "trades":
            print(f"{metric_name:<16} {v1:<18} {v2:<18}")
        elif key == "profit_factor":
            print(f"{metric_name:<16} {v1:<18.2f} {v2:<18.2f}")
        else:
            print(f"{metric_name:<16} {v1:<18.1f} {v2:<18.1f}")

    # Recommendation
    print("\n" + "=" * 80)
    print("Recommendation")
    print("=" * 80)
    if m2['profit_pct'] > m1['profit_pct'] * 1.1:
        print("[RECOMMENDED] Futures L/S shows significant improvement")
    elif m2['profit_pct'] > m1['profit_pct'] * 0.9:
        print("[CONSIDER] Futures L/S shows similar performance")
    elif m2['profit_pct'] > 0:
        print("[NOT RECOMMENDED] Futures L/S underperforms spot Ensemble")
    else:
        print("[FAILED] Futures L/S could not be tested or produced no trades")

    return 0


if __name__ == "__main__":
    sys.exit(main())
