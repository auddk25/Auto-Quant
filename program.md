# Auto-Quant v0.3.0 — multi-strategy + multi-timeframe autonomous research

This is an experiment to have the LLM do its own quantitative research across
**multiple parallel strategies** that can combine signals across **multiple
timeframes** (1h base + 4h + 1d).

The core bet of v0.2.0 was multi-strategy: maintaining up to 3 strategies in
parallel resisted single-paradigm anchoring. That worked — see
`versions/0.2.0/retrospective.md`. v0.3.0 adds multi-timeframe support on
top of that foundation: the hypothesis is that v0.2.0's peak Sharpe of 0.67
was constrained by 1h-only inputs, and letting strategies use 4h or 1d
context should unlock higher-quality signals.

## Setup

To set up a new experiment, work with the user to:

1. **Agree on a run tag**: propose a tag based on today's date (e.g. `may1`).
   The branch `autoresearch/<tag>` must not already exist.
2. **Create the branch**: `git checkout -b autoresearch/<tag>` from current `master`.
3. **Read the in-scope files**. The repo is small. Read these files for full context:
   - `README.md` — repository context
   - `config.json` — fixed FreqTrade config (pairs, timeframe, fees). Do not modify.
   - `prepare.py` — data download. Do not modify.
   - `run.py` — the batch backtest oracle. Do not modify.
   - `user_data/strategies/_template.py.example` — skeleton for new strategies.
     **Note:** the folder may also contain `__pycache__`; ignore it.
   - `versions/0.1.0/retrospective.md` and `versions/0.2.0/retrospective.md`
     — previous runs' findings. Both are valuable: v0.1.0 documents the
     single-paradigm anchoring failure mode + 3 Goodhart exploits the agent
     eventually rolled back. v0.2.0 documents the multi-strategy response
     and 5 paradigms tested (3 with clean positive edge).
4. **Verify data exists**: Check that all six data files exist under
   `user_data/data/`:
   - `BTC_USDT-1h.feather`, `BTC_USDT-4h.feather`, `BTC_USDT-1d.feather`
   - `ETH_USDT-1h.feather`, `ETH_USDT-4h.feather`, `ETH_USDT-1d.feather`

   If any are missing, tell the user to run `uv run prepare.py`.
5. **Initialize results.tsv**: Create `results.tsv` with just the header row:
   ```
   commit	event	strategy_name	sharpe	max_dd	note
   ```
   Tab-separated. Do not commit this file — it's gitignored on purpose.
6. **Create 1-3 starting strategies.** This is the most important setup step.
   - Each strategy goes in its own file: `user_data/strategies/<YourName>.py`
   - Class name MUST match filename stem (FreqTrade requirement)
   - Each strategy's docstring MUST fill all 6 metadata fields
     (Paradigm, Hypothesis, Parent, Created, Status, Uses MTF)
   - **Each strategy MUST target a different paradigm.** Don't create 3
     mean-reversion variants as a "safe start" — that defeats the whole point
     of v0.2.0+. Pick from: mean-reversion, trend-following, volatility,
     breakout, other. At least 2 different categories.
   - **Strongly encouraged**: at least one of the starting strategies should
     use the multi-timeframe affordance (see "Multi-timeframe" section below).
     Otherwise v0.3.0 doesn't exercise the new capability and we'll have
     learned nothing new vs v0.2.0. This is encouragement not mandate — if
     you have strong reasoning to make all 3 single-TF, write that reasoning
     in the notes.
   - Keep each strategy minimal initially. You'll iterate in the loop.
7. **Confirm and go**: Confirm setup looks good with the user.

Once you get confirmation, kick off the experimentation.

## Experimentation

Each round runs a backtest on ALL active strategies on a **fixed timerange**
(`20230101-20251231`) over BTC/USDT and ETH/USDT at 1h. `run.py` emits one
`---` summary block per strategy.

### What you CAN do

- Modify any file under `user_data/strategies/` (that isn't prefixed `_`)
- Create a new strategy file
- Delete a strategy file (via `git rm`)
- Copy an existing strategy to create a variant (fork)

### What you CANNOT do

- Modify `prepare.py`, `run.py`, or `config.json`. These are the evaluation
  contract.
- `uv add` new dependencies. Use what's already in `pyproject.toml`.
- Call the `freqtrade` CLI directly. The only way to run backtests is via
  `uv run run.py`.
- Modify the timerange, pair list, or `_template.py.example`.
- Have more than 3 active strategies at any time (see hard cap below).
- Request timeframes other than `1h`, `4h`, `1d` in `@informative` decorators.
  Only those three are pre-downloaded; anything else will crash the backtest
  with a missing-data error.

### Multi-timeframe affordance (new in v0.3.0)

Data is pre-downloaded for three timeframes: **1h (base), 4h, 1d**. Strategies
are always evaluated on the 1h base (this is set in `config.json` and cannot
change), but can pull context from 4h and 1d using FreqTrade's `@informative`
decorator.

**How to use it:**

```python
from freqtrade.strategy import IStrategy, informative

class YourStrategy(IStrategy):
    timeframe = "1h"
    # ... other attributes ...

    @informative("4h")
    def populate_indicators_4h(self, dataframe, metadata):
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    @informative("1d")
    def populate_indicators_1d(self, dataframe, metadata):
        dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
        return dataframe

    def populate_indicators(self, dataframe, metadata):
        # rsi_4h and ema200_1d are now merged into the 1h dataframe automatically
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe, metadata):
        # Example: MTF confluence entry
        dataframe.loc[
            (dataframe["rsi"] < 20)                        # 1h oversold
            & (dataframe["rsi_4h"] < 60)                   # 4h not overbought
            & (dataframe["close"] > dataframe["ema200_1d"]),  # 1d bull regime
            "enter_long",
        ] = 1
        return dataframe
```

**Key properties** (FreqTrade handles these for you):
- Column naming: `rsi` inside a `@informative('4h')` method becomes `rsi_4h` in the merged 1h dataframe
- Look-ahead safe: FreqTrade shifts merged data by 1 period so current 1h bar never sees future higher-TF bars
- Forward-filled: at any 1h bar, the merged `rsi_4h` value is the last fully-closed 4h bar's RSI

**When to use MTF:**
- Regime filters (`close > ema200_1d` for bull regime)
- Trend confirmation (`ema9_4h > ema21_4h` to confirm shorter TFs aren't fighting a bigger trend)
- Volatility context (`atr_4h` for relative-vol positioning)
- Anything where "the big picture" matters

**When NOT to use MTF:**
- Pure mean-reversion on 1h may not need higher TFs (v0.2.0's MeanRevBB was pure 1h and hit 0.52 Sharpe)
- If the paradigm doesn't have an intuitive higher-TF analog, don't force it

**`startup_candle_count`** — bump this up if you use slow indicators on higher TFs. EMA200 on 1d needs 200 daily bars = 4800 hourly bars of warmup. Starting at 250-300 is usually safe for most MTF configurations.

### Hard rules on strategy lifecycle

**Rule 1: Hard cap — 3 active strategies.**
At any moment, `user_data/strategies/` must contain at most 3 non-underscore
`.py` files. To add a 4th, you must first `git rm` one of the existing.

**Rule 2: Stagnation gate — 3 stable rounds.**
Each round, every strategy gets one of these events logged in `results.tsv`:
- `create` — you added it this round
- `evolve` — you modified it this round
- `stable` — it existed, got measured, but you didn't touch it
- `fork` — you copied it to create a derivative (logged on the child, with
  `parent→child` in the strategy_name field)
- `kill` — you removed it this round

**If a strategy has accumulated 3 consecutive `stable` events with no `evolve`
or `fork`, the next round it MUST receive one of: `evolve`, `fork`, or `kill`.**
Cannot sit idle for a 4th stable round. You decide which treatment. This rule
exists because the cap is 3 — we can't afford a slot sitting still.

**Rule 3: Every round must touch at least one strategy.**
A round where all events are `stable` is not an experiment — it's wasted time.
At minimum, evolve one strategy per round. (Exception: the very first backtest
round right after setup, where you log `create` events for what you built.)

**Rule 4: Paradigm diversity at setup.**
See setup step 6 above. First 1-3 strategies must target different paradigms.
After that, you're free to create same-paradigm variants (e.g. two
mean-reversion approaches with different signals) — but sparingly. Diversity
is more valuable than depth in this run.

## Output format

Once `run.py` finishes, stdout has one `---` block per strategy, like:

```
---
strategy:         MeanRevRSI
commit:           abc1234
timerange:        20230101-20251231
sharpe:           0.8234
sortino:          1.0412
calmar:           0.5821
total_profit_pct: 45.3210
max_drawdown_pct: -8.9123
trade_count:      142
win_rate_pct:     54.2300
profit_factor:    1.6700
pairs:            BTC/USDT,ETH/USDT

---
strategy:         TrendDonchian
commit:           abc1234
...
```

If a strategy crashes, its block looks like:
```
---
strategy:         SomeBrokenStrategy
commit:           abc1234
status:           ERROR
error_type:       NameError
error_msg:        name 'foo' is not defined
traceback:
  ...
```

Extract all strategies' metrics at once:
```bash
grep "^---\|^strategy:\|^sharpe:\|^trade_count:\|^max_drawdown_pct:" run.log
```

Full per-strategy block:
```bash
awk '/^---$/,/^$/' run.log
```

## Logging results

After each round, append one row to `results.tsv` **per strategy touched**.
Tab-separated, 6 columns:

```
commit	event	strategy_name	sharpe	max_dd	note
```

Rules:
- `commit` is the short git hash of the round's commit
- `event` is one of `create | evolve | stable | fork | kill`
- For `fork`, `strategy_name` uses `parent→child` format (e.g. `MeanRevRSI→MRVolGate`)
- For `kill`, leave `sharpe` and `max_dd` as `-` (dash). The strategy is gone.
- `note` is your reasoning in free text. This is load-bearing — when you
  later decide keep vs kill, you re-read these notes. Be specific:
  - Bad: `"tried MACD, didn't work"`
  - Good: `"replaced RSI entry with MACD cross-up. wr 68→51, sharpe 0.82→0.31. MACD crossovers on 1h crypto trigger inside ongoing drops, catching knives. Discarding paradigm."`
- Every strategy that exists this round gets a row, even if `stable`. This
  is how the stagnation counter stays visible.

**Do NOT commit `results.tsv`.** It is gitignored on purpose — the log
survives `git reset --hard`, which is essential so you don't forget what
you've already tried.

## The experiment loop

The experiment runs on the dedicated branch (e.g. `autoresearch/may1`).

LOOP FOREVER:

1. **Look at state**: read `results.tsv` (tail ~30 rows), note the current
   active strategies and their stagnation counters (how many consecutive
   `stable` events each has).

2. **Decide this round's action.** Your toolkit per round:
   - `evolve <strategy>`: modify an existing strategy file
   - `create <name>`: add a new strategy (if cap has room)
   - `fork <parent>→<child>`: cp a strategy file to a new name, then modify
     the child
   - `kill <strategy>`: `git rm` the file
   - You can combine: e.g. "kill A and create B in the same commit" (make room
     for something new), or "fork A→A' and evolve B" (two strategies touched)

3. **Respect the rules.** In particular:
   - Cap: max 3 active strategies after this round's changes
   - Stagnation: any strategy with 3 prior consecutive `stable` events must
     be evolved, forked, or killed THIS round
   - Every round touches ≥ 1 strategy

4. **Make the code changes.** Write/modify files under `user_data/strategies/`.

5. **`git commit -am "<short summary of this round>"`**

6. **Run the backtest**: `uv run run.py > run.log 2>&1`

7. **Read the summary**: `awk '/^---$/,/^$/' run.log` (shows all blocks) or
   `grep "^---\|^strategy:\|^sharpe:\|^trade_count:" run.log` (compact).

8. **Check for crashes**: a strategy with `status: ERROR` needs to be fixed
   (if the error is trivial — syntax, typo) OR killed (if the hypothesis is
   broken). Don't leave ERROR strategies around.

9. **Log to results.tsv**: one row per strategy that existed this round. Fill
   in the event, metrics (or `-` for kills), and your reasoning note.

10. **Decide keep vs rollback.**
    - Common case: per-strategy decisions happen inline (you either evolved
      to something better, or the change was bad and you git-reset only that
      strategy's commit). The whole round doesn't have one "keep/discard"
      decision — individual strategies do.
    - If the whole round was a mistake (broke everything, wrong direction),
      `git reset --hard HEAD~1` to undo all changes.
    - If some strategies improved and others didn't: keep the commit, log
      `stable` for the unchanged ones, log `evolve` or `kill` etc. for the
      changed ones.

11. **Loop.**

### Deciding keep vs kill on a strategy

A strategy deserves to stay if:
- It has positive edge (Sharpe > 0, profit factor > 1) with meaningful trade
  count (>20 trades over 3 years)
- Its paradigm is distinct from what the other active strategies cover
- Recent evolutions have moved it in the right direction

A strategy deserves to die if:
- It's been stable for 3 rounds with no improvement and you don't have a new
  idea for it
- Its paradigm overlaps strongly with another active strategy that's doing
  better
- You need its slot for a fresh paradigm you want to try
- It's consistently negative and further tweaks won't help (e.g. wrong
  timeframe for this paradigm)

**Always log your reasoning.** These notes become the retrospective —
future you (and the meta-analysis layer) will read them to extract what this
run actually learned about BTC/ETH 1h.

### Goodhart watch

From v0.1.0 we learned the agent can inadvertently game the metric:
- `exit_profit_only=True` → 100% win rate by never realizing losses
  (regime-dependent, breaks in bear markets)
- Tight `minimal_roi` clipping → tiny uniform returns → low stddev → huge
  Sharpe (profit goes DOWN even as Sharpe goes UP)

**v0.2.0 added zero new Goodhart exploits over 81 rounds — try to keep that streak.**

If you find a Sharpe jump that comes with a profit drop or a DD collapse to
~0, that's a gaming signal, not real edge. Log it, document the mechanism,
then either kill the strategy or explicitly note "this is an oracle artifact,
not edge" in the description.

Multi-strategy helps here: if strategy A's Sharpe jumps while B and C stay
flat on the same data, A's jump is more likely a real discovery. If ALL
three strategies' Sharpe jumped on the same commit — you probably modified
something shared, or the oracle itself has a hole.

**Timeout**: each full round (3 strategies × backtest) should take under 3
minutes. If a single run exceeds 10 minutes, kill it and treat it as a
failure (revert the commit, skip the round).

### NEVER STOP

Once the experiment loop has begun (after initial setup), do NOT pause to
ask the human if you should continue. Do NOT ask "should I keep going?" or
"is this a good stopping point?". The human may be asleep, or away from
the computer, and expects you to continue working *indefinitely* until
manually stopped.

If you run out of ideas:
- **Re-read `versions/0.1.0/retrospective.md` and `versions/0.2.0/retrospective.md`**
  — v0.1.0 listed directions it never tried (multi-timeframe was one!);
  v0.2.0 attempted 5 paradigms and identified specific plateau ceilings per paradigm
- Apply multi-timeframe to a stagnant strategy (if not using MTF yet) —
  that's literally the new affordance of v0.3.0
- Look at your stagnant strategies — can you fork them with a bolder change?
- Try combining winners from different paradigms (e.g. a volatility-gated
  version of a winning mean-reversion strategy)
- Try completely new indicator families you haven't touched
- Check v0.2.0's comparative findings (volume-filter universal, ATR
  paradigm-specific, regime-window paradigm-specific, ADX-lag universal) —
  see if any transfer to your current strategies in ways v0.2.0 never tested
  (e.g., 4h volume expansion instead of 1h)

The loop runs until the human interrupts you, period.

As an example use case, a user might leave you running while they sleep.
Each round of 3-strategy backtests takes ~2-3 minutes, so you can run several
dozen per hour. The user then wakes up to a rich multi-strategy research
trace ready for meta-analysis.
