import urllib.request
import json
import pandas as pd
import numpy as np
from datetime import datetime

# 1. 离线/在线获取 CBBI 数据
def get_cbbi():
    print("正在抓取 CBBI 官方链上聚合指标...")
    req = urllib.request.Request(
        'https://colintalkscrypto.com/cbbi/data/latest.json', 
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*'
        }
    )
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode())
        # The JSON has nested keys: {"Confidence": {"12345": value}, "Price": {...}, ...}
        cbbi_series = data['Confidence']
        df = pd.DataFrame(list(cbbi_series.items()), columns=['ts', 'cbbi'])
        df['date'] = pd.to_datetime(pd.to_numeric(df['ts']), unit='s').dt.normalize()
        return df.groupby('date')['cbbi'].last()

# 2. 核心验证模型
def run_final_validation():
    # A. 加载价格与计算 AHR999
    df_1h = pd.read_feather("user_data/data/binance/BTC_USDT-1h.feather")
    df_1h['date'] = pd.to_datetime(df_1h['date']).dt.tz_localize(None)
    df = df_1h.resample('1D', on='date').agg({'close': 'last'})
    
    genesis_date = datetime(2009, 1, 3)
    df['days'] = (df.index - genesis_date).days
    df['log_line'] = 10**(5.8450937 * np.log10(df['days']) - 17.015931)
    df['sma200'] = df['close'].rolling(200).mean()
    df['ahr999'] = (df['close'] / df['sma200']) * (df['close'] / df['log_line'])
    
    # B. 合并 CBBI
    cbbi = get_cbbi()
    df = df.join(cbbi, how='left').ffill().dropna()
    
    # C. 模拟策略 (3倍杠杆版)
    balance = 10000.0
    leverage = 3.0
    position = 0 # 0 或 1
    entry_price = 0
    
    # 寻优后的参数
    X_BUY = 0.40
    Y_BUY = 10
    X1_SELL = 2.5
    Y1_SELL = 85
    
    print(f"\n--- R85 周期之神 (AHR999 + CBBI) 3.0x 杠杆验证 ---")
    for date, row in df.loc['2023-01-01':].iterrows():
        # 抄底逻辑: 价格在 200 日线下方且 AHR/CBBI 双低
        if position == 0:
            if row['ahr999'] < X_BUY and row['cbbi'] < Y_BUY:
                position = 1
                entry_price = row['close']
                print(f"[{date.date()}] 极寒时刻入场! BTC 价格: {entry_price:.0f} | AHR: {row['ahr999']:.2f} | CBBI: {row['cbbi']:.0f}")
        
        # 逃顶逻辑: 只要有一个指标触顶
        elif position == 1:
            if row['ahr999'] > X1_SELL or row['cbbi'] > Y1_SELL:
                pnl = (row['close'] - entry_price) / entry_price * leverage
                balance *= (1 + pnl)
                position = 0
                print(f"[{date.date()}] 巅峰狂欢离场! BTC 价格: {row['close']:.0f} | 结余: {balance:.0f} USDT")

    if position == 1:
        pnl = (df.iloc[-1]['close'] - entry_price) / entry_price * leverage
        balance *= (1 + pnl)
        
    print(f"\n最终回测成绩: {balance:.2f} USDT")
    print(f"总收益率: {(balance/10000 - 1)*100:.2f}%")

if __name__ == "__main__":
    run_final_validation()
