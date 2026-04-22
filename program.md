# Auto-Quant

This is an experiment to have the LLM do its own quantitative research.

An autonomous research loop: modify one strategy file, run a backtest, check if
results improved, keep or discard, and repeat. Over many iterations we're trying
to observe which patterns an LLM finds useful on this specific asset pair
(BTC/USDT + ETH/USDT @ 1h), not to deploy a profitable strategy.

## Setup

To set up a new experiment, work with the user to:

1. **Agree on a run tag**: propose a tag based on today's date (e.g. `mar5`).
   The branch `autoresearch/<tag>` must not already exist — this is a fresh run.
2. **Create the branch**: `git checkout -b autoresearch/<tag>` from current master.
3. **Read the in-scope files**. The repo is small. Read these files for full context:
   - `README.md` — repository context
   - `config.json` — fixed FreqTrade config (pairs, timeframe, fees). Do not modify.
   - `prepare.py` — data download. Do not modify.
   - `run.py` — the backtest oracle. Do not modify.
   - `user_data/strategies/AutoResearch.py` — **the file you modify**
4. **Verify data exists**: Check that `user_data/data/binance/BTC_USDT-1h.feather`
   and `ETH_USDT-1h.feather` exist. If not, tell the user to run `uv run prepare.py`.
5. **Initialize results.tsv**: Create `results.tsv` with just the header row.
   The baseline will be recorded after the first run.
6. **Confirm and go**: Confirm setup looks good with the user.

Once you get confirmation, kick off the experimentation.

## Experimentation

Each experiment runs a backtest on a **fixed timerange** (`20230101-20251231`)
over BTC/USDT and ETH/USDT at 1h. A single backtest takes roughly 10-60 seconds.

**What you CAN do:**
- Modify `user_data/strategies/AutoResearch.py`. Everything inside is fair game:
  indicators, entry/exit logic, class attributes (timeframe stays `1h`), ROI table,
  stoploss, trailing stop, custom exit logic, etc.

**What you CANNOT do:**
- Modify `prepare.py`, `run.py`, or `config.json`. These are the evaluation contract.
- `uv add` new dependencies. Use what's already in `pyproject.toml`
  (pandas, numpy, talib via TA-Lib, and anything else FreqTrade installs).
- Call the `freqtrade` CLI directly. The only way to run a backtest is via
  `uv run run.py`. This keeps everything reproducible and parseable.
- Modify the timerange or pair list.

**The goal**: get the highest `sharpe` on the `---` summary, subject to common
sense — a sharpe of 5 with 3 trades is not real signal. You should judge the
**full summary block** when deciding keep vs discard, not just sharpe.

**Simplicity criterion**: All else being equal, simpler is better. A small
improvement that adds ugly complexity is not worth it. Removing something and
getting equal or better results is a great outcome. When evaluating whether to
keep a change, weigh the complexity cost against the improvement magnitude.

**The first run**: Your very first run should always be to establish the baseline,
so you will run the backtest on the strategy as-is.

## Output format

Once `run.py` finishes it prints a summary like this:

```
---
strategy:         AutoResearch
commit:           abc1234
timerange:        20230101-20251231
sharpe:           1.234
sortino:          1.567
calmar:           0.892
total_profit_pct: 12.34
max_drawdown_pct: -8.91
trade_count:      142
win_rate_pct:     54.23
profit_factor:    1.67
pairs:            BTC/USDT,ETH/USDT
```

Extract the key metrics from the log file:

```bash
grep "^sharpe:\|^trade_count:\|^max_drawdown_pct:\|^total_profit_pct:" run.log
```

For a richer read, `grep "^---" -A 12 run.log` dumps the whole block.

## Logging results

When an experiment is done, log it to `results.tsv` (**tab**-separated, NOT
comma-separated — commas break in descriptions).

The TSV has a header row and 5 columns:

```
commit	sharpe	max_dd	status	description
```

1. git commit hash (short, 7 chars)
2. sharpe (e.g. 1.2340) — use 0.0000 for crashes
3. max_drawdown_pct as a positive number (e.g. 8.9 — absolute value)
4. status: `keep`, `discard`, or `crash`
5. short text description of what this experiment tried **and why you kept or discarded**

Example:

```
commit	sharpe	max_dd	status	description
a1b2c3d	0.823	12.4	keep	baseline: RSI<30 buy, RSI>70 sell
b2c3d4e	1.104	10.9	keep	add 50/200 SMA regime filter — only long in uptrend. Sharpe up 0.28, DD down.
c3d4e5f	0.412	18.2	discard	RSI threshold 40/60 — too many whipsaws, sharpe tanked
d4e5f6g	0.000	0.0	crash	added BB squeeze — NameError, talib.BBANDS signature mismatch
```

Do NOT commit `results.tsv` — leave it untracked. It is your journal across
`git reset` operations.

## The experiment loop

The experiment runs on a dedicated branch (e.g. `autoresearch/mar5`).

LOOP FOREVER:

1. Look at the git state: current branch, current commit
2. Tune `user_data/strategies/AutoResearch.py` with an experimental idea
3. `git commit -am "<short description>"`
4. Run the backtest: `uv run run.py > run.log 2>&1` (redirect everything — do
   NOT use tee or let output flood your context)
5. Read the summary: `grep "^---" -A 12 run.log` (or grep specific fields)
6. If the summary is empty or malformed, the run crashed. Run `tail -n 50 run.log`
   to read the Python stack trace and attempt a fix. If you can't get it to work
   after more than a few attempts, give up and revert.
7. **Decide keep or discard** by reading the full summary. Questions to consider:
   - Is the sharpe improvement real or noise? (sharpe 0.82 → 0.85 on 100 trades is
     probably noise; sharpe 0.82 → 1.30 with similar trade count is probably signal)
   - Is the trade count reasonable? (3 trades total means the strategy rarely
     triggers — not interpretable)
   - Is the drawdown acceptable? (a higher sharpe with 2× the drawdown might not
     be a real improvement)
   - Does the change make sense given your prior read on the asset?
8. Record the results in `results.tsv` with a description that explains BOTH the
   change and your reasoning for the keep/discard decision
9. If kept: the branch advances naturally (your commit stays). If discarded:
   `git reset --hard HEAD~1` to remove the commit.

The idea is that you are a completely autonomous researcher trying things out.
If an idea works, keep. If it doesn't, discard. Advance the branch to iterate.
If you feel stuck, you can rewind but do this very sparingly.

**Timeout**: Each backtest should take under a minute. If a run exceeds 5 minutes,
kill it and treat it as a failure (discard and revert).

**Crashes**: Use your judgment. Silly typos or wrong function signatures — fix
and re-run. Fundamentally broken ideas — log "crash" and move on.

**NEVER STOP**: Once the experiment loop has begun (after initial setup), do NOT
pause to ask the human if you should continue. Do NOT ask "should I keep going?"
or "is this a good stopping point?". The human may be asleep, or away from the
computer, and expects you to continue working *indefinitely* until manually
stopped. You are autonomous. If you run out of ideas, think harder — reread the
indicators you haven't tried, look at combining previous near-misses, try more
radical changes to entry/exit logic, experiment with different timeframes of
indicators (short RSI, long RSI), try mean-reversion vs momentum contrasts,
volatility filters, regime filters. The loop runs until the human interrupts you,
period.

As an example use case, a user might leave you running while they sleep. If each
experiment takes you ~1 minute then you can run several dozen per hour, for a
total of several hundred over the duration of an average human sleep. The user
then wakes up to experimental results, all completed by you while they slept.
