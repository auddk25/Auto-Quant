"""One-shot: fetch CBBI data and cache as feather file for cycle_bridge.py."""
import urllib.request
import json
import pandas as pd
from pathlib import Path

CACHE_DIR = Path("user_data/data/_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_PATH = CACHE_DIR / "cbbi_daily.feather"

print("Fetching CBBI from colintalkscrypto.com...")
req = urllib.request.Request(
    "https://colintalkscrypto.com/cbbi/data/latest.json",
    headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    },
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        cbbi_data = json.loads(resp.read().decode())
except Exception as e:
    print(f"ERROR fetching CBBI: {e}")
    exit(1)

if "Confidence" in cbbi_data:
    cbbi_series = cbbi_data["Confidence"]
else:
    cbbi_series = cbbi_data

cbbi_df = pd.DataFrame(list(cbbi_series.items()), columns=["timestamp", "cbbi"])
cbbi_df["timestamp"] = pd.to_numeric(cbbi_df["timestamp"])
cbbi_df["date"] = pd.to_datetime(cbbi_df["timestamp"], unit="s").dt.normalize()
cbbi_df = cbbi_df.groupby("date")["cbbi"].last().reset_index()

cbbi_df.to_feather(str(CACHE_PATH))
print(f"CBBI cached: {len(cbbi_df):,} daily rows -> {CACHE_PATH}")
print(f"Date range: {cbbi_df['date'].min()} to {cbbi_df['date'].max()}")
