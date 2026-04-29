# CBBI + AHR999 日线策略实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a parameterized daily-timeframe strategy combining CBBI + AHR999 for bottom-fishing entries and multi-mode exits, with a screening script to find optimal parameter combinations.

**Architecture:** Single strategy class (`CbbiAhr999Daily`) with configurable entry/exit modes. A screening script (`screen_cbbi_ahr.py`) iterates parameter combinations, runs backtests via FreqTrade in-process, and outputs ranked results. Three-layer screening: coarse → fine → validation.

**Tech Stack:** Python, FreqTrade (IStrategy), talib, pandas, existing `autoq_data.cycle_bridge` (merge_cbbi, merge_ahr999, compute_ahr999)

---

## File Structure

| File | Purpose |
|------|---------|
| `user_data/strategies/CbbiAhr999Daily.py` | Parameterized strategy class (NEW) |
| `screen_cbbi_ahr.py` | Screening script: parameter sweep + backtest runner (NEW) |
| `config.json` | Existing config — no changes needed |
| `autoq_data/cycle_bridge.py` | Existing data bridge — no changes needed |
| `run.py` | Existing backtest runner — no changes needed |
| `val_rolling.py` | Existing rolling validation — no changes needed |

---

## Task 1: Create Branch + Strategy Skeleton

**Files:**
- Create: `user_data/strategies/CbbiAhr999Daily.py`

- [ ] **Step 1: Create branch**

```bash
cd E:/code/AutoQuant
git checkout -b strategy-cbbi-ahr999
```

- [ ] **Step 2: Write strategy skeleton with parameterized entry/exit modes**

```python
"""CbbiAhr999Daily — CBBI + AHR999 Daily Bottom-Fishing Strategy

Paradigm: Cycle-based bottom-fishing with dual on-chain indicators
Hypothesis: CBBI (sentiment) + AHR999 (valuation) together identify
            undervalued zones with higher accuracy than either alone.
            Daily timeframe reduces noise and extends holding periods.
Parent: CbbiMomentum (R99), Cycle01 (R86)
Created: R103
Status: active
Uses MTF: no (daily-only strategy)
"""
from pandas import DataFrame
from typing import Optional
from datetime import datetime
import talib.abstract as ta
from freqtrade.strategy import IStrategy
from autoq_data.cycle_bridge import merge_cbbi, merge_ahr999


class CbbiAhr999Daily(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1d"
    can_short = False
    max_open_trades = 1
    minimal_roi = {"0": 100}
    stoploss = -0.25
    process_only_new_candles = True
    use_exit_signal = True
    startup_candle_count: int = 200

    # ---- Configurable parameters (set by screening script) ----
    ENTRY_MODE = "threshold"   # "threshold" | "momentum" | "hybrid"
    EXIT_MODE = "high_estimate"  # "high_estimate" | "momentum_rev" | "trend"

    # Threshold entry params
    CB_THRESHOLD = 0.35
    AHR_THRESHOLD = 0.60

    # Momentum entry params
    MOMENTUM_N = 3

    # High-estimate exit params
    EXIT_CB = 0.80
    EXIT_AHR = 1.2

    # Momentum reversal exit params
    EXIT_MOM_N = 3
    EXIT_MOM_THRESHOLD = 0.03

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = merge_cbbi(dataframe, metadata)
        dataframe = merge_ahr999(dataframe, metadata)
        # Momentum calculations
        for n in [3, 5, 7]:
            dataframe[f"cbbi_mom_{n}"] = dataframe["cbbi"] - dataframe["cbbi"].shift(n)
            dataframe[f"ahr_mom_{n}"] = dataframe["ahr999"] - dataframe["ahr999"].shift(n)
        # Trend indicators for exit mode Z
        dataframe["sma200"] = ta.SMA(dataframe, timeperiod=200)
        dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if metadata["pair"] != "BTC/USDT":
            return dataframe

        cbbi = dataframe["cbbi"]
        ahr = dataframe["ahr999"]
        vol_ok = dataframe["volume"] > 0

        if self.ENTRY_MODE == "threshold":
            cond = (cbbi < self.CB_THRESHOLD) & (ahr < self.AHR_THRESHOLD) & vol_ok
        elif self.ENTRY_MODE == "momentum":
            n = self.MOMENTUM_N
            cond = (dataframe[f"cbbi_mom_{n}"] > 0) & (dataframe[f"ahr_mom_{n}"] > 0) & vol_ok
        elif self.ENTRY_MODE == "hybrid":
            n = self.MOMENTUM_N
            cond = (
                (cbbi < self.CB_THRESHOLD) & (ahr < self.AHR_THRESHOLD) &
                (dataframe[f"cbbi_mom_{n}"] > 0) & vol_ok
            )
        else:
            cond = vol_ok & False  # no entry

        dataframe.loc[cond.fillna(False), "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        cbbi = dataframe["cbbi"]
        ahr = dataframe["ahr999"]

        if self.EXIT_MODE == "high_estimate":
            cond = (cbbi > self.EXIT_CB) | (ahr > self.EXIT_AHR)
        elif self.EXIT_MODE == "momentum_rev":
            n = self.EXIT_MOM_N
            cond = dataframe[f"cbbi_mom_{n}"] < -self.EXIT_MOM_THRESHOLD
        elif self.EXIT_MODE == "trend":
            cond = (dataframe["close"] < dataframe["sma200"]) | (dataframe["ema50"] < dataframe["ema200"])
        else:
            cond = cbbi > 0.80  # fallback

        dataframe.loc[cond.fillna(False), "exit_long"] = 1
        return dataframe

    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: Optional[float], max_stake: float,
                            entry_tag: Optional[str], side: str, **kwargs) -> float:
        return self.wallets.get_total_stake_amount() * 0.99
```

- [ ] **Step 3: Verify strategy loads without errors**

```bash
cd E:/code/AutoQuant
uv run python -c "from user_data.strategies.CbbiAhr999Daily import CbbiAhr999Daily; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add user_data/strategies/CbbiAhr999Daily.py
git commit -m "R103: CbbiAhr999Daily — parameterized CBBI+ADR999 daily strategy skeleton"
```

---

## Task 2: Screening Script — Coarse Filter

**Files:**
- Create: `screen_cbbi_ahr.py`

- [ ] **Step 1: Write screening script**

```python
"""screen_cbbi_ahr.py — CBBI + AHR999 parameter screening.

Layer 1 (coarse): Tests 6 strategy types × representative params = ~18 runs.
Layer 2 (fine): Expands top-3 types with 5-8 param variants each.

Usage:
    uv run screen_cbbi_ahr.py              # coarse screening
    uv run screen_cbbi_ahr.py --fine       # fine screening (after coarse)
"""
from __future__ import annotations
import sys
import itertools
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
    # Import and configure strategy
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
    combos = COARSE_COMBOS  # TODO: fine mode combos added in Task 4

    print(f"=== CBBI+ADR999 Screening ({'F' if fine_mode else 'Coarse'}) ===")
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
```

- [ ] **Step 2: Verify script loads without errors**

```bash
cd E:/code/AutoQuant
uv run python -c "import screen_cbbi_ahr; print(f'Combos: {len(screen_cbbi_ahr.COARSE_COMBOS)}')"
```

Expected: `Combos: 18` (9 threshold×2 exit + 3 momentum×2 exit + 2 hybrid×1 trend + ...)

- [ ] **Step 3: Commit**

```bash
git add screen_cbbi_ahr.py
git commit -m "R103: screening script — coarse filter for CBBI+ADR999 params"
```

---

## Task 3: Run Coarse Screening

**Files:**
- Modify: `screen_cbbi_ahr.py` (results only)

- [ ] **Step 1: Run coarse screening**

```bash
cd E:/code/AutoQuant
uv run screen_cbbi_ahr.py 2>&1 | tee screen_coarse.log
```

Expected: ~18 backtest runs, each taking ~30 seconds. Total ~10 minutes.

- [ ] **Step 2: Analyze results — identify Top-3 strategy types**

Read `screen_coarse.log`. Look for:
- Which entry mode performs best (threshold vs momentum vs hybrid)
- Which exit mode works best with each entry
- Filter: trades >= 5, profit > +88%

- [ ] **Step 3: Record coarse screening results**

Add summary to `STRATEGY_MAP.md` or a results file.

- [ ] **Step 4: Commit**

```bash
git add screen_coarse.log
git commit -m "R103: coarse screening results — Top-3 identified"
```

---

## Task 4: Fine Screening — Expand Top-3

**Files:**
- Modify: `screen_cbbi_ahr.py` (add fine mode with expanded params)

- [ ] **Step 1: Add fine-mode parameter grid based on coarse results**

Based on Task 3 results, expand the top-3 entry×exit combinations. Example structure (replace with actual top-3):

```python
# Fine screening: expand around top-3 coarse results
FINE_COMBOS = []
# Example: if threshold+high_estimate was top-1
for cb in [0.30, 0.32, 0.35, 0.38, 0.40]:
    for ahr in [0.40, 0.50, 0.60, 0.70, 0.80]:
        for exit_cb in [0.70, 0.75, 0.80, 0.85]:
            for exit_ahr in [0.8, 1.0, 1.2, 1.5]:
                FINE_COMBOS.append({
                    "ENTRY_MODE": "threshold",
                    "EXIT_MODE": "high_estimate",
                    "CB_THRESHOLD": cb, "AHR_THRESHOLD": ahr,
                    "EXIT_CB": exit_cb, "EXIT_AHR": exit_ahr,
                })
# Add similar blocks for top-2 and top-3...
```

Update `main()` to use `FINE_COMBOS` when `--fine` is passed.

- [ ] **Step 2: Run fine screening**

```bash
cd E:/code/AutoQuant
uv run screen_cbbi_ahr.py --fine 2>&1 | tee screen_fine.log
```

Expected: ~24-50 runs depending on parameter expansion.

- [ ] **Step 3: Identify final top-3 parameter sets**

Criteria:
- Profit > +88% (beat BAH)
- Max drawdown < -25%
- Trades >= 5
- Best profit/drawdown ratio

- [ ] **Step 4: Commit**

```bash
git add screen_cbbi_ahr.py screen_fine.log
git commit -m "R103: fine screening — expanded top-3 parameter regions"
```

---

## Task 5: Rolling Window Validation

**Files:**
- Modify: `user_data/strategies/CbbiAhr999Daily.py` (set final params)

- [ ] **Step 1: Set strategy to top-1 parameters from fine screening**

Edit `CbbiAhr999Daily.py` class attributes to the winning parameter set.

- [ ] **Step 2: Run rolling validation**

```bash
cd E:/code/AutoQuant
uv run val_rolling.py 2>&1 | tee val_rolling_cbbiahr.log
```

Expected output: 7-window table with CbbiAhr999Daily row. Check:
- Mean > +25%
- No single window < -25%
- No consecutive negative windows

- [ ] **Step 3: Run OOS validation**

```bash
cd E:/code/AutoQuant
uv run val.py 2>&1 | tee val_oos_cbbiahr.log
```

Expected: profit and trade count for 2026 Q1.

- [ ] **Step 4: If validation fails, try top-2 and top-3 params**

Repeat steps 1-3 with next-best parameter set.

- [ ] **Step 5: Commit**

```bash
git add user_data/strategies/CbbiAhr999Daily.py val_rolling_cbbiahr.log val_oos_cbbiahr.log
git commit -m "R103: final params validated — [param summary]"
```

---

## Task 6: Record Results + Documentation

**Files:**
- Modify: `results.tsv`
- Modify: `STRATEGY_MAP.md`

- [ ] **Step 1: Add results to results.tsv**

Append row with: round, strategy name, event, metrics, notes.

- [ ] **Step 2: Update STRATEGY_MAP.md**

Add CbbiAhr999Daily section with:
- Entry/exit logic (final params)
- Training metrics
- Rolling window results
- Trade log (if applicable)

- [ ] **Step 3: Commit**

```bash
git add results.tsv STRATEGY_MAP.md
git commit -m "R103: record CbbiAhr999Daily results in strategy map"
```

---

## Task 7: Compare with Baselines

- [ ] **Step 1: Run all active strategies for comparison**

```bash
cd E:/code/AutoQuant
uv run run.py 2>&1 | tee run_compare.log
```

Compare CbbiAhr999Daily vs:
- BuyAndHold (+88.5%)
- CbbiMomentum (+732.7%)
- SmartHold (+92.8%)
- Bear01 (+107.7%)

- [ ] **Step 2: Final commit with comparison**

```bash
git add run_compare.log
git commit -m "R103: final comparison — CbbiAhr999Daily vs baselines"
```

---

## Acceptance Criteria

- [ ] Coarse screening complete (18+ runs)
- [ ] Fine screening complete (24+ runs)
- [ ] Rolling validation: 7-window mean > +25%
- [ ] OOS validation: 2026 Q1 results recorded
- [ ] At least 1 parameter set beats BAH (+88.5%)
- [ ] Results in results.tsv and STRATEGY_MAP.md

---

## Known Constraints

- CBBI API returns HTTP 406; cached data through 2026-04-24
- AHR999 requires SMA200 warmup (200 days)
- Daily timeframe = ~1000 data points (2022-2025), overfitting risk
- BTC only (AHR999 not meaningful for ETH)
- `run.py` runs on 2 pairs (BTC+ETH); strategy only signals on BTC, ETH will show 0 trades
