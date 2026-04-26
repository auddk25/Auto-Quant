[English](README.md) | [中文](README_zh.md)

# Auto-Quant

LLM-driven autonomous quantitative research. Apply Karpathy's autoresearch pattern to FreqTrade crypto strategies.

**Current recommended branch: `v0.4.0`**

## Research Findings (v0.4.0)

After 96 experiment rounds across 4 versions, here is what we learned.

### Strategy Performance

| Strategy | Indicators | Training (2023-25) | 2026 Q1 OOS |
|---|---|---|---|
| SmartHold (R90) | EMA50, EMA200, SMA200 | +427.1% | 0% ⭐ |
| CbbiLead (R98) | CBBI, EMA100, EMA200 | +289.4% | 0% ⭐ |
| EmaValuation (R94) | EMA100, EMA200, AHR999, CBBI | +173.7% | 0% ⭐ |
| Cycle01v2 (R97) | AHR999, CBBI, SMA200 | +87.6% | +3.4% ⭐ |
| Bear01 (R87) | SMA200, funding rate, stablecoin | +58.8% | 0% ⭐ |
| BuyAndHold | (benchmark) | +429.6% | -16.0% |

> BTC 2023-2025: $16k → $100k | BTC 2026 Q1: $94k → $76k (-16%)

### Key Findings

1. **No active strategy beats BuyAndHold in a bull market.** 2023-2025 was a 6x rally. Every entry delay costs return. The best strategies capture >95% of it by holding almost continuously.

2. **Bear protection is where active management wins.** In 2026 Q1 (-16% grind down), 4/6 strategies correctly stayed out (0% loss vs -16% benchmark). SMA200 entry filters and EMA death-cross exits proved effective.

3. **CBBI is the best single indicator.** Pure CBBI timing (buy when fearful <0.4, sell when greedy >0.75) achieved +289% in bulls with zero bear losses. It aggregates multiple on-chain metrics into one signal.

4. **Simplicity wins.** Strategies with 2-3 indicators outperform those with 5+. Every additional condition is an opportunity to miss a good trade.

5. **SMA200 is the most reliable bear filter.** Price below SMA200 consistently identified the 2026 bear regime. Entry filters work better than exit filters.

## How It Works

Four immutable pieces + one agent workspace:

- `config.json` — FreqTrade config. Pairs, timeframe, fees. Agent never touches this.
- `prepare.py` — Data download. Agent never touches this.
- `run.py` — Batch backtest oracle. Runs every strategy, prints metrics. Agent never touches this.
- `program.md` — Agent instructions. The loop lives here.
- `user_data/strategies/` — The directory the agent owns. Create, evolve, fork, kill strategies here.

## Project Structure

```
Auto-Quant/
├── README.md                           # this file
├── README_zh.md                        # 中文版
├── STRATEGY_MAP.md                     # strategy evolution & performance details
├── pyproject.toml
├── config.json                         # FreqTrade config (read-only)
├── prepare.py                          # data download (read-only)
├── run.py                              # training backtest (read-only)
├── val.py                              # OOS validation runner
├── program.md                          # agent instructions
├── user_data/
│   ├── strategies/
│   │   ├── _template.py.example
│   │   ├── MtfTrendSmartHold.py        # +427% bull, 0% bear
│   │   ├── MtfTrendCbbiLead.py         # CBBI-first +289%
│   │   ├── MtfTrendEmaValuation.py     # 4-indicator combo +174%
│   │   ├── MtfTrendCycle01.py          # AHR999+CBBI+SMA200 +88%
│   │   ├── MtfTrendBear01.py           # SMA200 bear guard
│   │   ├── BuyAndHold.py               # benchmark
│   │   └── .archive/                   # 38 archived experiments
│   ├── data/                           # training data (2023-2025)
│   └── data_val/                       # validation data (2026 Q1)
├── autoq_data/
│   ├── strategy_bridge.py              # macro factors (funding, DVOL, stablecoin)
│   └── cycle_bridge.py                 # AHR999 + CBBI indicators
├── prepare_cbbi.py                     # fetch CBBI data
├── prepare_ahr999.py                   # pre-compute AHR999
├── versions/                           # frozen snapshots of past runs
└── tests/                              # 13 tests, all passing
```

## Quick Start

```bash
# 1. Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install TA-Lib C library
#    macOS: brew install ta-lib
#    Linux: see https://github.com/mrjbq7/ta-lib#dependencies

# 3. Install Python deps
uv sync

# 4. Download data (Binance API required)
uv run prepare.py

# 5. Pre-fetch indicators
uv run prepare_cbbi.py
uv run prepare_ahr999.py

# 6. Sanity check
uv run run.py > run.log 2>&1

# 7. Run validation
uv run val.py
```

## Available Branches

| Branch | Status | Content |
|---|---|---|
| `v0.4.0` | **Recommended** | 6 strategies + OOS validation + CBBI/AHR999 indicators |
| `daily-trend` | Archive | Daily-timeframe strategies (DailyTrendEMA, R31-R81) |
| `autoresearch/apr22` | Archive | Automated batch experiment rounds 7-8 |
| `autoresearch/apr23` | Archive | Automated batch experiment rounds (R125) |
| `master` | Archive | v0.3.0 — 5-pair MTF portfolio |

## Version History

| Version | Rounds | Peak Sharpe | Key Innovation |
|---|---|---|---|
| v0.1.0 | 99 | 1.44 (true 0.19) | Single-file mutation, oracle-gaming discovered |
| v0.2.0 | 81 | 0.67 | Multi-strategy (3 slots), zero Goodhart |
| v0.3.0 | 39 | 1.07 | MTF + 5-pair portfolio, per-pair metrics |
| v0.4.0 | 98 | 0.16 (Sharpe) | CBBI/AHR999 indicators + 2026 Q1 OOS: 5/6 strategies beat benchmark |

See `versions/` for full retrospectives.

## License

MIT
