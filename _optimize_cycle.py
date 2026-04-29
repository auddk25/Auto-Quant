import urllib.request
import json
import pandas as pd
import numpy as np
from datetime import datetime

# 1. Fetch CBBI Data (It aggregates complex on-chain metrics like Pi Cycle, MVRV, etc.)
print("Fetching CBBI data from colintalkscrypto.com...")
req = urllib.request.Request(
    'https://colintalkscrypto.com/cbbi/data/latest.json', 
    headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/plain, */*'
    }
)
try:
    with urllib.request.urlopen(req) as response:
        cbbi_data = json.loads(response.read().decode())
        # The structure is {"Confidence": {"Timestamp": Value, ...}, ...} 
        # Let's inspect the keys to find the actual CBBI scores
        if 'Confidence' in cbbi_data:
            cbbi_series = cbbi_data['Confidence']
        else:
            # If it's a flat dict of timestamp: value
            cbbi_series = cbbi_data

        cbbi_df = pd.DataFrame(list(cbbi_series.items()), columns=['timestamp', 'cbbi'])
        cbbi_df['timestamp'] = pd.to_numeric(cbbi_df['timestamp'])
        cbbi_df['date'] = pd.to_datetime(cbbi_df['timestamp'], unit='s').dt.normalize()
        cbbi_df = cbbi_df.groupby('date')['cbbi'].last().reset_index()
        cbbi_df = cbbi_df.set_index('date')
        print("CBBI Data fetched successfully!")
except Exception as e:
    print(f"Failed to fetch CBBI: {e}")
    exit(1)

# 2. Load Local Price Data
print("Loading BTC price data...")
df_1h = pd.read_feather("user_data/data/binance/BTC_USDT-1h.feather")
df_1h['date'] = pd.to_datetime(df_1h['date']).dt.tz_localize(None)
df = df_1h.resample('1D', on='date').agg({'close': 'last'})

# 3. Calculate AHR999
# Note: AHR999 does not use on-chain data. It is a pure mathematical formula 
# based on the 200-day moving average and the exponential growth of Bitcoin's price over time.
# AHR999 = (Price / 200d_SMA) * (Price / Exponential_Growth_Line)
genesis_date = datetime(2009, 1, 3)
df['days_since_genesis'] = (df.index - genesis_date).days
df['log_growth_line'] = 10**(5.8450937 * np.log10(df['days_since_genesis']) - 17.015931)
df['sma200'] = df['close'].rolling(200).mean()
df['ahr999'] = (df['close'] / df['sma200']) * (df['close'] / df['log_growth_line'])

# Merge CBBI
df = df.join(cbbi_df, how='left')
df['cbbi'] = df['cbbi'].ffill() # Forward fill any missing daily CBBI

df = df.dropna()

# We test on the 2023-2026 cycle
df_test = df.loc['2023-01-01':'2026-04-20']

def test_strategy(df, buy_ahr, buy_cbbi, sell_ahr, sell_cbbi):
    balance = 10000.0
    position = 0 # 0 or 1
    entry_price = 0
    trades = 0
    
    for i in range(len(df)):
        row = df.iloc[i]
        
        # BUY: AHR999 < x AND CBBI < y
        if position == 0:
            if row['ahr999'] < buy_ahr and row['cbbi'] < buy_cbbi:
                position = 1
                entry_price = row['close']
                trades += 1
        
        # SELL: AHR999 > x1 AND CBBI > y1
        elif position == 1:
            if row['ahr999'] > sell_ahr and row['cbbi'] > sell_cbbi:
                profit = (row['close'] - entry_price) / entry_price
                balance *= (1 + profit)
                position = 0
                
    # Close out final position at the end to evaluate unrealized gains
    if position == 1:
        profit = (df.iloc[-1]['close'] - entry_price) / entry_price
        balance *= (1 + profit)
        
    return balance, trades

print("\nScanning for optimal long-term thresholds (Buy Low, Sell High)...")
results = []

# Buy variables: AHR < [0.3, 0.4, 0.5, 0.6], CBBI < [10, 20, 30, 40]
# Sell variables: AHR > [1.5, 2.0, 3.0, 4.0], CBBI > [60, 70, 80, 90]

for bx in np.arange(0.3, 0.7, 0.1):
    for by in np.arange(10, 50, 10):
        for sx in np.arange(1.5, 4.5, 0.5):
            for sy in np.arange(60, 95, 10):
                final_bal, trades = test_strategy(df_test, bx, by, sx, sy)
                if trades > 0:
                    results.append((bx, by, sx, sy, final_bal, trades))

best = sorted(results, key=lambda x: x[4], reverse=True)[:10]

print("\n--- TOP 10 OPTIMIZED CYCLICAL PARAMETERS (2023-2026) ---")
print(f"BuyAndHold Baseline: {df_test.iloc[-1]['close'] / df_test.iloc[0]['close'] * 10000:.2f} USDT")
print("-------------------------------------------------------------------------")
for r in best:
    ret = (r[4]/10000 - 1) * 100
    print(f"Buy(AHR<{r[0]:.2f} AND CBBI<{r[1]:.0f}) | Sell(AHR>{r[2]:.1f} AND CBBI>{r[3]:.0f}) | Return: {ret:>7.2f}% | Trades: {r[5]}")
