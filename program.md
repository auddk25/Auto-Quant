# Auto-Quant v0.4.0 — multi-timeframe trend + alternative data

v0.4.0 combines the best findings from all prior versions:

- v0.1.0-v0.2.0: mean-reversion strategies hit parameter ceiling (125 rounds)
- v0.3.0: MTF + cross-pair breakout achieved Sharpe 1.07
- daily-trend branch: breakeven stop pattern + daily EMA crossover (Sharpe 0.86)
- autoq_data module: 6 alternative data sources beyond pure TA

## Core Innovation

Multi-timeframe strategy with alternative data integration:

- **Daily (1d)**: EMA trend direction + macro factors (funding rate, net liquidity, stablecoin growth) determine regime
- **4-hour (4h)**: Technical signals (BB reversion, RSI oversold) find precise entry points within daily trend
- **Exit**: Daily EMA death cross OR breakeven stop (-5% after 30% profit peak)

## Architecture

### Data Sources (autoq_data module)

| Source | Type | Signal |
|--------|------|--------|
| spot_klines | Exchange | Taker buy/sell volume, CVD |
| funding_rate | Derivatives | Perpetual funding rate (sentiment) |
| open_interest | Derivatives | Open interest (leverage level) |
| macro_liquidity | Macro | US10Y, DXY, Fed net liquidity |
| dvol | Volatility | Deribit BTC implied volatility |
| stablecoins | On-chain | Stablecoin total mcap + growth rate |

### Strategy Design

Each strategy uses FreqTrade @informative decorators for MTF:

```python
@informative("1d")
def populate_indicators_1d(self, dataframe, metadata):
    # Daily trend + macro regime filter

@informative("4h")
def populate_indicators_4h(self, dataframe, metadata):
    # 4h entry signals (BB, RSI, etc.)

def populate_indicators(self, dataframe, metadata):
    # 1h base - merge external factors from autoq_data
```

### Pairs and Timeframes

Pairs: BTC/USDT, ETH/USDT (2 pairs only)
Base timeframe: 1h
Informative timeframes: 4h, 1d
Timerange: 20230101-20251231
Exchange: Binance (spot)

## Experiment Rules

- Max 3 active strategies at any time
- Strategies go in user_data/strategies/<Name>.py
- Class name must match filename
- Run backtests via: uv run run.py > run.log 2>&1
- Log results to results.tsv (gitignored, survives git reset)
- Events: create, evolve, stable, fork, kill
- 3 consecutive stable rounds forces evolve/fork/kill
- Each round must touch at least one strategy

## Proven Patterns (from prior versions)

- Breakeven stop: -5% after 30% profit peak (daily-trend R52-R55, Sharpe 0.71->0.86)
- EMA crossover for daily trend: EMA40/120 and EMA50/150 both work
- Factor gates: funding_rate + stablecoin_growth protect BTC entries in bear markets
- exit_profit_only=True is a Goodhart trap in bear markets (v0.1.0 lesson)
- Mean-reversion ceiling: 28% return vs 427% buy-and-hold over 3 years
- Tighter stoploss kills mean-reversion (needs room to recover)
- Volume filter improves Sharpe but removes too many trades

## Dead Ends (do not retry)

- close > EMA50 AND close < BB_lower are structurally incompatible
- bb_upper exit doubles DD for mean-reversion
- ETH does not benefit from stablecoin gates
- Entry/exit oscillators must be paired (RSI+stoch = mismatch)
- Breakeven stop does NOT transfer from daily to 1h timeframe
- Trailing stop underperforms breakeven stop on daily

## Workflow

1. Download data: HTTPS_PROXY=http://127.0.0.1:7897 uv run prepare.py
2. Create/modify strategies in user_data/strategies/
3. Commit changes: git commit -am 'R<N>: description'
4. Run backtest: uv run run.py > run.log 2>&1
5. Read results: awk '/^---$/,/^$/' run.log
6. Log to results.tsv
7. Decide keep vs revert
8. Loop

## File Structure

- config.json: FreqTrade config (2 pairs, 1h base, proxy enabled)
- prepare.py: Data download (BTC/ETH x 1h/4h/1d)
- run.py: Backtest oracle (discovers strategies, reports per-pair metrics)
- program.md: This file (v0.4.0 plan)
- autoq_data/: Alternative data pipeline (6 sources)
- user_data/strategies/: Active strategy files
- user_data/strategies/_template.py.example: Strategy skeleton
- versions/: Archived results from prior versions
- tests/: Data pipeline tests
- claude-progress.txt: Session progress log
