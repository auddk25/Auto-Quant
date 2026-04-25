"""One-shot: pre-compute AHR999 for BTC daily and cache as feather file."""
import pandas as pd
import numpy as np

GENESIS = pd.Timestamp("2009-01-03", tz="UTC")

# Load BTC daily
df = pd.read_feather("user_data/data/binance/BTC_USDT-1d.feather")
df["date"] = pd.to_datetime(df["date"])
if df["date"].dt.tz is None:
    df["date"] = df["date"].dt.tz_localize("UTC")
else:
    df["date"] = df["date"].dt.tz_convert("UTC")

# Compute SMA200
df["sma200"] = df["close"].rolling(200).mean()

# Compute AHR999
days = (df["date"] - GENESIS).dt.days.astype(float)
log_growth = 10.0 ** (5.8450937 * np.log10(days.clip(lower=1)) - 17.015931)
df["ahr999"] = (df["close"] / df["sma200"]) * (df["close"] / log_growth)

# Cache
out = df[["date", "ahr999", "sma200"]].dropna()
out_path = "user_data/data/_cache/ahr999_daily.feather"
out.to_feather(out_path)
print(f"AHR999 cached: {len(out):,} daily rows -> {out_path}")
print(f"Date range: {out['date'].min()} to {out['date'].max()}")
print(f"ahr999 range: {out['ahr999'].min():.4f} to {out['ahr999'].max():.4f}")
print(f"ahr999 < 0.45 count: {(out['ahr999'] < 0.45).sum()} / {len(out)}")
