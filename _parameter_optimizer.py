import pandas as pd
import numpy as np
import talib.abstract as ta
from datetime import datetime, timezone

def load_data():
    df_1h = pd.read_feather("user_data/data/binance/BTC_USDT-1h.feather")
    df_1h['date'] = pd.to_datetime(df_1h['date'])
    # Handle timezone: ensure both are UTC or both are naive
    df_1h['date'] = df_1h['date'].dt.tz_localize(None) 
    df = df_1h.resample('1D', on='date').agg({'close': 'last', 'high': 'max', 'low': 'min'})
    
    # 1. AHR999 Calculation
    genesis_date = datetime(2009, 1, 3) # Naive
    df['days_since_genesis'] = (df.index - genesis_date).days
    df['log_growth_line'] = 10**(5.8450937 * np.log10(df['days_since_genesis']) - 17.015931)
    df['sma200'] = df['close'].rolling(200).mean()
    df['ahr999'] = (df['close'] / df['sma200']) * (df['close'] / df['log_growth_line'])
    
    # 2. CBBI Proxy
    df['sma350'] = df['close'].rolling(350).mean()
    df['cbbi_proxy'] = (df['close'] / df['sma350']) * 20 
    df['rsi_1d'] = ta.RSI(df, timeperiod=14)
    df['macro_osc'] = (df['cbbi_proxy'] * 0.7 + df['rsi_1d'] * 0.3)
    
    return df.dropna()

def test_strategy(df, buy_x, buy_y, sell_x1, sell_y1):
    balance = 10000.0
    position = 0 
    entry_price = 0
    
    for i in range(len(df)):
        row = df.iloc[i]
        if position == 0:
            if row['ahr999'] < buy_x and row['macro_osc'] < buy_y:
                position = 1
                entry_price = row['close']
        elif position == 1:
            if row['ahr999'] > sell_x1 or row['macro_osc'] > sell_y1:
                profit = (row['close'] - entry_price) / entry_price
                balance *= (1 + profit)
                position = 0
                
    if position == 1:
        profit = (df.iloc[-1]['close'] - entry_price) / entry_price
        balance *= (1 + profit)
        
    return balance

df = load_data()
df_train = df.loc['2023-01-01':'2025-12-31']

results = []
print("Scanning optimized thresholds for BTC Cycle...")
for bx in np.arange(0.4, 0.9, 0.1):
    for by in np.arange(25, 45, 5):
        for sx in np.arange(1.2, 5.0, 0.5): # Finer grain for peak
            for sy in np.arange(70, 95, 5):
                final = test_strategy(df_train, bx, by, sx, sy)
                results.append((bx, by, sx, sy, final))

best = sorted(results, key=lambda x: x[4], reverse=True)[:5]
print("\n--- OPTIMIZED BTC LONG-TERM THRESHOLDS ---")
for r in best:
    print(f"ENTRY: AHR999 < {r[0]:.2f} & CBBI < {r[1]:.0f} | EXIT: AHR999 > {r[2]:.1f} OR CBBI > {r[3]:.0f} | Return: {(r[4]/10000-1)*100:.2f}%")
