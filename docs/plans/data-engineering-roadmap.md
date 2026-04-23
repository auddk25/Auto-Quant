# AutoQuant Data Engineering Roadmap (v0.3.0)

## Objective
Upgrade the AutoQuant backtesting engine from a pure Price/Volume (Technical Analysis) framework to a compatibility-first Multi-Factor Macro/Micro structure. The operator workflow stays the same (`uv run prepare.py`, `uv run run.py`), but `prepare.py` now owns external factor ingestion and writes enriched sidecar feather files without breaking Freqtrade's fixed 6-column OHLCV loader.

## Tier 1: Immediate Integration (High Value, Deep History, Free)
These datasets are prepared alongside the canonical pair files Freqtrade already reads:
- `user_data/data/binance/BTC_USDT-1h.feather`
- `user_data/data/binance/ETH_USDT-1h.feather`

Canonical mirrored top-level copies under `user_data/data/` stay in sync for repo compatibility. Enriched sidecar files live under `user_data/data/_cache/enriched/binance/`.

1. **CVD (Cumulative Volume Delta) / Taker Volume**
   - **Source**: Binance Klines API (already present in standard OHLCV downloads as Taker Buy Base Asset Volume).
   - **Action**: Extend `prepare.py` / `autoq_data` to engineer `taker_buy_base_volume`, `taker_sell_base_volume`, `taker_delta_volume`, and rolling `cvd`.
2. **Funding Rate & Open Interest (Derivatives)**
   - **Source**: Binance Vision (Public Data Archives).
   - **Action**: Download historical 8h/1h funding rates and OI for BTCUSDT and ETHUSDT perpetuals. Merge to 1h timeframe using Forward Fill (`ffill`) where needed.
3. **Macro Liquidity (US10Y, DXY, Fed Net Liquidity)**
   - **Source**: `yfinance` (Yahoo Finance) and `pandas_datareader` (FRED).
   - **Action**: Fetch daily data. **Crucial**: Apply `shift(1)` before `ffill` merging to the 1h timeframe to strictly prevent Look-ahead Bias (future data leakage).

## Tier 2: High Value, Minor Limitations (Implement Now)
1. **Deribit Volatility Index (DVOL) - Crypto VIX**
   - **Source**: Deribit Public API.
   - **Limitation**: History only goes back to March 2021.
   - **Action**: Fetch 1h DVOL history. For backtests spanning pre-2021, fallback to standard ATR or set DVOL-based filters to pass-through.
2. **Stablecoin Total Market Cap**
   - **Source**: DefiLlama API.
   - **Action**: Fetch daily total stablecoin mcap (proxy for fiat inflows). Calculate daily growth rate (%). Apply `shift(1)` and `ffill` to 1h data.

## Tier 3: Future Considerations (Deferred)
*Reason for deferral: History too short, extremely expensive API costs, or prone to overfitting.*
1. **Spot BTC ETF Net Flows**: History starts Jan 2024. Too short for multi-year strategy training.
2. **On-Chain Data (LTH-MVRV, SOPR, NUPL)**: High quality, but historical API access (Glassnode/CryptoQuant) is prohibitively expensive for open-source automated research.
3. **Aggregated Liquidations**: Hard to compile historical data without paid services.

## Architecture Change in `prepare.py`
Currently, `prepare.py` fetches OHLCV via FreqTrade and then builds enriched sidecar datasets next to the canonical files.
**Proposed Flow:**
1. `download_ohlcv()` executes normally.
2. `download_external_factors()` fetches Tier 1 & 2 data locally into `user_data/data/_cache/`.
3. `merge_factors()` aligns all data on the 1h DatetimeIndex. Daily data is shifted by 1 day and forward-filled.
4. Final output keeps canonical per-pair `.feather` inputs at the original 6 OHLCV columns and writes enriched sidecar `.feather` files with the additional factor columns.
