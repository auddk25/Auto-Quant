"""_simulator_cbbi.py — CBBI momentum multi-regime simulator with leverage.

Tests CbbiMomentum logic with Long (1-3x), Short (2x), and Cash positions.
Runs on daily data, bypasses FreqTrade for fast iteration.

Usage: uv run _simulator_cbbi.py
"""

import pandas as pd
import numpy as np

# ── Load & prepare data ────────────────────────────────────
df_1h = pd.read_feather("user_data/data/BTC_USDT-1h.feather")
df_1h["date"] = pd.to_datetime(df_1h["date"]).dt.tz_convert("UTC")
df_1h = df_1h.set_index("date")
df = df_1h.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()

# Indicators (shifted for no look-ahead)
df["sma200"] = df["close"].rolling(200).mean().shift(1)
df["ema100"] = df["close"].ewm(span=100).mean().shift(1)
df["ema200"] = df["close"].ewm(span=200).mean().shift(1)

# CBBI
cbbi = pd.read_feather("user_data/data/_cache/cbbi_daily.feather")
cbbi["date"] = pd.to_datetime(cbbi["date"]).dt.tz_localize("UTC").dt.normalize()
df["_day"] = df.index.normalize()
df["cbbi"] = df["_day"].map(cbbi.set_index("date")["cbbi"]).ffill()
df["cbbi_mom_3d"] = df["cbbi"] - df["cbbi"].shift(3)  # entry
df["cbbi_mom_4d"] = df["cbbi"] - df["cbbi"].shift(4)  # exit

# Only drop rows where critical fields are NaN
critical_cols = ["sma200", "ema100", "ema200", "cbbi", "cbbi_mom_3d", "cbbi_mom_4d"]
df = df.dropna(subset=critical_cols)
print(f"Ready: {len(df)} daily rows, {df.index.min().date()} -> {df.index.max().date()}")

# ── Backtest engine ────────────────────────────────────────
def backtest(subset, lev_long=1.0, lev_short=0.0):
    bal = 10000.0
    pos = None  # (type, entry_px, leverage)
    fee = 0.001
    n_trades = 0

    for i in range(len(subset)):
        r = subset.iloc[i]
        px = r["close"]

        if pos:
            typ, ep, lev = pos
            pnl = (px - ep) / ep * lev if typ == "long" else (ep - px) / ep * lev

            # Exit conditions (same as CbbiMomentum + regime safety)
            if (r["cbbi_mom_4d"] < -0.03 or r["cbbi"] > 0.80
                    or r["ema100"] < r["ema200"]
                    or (typ == "long" and px < r["sma200"])
                    or (typ == "short" and px > r["sma200"])
                    or pnl < -0.15):
                bal *= (1 + pnl) * (1 - fee)
                pos = None; n_trades += 1
                continue

        if not pos and bal > 100:
            # Long: CBBI rising + not greedy + uptrend
            long_sig = (r["cbbi_mom_3d"] > 0 and r["cbbi"] < 0.65
                        and r["ema100"] > r["ema200"] and lev_long > 0)
            # Short: bear regime + CBBI falling + not already oversold
            short_sig = (lev_short > 0 and px < r["sma200"]
                         and r["cbbi_mom_3d"] < 0 and r["cbbi"] > 0.3)

            if long_sig:
                pos = ("long", px, lev_long)
            elif short_sig:
                pos = ("short", px, lev_short)

    if pos:
        typ, ep, lev = pos
        fp = subset.iloc[-1]["close"]
        pnl = (fp - ep) / ep * lev if typ == "long" else (ep - fp) / ep * lev
        bal *= (1 + pnl); n_trades += 1

    return (bal / 10000 - 1) * 100, n_trades

# ── Run all scenarios ──────────────────────────────────────
scenarios = [
    ("2022-2025 Full Cycle", "2022-01-01", "2025-12-31"),
    ("2023-2025 Bull Only",  "2023-01-01", "2025-12-31"),
    ("2022 Bear Market",     "2022-01-01", "2022-12-31"),
    ("2026 Q1 Grind Down",   "2026-01-01", "2026-04-20"),
]

configs = [
    ("Spot (1x, no short)",       1.0, 0.0),
    ("Lev Long (3x, no short)",   3.0, 0.0),
    ("Multi (3x long, 2x short)", 3.0, 2.0),
]

print(f"{'Period':<22} {'Config':<28} {'Return':>10}  Trades")
print("-" * 75)
for label, start, end in scenarios:
    sub = df.loc[start:end]
    if len(sub) < 50: continue
    for cname, ll, ls in configs:
        ret, nt = backtest(sub, ll, ls)
        print(f"{label:<22} {cname:<28} {ret:>9.1f}%  {nt:>4}")
