import pandas as pd
import numpy as np
import talib.abstract as ta

def load_data():
    df_1h = pd.read_feather("user_data/data/binance/BTC_USDT-1h.feather")
    df_1h['date'] = pd.to_datetime(df_1h['date'])
    df_1h = df_1h.set_index('date')
    
    # Daily aggregation
    df = df_1h.resample('1D').agg({
        'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
    })
    
    # INDICATORS (Shifted to prevent look-ahead bias)
    df['sma200'] = ta.SMA(df, timeperiod=200).shift(1)
    df['ema20'] = ta.EMA(df, timeperiod=20).shift(1)
    df['adx'] = ta.ADX(df, timeperiod=14).shift(1)
    df['vol_std'] = df['close'].pct_change().rolling(7).std().shift(1) # 7-day vol
    
    macd = ta.MACD(df)
    df['macd_hist'] = macd['macdhist'].shift(1)
    
    return df.dropna()

def run_multiregime_backtest(df, start_bal=10000.0):
    balance = start_bal
    position = None # (type: 'long'/'short', amt, entry_price, leverage)
    slip_fee = 0.0012 # Balanced futures fee + slip
    
    for i in range(len(df)):
        row = df.iloc[i]
        current_price = row['close']
        
        # 1. CURRENT POSITION MANAGEMENT
        if position:
            p_type, p_amt, p_entry, p_lev = position
            
            # Calculate Unrealized PnL
            if p_type == 'long':
                pnl_ratio = (current_price - p_entry) / p_entry * p_lev
            else:
                pnl_ratio = (p_entry - current_price) / p_entry * p_lev
            
            # --- EXIT LOGIC ---
            exit_triggered = False
            exit_reason = ""
            
            # A. Short Stoploss (User's absolute rule)
            if p_type == 'short' and pnl_ratio < -0.05:
                exit_triggered = True
                exit_reason = "Short_SL"
            
            # B. Volatility Flush (Panic)
            elif row['vol_std'] > 0.05:
                exit_triggered = True
                exit_reason = "Panic_Exit"
                
            # C. Regime Reversal
            elif p_type == 'long' and current_price < row['sma200']:
                exit_triggered = True
                exit_reason = "Bull_End"
            elif p_type == 'short' and current_price > row['sma200']:
                exit_triggered = True
                exit_reason = "Bear_End"
                
            if exit_triggered:
                balance = balance * (1 + pnl_ratio) * (1 - slip_fee)
                position = None
                continue

        # 2. ENTRY LOGIC (If flat)
        if not position and balance > 100:
            # Check Volatility first
            if row['vol_std'] > 0.04: continue
            
            # MODE A: Bull Market
            if current_price > row['sma200']:
                # Sub-mode: Leverage (Strong ADX) or Spot (Weak ADX)
                lev = 3.0 if row['adx'] > 25 else 1.0
                p_type = 'long'
                position = (p_type, None, current_price, lev)
            
            # MODE B: Bear Market
            elif current_price < row['sma200'] and row['macd_hist'] < 0:
                p_type = 'short'
                lev = 2.0 # Conservative short leverage
                position = (p_type, None, current_price, lev)

    # Final valuation
    if position:
        p_type, p_amt, p_entry, p_lev = position
        if p_type == 'long':
            pnl_ratio = (df.iloc[-1]['close'] - p_entry) / p_entry * p_lev
        else:
            pnl_ratio = (p_entry - df.iloc[-1]['close']) / p_entry * p_lev
        balance = balance * (1 + pnl_ratio)

    return balance

df_full = load_data()
df_train = df_full.loc['2023-01-01':'2025-12-31']
df_val = df_full.loc['2026-01-01':'2026-04-20']

train_res = run_multiregime_backtest(df_train)
val_res = run_multiregime_backtest(df_val)

print(f"--- R84 Multi-Regime Matrix (Leverage + Short + Spot) ---")
print(f"Training (2023-2025) Return: {(train_res/10000 - 1)*100:.2f}%")
print(f"Validation (2026) Return: {(val_res/10000 - 1)*100:.2f}%")
