== Session: 2026-04-26 17:30 (R102 Final — Futures + Documentation) ==
## Completed
- R102: MtfTrendLongShort + config_futures.json — long/short strategy infrastructure
  Futures data downloaded, config ready. FreqTrade Binance futures API unstable.
  _simulator_cbbi.py daily-level validation: 3x leverage = +576%, shorts counterproductive.
- STRATEGY_MAP.md: added full pseudocode for all 4 active strategies
  Each strategy now has IF/THEN entry/exit logic, indicator prep steps, risk params, rationale.
  Added 8-step build guide with code snippets and acceptance criteria.
  Added archived strategies summary table with reasons.
- results.tsv: backfilled R86-R102 (was missing 17 rounds)
  Force-added to git (was gitignored per original design, user wants it tracked).
- README sync: updated both README.md and README_zh.md with R97-R98 results.
- Migrated claude-progress.txt → claude-progress.md per updated handoff skill format.

## Pending
- Fix FreqTrade Binance futures API for true long/short backtest
- Real 2026 Q2+ data download (requires ongoing Binance API access)
- Live trading test proposal

## Known Issues
- FreqTrade futures mode: "Ticker pricing not available for Binance" — need exchange config fix
- CBBI API (colintalkscrypto.com) returns HTTP 406; cached data through 2026-04-24 still usable
- config.json: spot-only, can_short=False, max_open_trades=1
==
== Session: 2026-04-26 17:00 (R100-R101 Full Cycle + Simulator) ==
## Completed
- R100: Extended data to 2022 (real bear market, BTC -65%)
  Full cycle: CbbiMomentum +732.7%, 14 trades, DD -2.9%, PF 10.2
- R101: _simulator_cbbi.py — leverage/short daily simulator
  3x leverage: +575.8%. Shorts: counterproductive in current cycle.
- val_rolling.py: expanded to 7 windows (2023 H1 through 2026 Q1)
- STRATEGY_MAP.md: complete with trade log, parameter matrix

## FINAL State (v0.4.0)
### Active (4): CbbiMomentum +732.7% ⭐ | SmartHold +92.8% | Bear01 +107.7% | BuyAndHold +88.5%
### CbbiMomentum: 3d/4d CBBI momentum, 14 trades, 64% WR, 10:1 PF, -2.9% DD
==
== Session: 2026-04-26 15:00 (R94-R99 CBBI + EMA + Parameter Optimization) ==
## Completed
- R94-R96: EmaValuation, EmaAhr, CbbiLead — CBBI/EMA/AHR999 combos (all later archived)
- R97: Cycle01v2 — SMA200 trend exit; 2026Q1: -16.5%→+3.4%
- R98: CbbiLead optimize — exit 0.70→0.75 (+38pp)
- R99v1-v4: CbbiMomentum evolution — CBBI absolute→momentum→3d/4d optimal
  10-group parameter scan: 3d entry + 4d exit confirmed best
  v4: +667.65% training, +40.93% rolling mean, 13 trades, PF 9.49
- Bear01 parameter sweep: 4 variants tested, current thresholds are optimal
- Final consolidation: 36→4 strategies
==
