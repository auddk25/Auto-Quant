"""run_fusion_test.py — Compare CBBI fusion strategies.

Usage: uv run run_fusion_test.py
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
CONFIG = PROJECT / "config.json"
DATA = USER_DATA / "data"
TIMERANGE = "20230101-20251231"


def run_backtest(strategy: str) -> dict:
    args = {
        "config": [str(CONFIG)], "user_data_dir": str(USER_DATA),
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
        if e.get("key") == "BTC/USDT":
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
    print("CBBI Multi-Indicator Fusion Strategy Comparison")
    print("=" * 80)

    strategies = [
        ("MtfTrendCbbiMomentumEnsemble", "Ensemble (baseline)"),
        ("MtfTrendCbbiRsiFusion", "CBBI + RSI"),
        ("MtfTrendCbbiMacdFusion", "CBBI + MACD"),
        ("MtfTrendCbbiBbFusion", "CBBI + Bollinger"),
    ]

    results = {}
    for i, (name, label) in enumerate(strategies, 1):
        print(f"\n[{i}/{len(strategies)}] {label}...")
        r = run_backtest(name)
        m = extract_metrics(r, name)
        results[name] = m
        print(f"  Profit: {m['profit_pct']:.1f}%")
        print(f"  Max DD: {m['max_dd_pct']:.1f}%")
        print(f"  Trades: {m['trades']}")
        print(f"  Win rate: {m['win_rate']:.1f}%")
        print(f"  Profit factor: {m['profit_factor']:.2f}")

    # Comparison table
    print("\n" + "=" * 80)
    print("Comparison")
    print("=" * 80)
    labels = [label for _, label in strategies]
    print(f"{'Metric':<16} {labels[0]:<20} {labels[1]:<16} {labels[2]:<16} {labels[3]:<16}")
    print("-" * 84)

    m0 = results[strategies[0][0]]
    for metric_name, key in [("Profit %", "profit_pct"), ("Max DD %", "max_dd_pct"),
                              ("Trades", "trades"), ("Win Rate %", "win_rate"),
                              ("Profit Factor", "profit_factor")]:
        vals = [results[name][key] for name, _ in strategies]
        line = f"{metric_name:<16}"
        for v in vals:
            if key == "trades":
                line += f"{v:<20}" if vals.index(v) == 0 else f"{v:<16}"
            elif key == "profit_factor":
                line += f"{v:<20.2f}" if vals.index(v) == 0 else f"{v:<16.2f}"
            else:
                line += f"{v:<20.1f}" if vals.index(v) == 0 else f"{v:<16.1f}"
        print(line)

    # Recommendation
    print("\n" + "=" * 80)
    print("Recommendation")
    print("=" * 80)

    best_name = max(results, key=lambda k: results[k]["profit_pct"])
    best_label = [label for name, label in strategies if name == best_name][0]
    print(f"Best performer: {best_label} ({results[best_name]['profit_pct']:.1f}%)")

    for name, label in strategies[1:]:
        m = results[name]
        if m['profit_pct'] > m0['profit_pct'] * 1.1:
            print(f"[RECOMMENDED] {label} shows significant improvement over Ensemble")
        elif m['profit_pct'] > m0['profit_pct'] * 0.9:
            print(f"[CONSIDER] {label} shows similar performance to Ensemble")
        else:
            print(f"[NOT RECOMMENDED] {label} underperforms Ensemble")

    return 0


if __name__ == "__main__":
    sys.exit(main())
