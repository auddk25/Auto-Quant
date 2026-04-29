"""screen_cbbi_ahr.py — CBBI + AHR999 parameter screening.

Layer 1 (coarse): Tests 6 strategy types × representative params = ~18 runs.
Layer 2 (fine): Expands top-3 types with 5-8 param variants each.

Usage:
    uv run screen_cbbi_ahr.py              # coarse screening
    uv run screen_cbbi_ahr.py --fine       # fine screening (after coarse)
"""
from __future__ import annotations
import sys
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
TIMERANGE = "20230101-20251231"

# ---- Parameter definitions ----
ENTRY_PARAMS = {
    "threshold": [
        {"CB_THRESHOLD": cb, "AHR_THRESHOLD": ahr}
        for cb, ahr in [(0.30, 0.40), (0.35, 0.60), (0.40, 0.80)]
    ],
    "momentum": [
        {"MOMENTUM_N": n}
        for n in [3, 5, 7]
    ],
    "hybrid": [
        {"CB_THRESHOLD": cb, "AHR_THRESHOLD": ahr, "MOMENTUM_N": n}
        for cb, ahr, n in [(0.35, 0.60, 3), (0.40, 0.80, 5)]
    ],
}

EXIT_PARAMS = {
    "high_estimate": [
        {"EXIT_CB": cb, "EXIT_AHR": ahr}
        for cb, ahr in [(0.75, 1.0), (0.80, 1.2)]
    ],
    "momentum_rev": [
        {"EXIT_MOM_N": n, "EXIT_MOM_THRESHOLD": t}
        for n, t in [(3, 0.03), (5, 0.05)]
    ],
    "trend": [{}],  # no params
}

# Coarse: all entry×exit combos
COARSE_COMBOS = []
for entry_mode, entry_list in ENTRY_PARAMS.items():
    for exit_mode, exit_list in EXIT_PARAMS.items():
        for ep in entry_list:
            for xp in exit_list:
                COARSE_COMBOS.append({
                    "ENTRY_MODE": entry_mode,
                    "EXIT_MODE": exit_mode,
                    **ep, **xp,
                })


def run_backtest(params: dict) -> dict[str, Any]:
    """Run backtest with given params applied to strategy class."""
    from user_data.strategies.CbbiAhr999Daily import CbbiAhr999Daily
    for k, v in params.items():
        setattr(CbbiAhr999Daily, k, v)

    args = {
        "config": [str(CONFIG)], "user_data_dir": str(USER_DATA),
        "datadir": str(DATA), "strategy": "CbbiAhr999Daily",
        "strategy_path": str(STRATEGIES), "timerange": TIMERANGE,
        "export": "none", "exportfilename": None, "cache": "none",
    }
    config = Configuration(args, RunMode.BACKTEST).get_config()
    bt = Backtesting(config)
    bt.start()
    return bt.results


def extract_metrics(results: dict, name: str) -> dict:
    strat = results.get("strategy", {}).get(name, {})
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
    parts.append(f"entry={params['ENTRY_MODE']}")
    parts.append(f"exit={params['EXIT_MODE']}")
    for k, v in sorted(params.items()):
        if k not in ("ENTRY_MODE", "EXIT_MODE"):
            parts.append(f"{k}={v}")
    return " | ".join(parts)


def main():
    fine_mode = "--fine" in sys.argv
    combos = COARSE_COMBOS  # fine mode combos added in Task 4

    print(f"=== CBBI+ADR999 Screening ({'Fine' if fine_mode else 'Coarse'}) ===")
    print(f"Combos: {len(combos)}")
    print()

    results = []
    for i, params in enumerate(combos):
        label = format_params(params)
        try:
            bt_results = run_backtest(params)
            metrics = extract_metrics(bt_results, "CbbiAhr999Daily")
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

    # Save top-3 for fine screening
    if not fine_mode and len(valid) >= 3:
        print("\n=== Top-3 for fine screening ===")
        for i, (p, m) in enumerate(valid[:3]):
            print(f"  Top-{i+1}: {format_params(p)}")


if __name__ == "__main__":
    main()
