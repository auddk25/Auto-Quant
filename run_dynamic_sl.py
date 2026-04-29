"""run_dynamic_sl.py — Compare fixed vs dynamic stoploss for ensemble strategy.

Usage: uv run run_dynamic_sl.py
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
                "avg_duration": str(e.get("avg_duration", "")),
            }
    return {"profit_pct": 0, "max_dd_pct": 0, "trades": 0, "win_rate": 0, "profit_factor": 0, "avg_duration": ""}


def main():
    print("=" * 70)
    print("Fixed vs Dynamic Stoploss Comparison")
    print("=" * 70)

    # Run fixed stoploss version
    print("\n[1/2] Fixed Stoploss (Ensemble)...")
    r1 = run_backtest("MtfTrendCbbiMomentumEnsemble")
    m1 = extract_metrics(r1, "MtfTrendCbbiMomentumEnsemble")
    print(f"  Profit: {m1['profit_pct']:.1f}%")
    print(f"  Max DD: {m1['max_dd_pct']:.1f}%")
    print(f"  Trades: {m1['trades']}")
    print(f"  Win rate: {m1['win_rate']:.1f}%")
    print(f"  Profit factor: {m1['profit_factor']:.2f}")

    # Run dynamic stoploss version
    print("\n[2/2] Dynamic Stoploss (Ensemble + ATR)...")
    r2 = run_backtest("MtfTrendCbbiMomentumEnsembleDSL")
    m2 = extract_metrics(r2, "MtfTrendCbbiMomentumEnsembleDSL")
    print(f"  Profit: {m2['profit_pct']:.1f}%")
    print(f"  Max DD: {m2['max_dd_pct']:.1f}%")
    print(f"  Trades: {m2['trades']}")
    print(f"  Win rate: {m2['win_rate']:.1f}%")
    print(f"  Profit factor: {m2['profit_factor']:.2f}")

    # Comparison
    print("\n" + "=" * 70)
    print("Comparison")
    print("=" * 70)
    print(f"{'Metric':<20} {'Fixed SL':<15} {'Dynamic SL':<15} {'Change':<15}")
    print("-" * 65)
    print(f"{'Profit %':<20} {m1['profit_pct']:<15.1f} {m2['profit_pct']:<15.1f} {m2['profit_pct']-m1['profit_pct']:+.1f}")
    print(f"{'Max DD %':<20} {m1['max_dd_pct']:<15.1f} {m2['max_dd_pct']:<15.1f} {m2['max_dd_pct']-m1['max_dd_pct']:+.1f}")
    print(f"{'Trades':<20} {m1['trades']:<15} {m2['trades']:<15} {m2['trades']-m1['trades']:+d}")
    print(f"{'Win Rate %':<20} {m1['win_rate']:<15.1f} {m2['win_rate']:<15.1f} {m2['win_rate']-m1['win_rate']:+.1f}")
    print(f"{'Profit Factor':<20} {m1['profit_factor']:<15.2f} {m2['profit_factor']:<15.2f} {m2['profit_factor']-m1['profit_factor']:+.2f}")

    # Recommendation
    print("\n" + "=" * 70)
    print("Recommendation")
    print("=" * 70)

    dd_improved = m2['max_dd_pct'] > m1['max_dd_pct']  # Less negative = better
    profit_maintained = m2['profit_pct'] > m1['profit_pct'] * 0.9  # Within 10%

    if dd_improved and profit_maintained:
        print("[RECOMMENDED] Dynamic stoploss reduces drawdown while maintaining profit")
    elif dd_improved:
        print("[CONSIDER] Dynamic stoploss reduces drawdown but profit decreased")
    else:
        print("[NOT RECOMMENDED] Dynamic stoploss did not improve drawdown")

    return 0


if __name__ == "__main__":
    sys.exit(main())
