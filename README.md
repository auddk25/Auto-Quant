# Auto-Quant

> LLM-native autonomous quant research loop. Karpathy's
> [autoresearch](https://github.com/karpathy/autoresearch) pattern applied to
> FreqTrade strategies on BTC/USDT + ETH/USDT @ 1h.

The idea: give an LLM agent a FreqTrade backtest harness and a single strategy
file. The agent modifies the strategy, runs a backtest, checks if the result
improved, keeps or discards, and repeats. Over many iterations the hope is to
observe which patterns the LLM actually finds useful on this asset pair. The
**loop lives in `program.md`** — not in any orchestrator — and is executed by
whatever LLM agent you point at the repo.

This is a prototype to validate whether Karpathy's autoresearch pattern
transfers to quant research. The success metric is "did the loop run and
produce an interpretable `results.tsv`", **not** "did we find a profitable
strategy". Nothing in this repo is a recommendation to trade real capital.

## How it works

Four files that matter:

- **`config.json`** — FreqTrade config, fixed. Pairs, timeframe, fees, dry-run
  wallet, timerange. The agent does not touch this.
- **`prepare.py`** — one-time data download from Binance via FreqTrade's Python
  API. The agent does not touch this.
- **`run.py`** — in-process backtest. Calls FreqTrade's `Backtesting` class
  directly (no CLI), extracts key metrics, prints a parseable `---` summary
  block to stdout. The agent does not touch this.
- **`user_data/strategies/AutoResearch.py`** — **the only file the agent edits**.
  Contains the full strategy: indicators, entry/exit logic, ROI/stoploss. This
  is the `train.py` equivalent of Karpathy's setup.

Plus:

- **`program.md`** — the autonomous-research instructions the human points the
  LLM agent at. Direct analog of Karpathy's `program.md`.
- **`results.tsv`** — the journal. `commit | sharpe | max_dd | status | description`.
  Git-ignored so it survives `git reset --hard` when the agent rolls back a
  failed experiment — past lessons stay available even when experimental
  commits get thrown away.
- **`analysis.ipynb`** — post-hoc read of `results.tsv` once the loop has
  collected some data.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- TA-Lib (the C library — installed separately from the Python binding)

## Install

```bash
# 1. Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install the TA-Lib C library
#    macOS:  brew install ta-lib
#    Linux:  see https://github.com/mrjbq7/ta-lib#dependencies
#    If native install is painful on your platform, the FreqTrade Docker
#    image ships with TA-Lib pre-built and works as an alternate runtime.

# 3. Install Python deps
uv sync

# 4. One-time data download (~a few minutes)
uv run prepare.py

# 5. Sanity check — run the baseline backtest
uv run run.py > run.log 2>&1 && grep "^---" -A 12 run.log
```

If step 5 prints a `---` block ending with a `pairs:` line, you're ready.

## Running the agent

Open a **second** terminal (keep your editor/IDE in the first so the two
sessions don't fight over the working tree), `cd` into the repo, and start
your preferred LLM agent (Claude Code, Codex, Cursor agent, etc.). Then
prompt something like:

> Have a look at `program.md` and let's kick off a new experiment. Let's do
> the setup first.

The agent reads `program.md`, goes through setup, then enters the experiment
loop. It keeps iterating until you interrupt it or it runs out of context.

### Permissions

The loop only works if the agent can run commands without a human approving
each one — it will invoke `uv run run.py`, `git commit`, `git reset`, and
edit the strategy file hundreds of times. How you grant that depends on your
tooling:

- **Claude Code**: prefer a scoped allowlist via a project-level
  `.claude/settings.json`. See the
  [permissions docs](https://docs.claude.com/en/docs/claude-code/settings#permissions)
  for patterns like `Bash(uv run *)` and `Bash(git commit:*)`.
- **Other agents**: most have an equivalent — a config flag or settings file
  to mark specific commands or tools as pre-approved.

Read the docs and choose a permission posture you're comfortable with before
leaving a loop running unattended. The agent is pointed at a sandboxed
FreqTrade workspace and has no live-trading access (all `dry_run`), but it
does run arbitrary shell commands and write files inside this directory.

## Project structure

```
Auto-Quant/
├── README.md
├── pyproject.toml                     # uv-managed deps
├── .python-version                    # 3.11
├── config.json                        # FreqTrade config (read-only for agent)
├── prepare.py                         # data download (read-only for agent)
├── run.py                             # backtest + summary (read-only for agent)
├── program.md                         # agent instructions
├── analysis.ipynb                     # post-hoc analysis
├── user_data/
│   ├── strategies/
│   │   └── AutoResearch.py            # THE one file the agent edits
│   ├── data/                          # gitignored — downloaded OHLCV
│   └── backtest_results/              # gitignored — FreqTrade outputs
└── results.tsv                        # gitignored — agent's journal
```

## Design notes

- **Agent only modifies one file.** All other files are the evaluation
  contract. This is the single biggest design decision; it keeps diffs
  reviewable and prevents Goodharting the metric.
- **No CLI indirection.** The agent only runs `uv run prepare.py` and
  `uv run run.py`. `run.py` uses FreqTrade's `Backtesting` class in-process,
  so startup is fast and errors surface as real Python stack traces.
- **`results.tsv` is gitignored.** When the agent reverts a failed
  experiment with `git reset --hard`, the journal of what was tried
  survives. Essential to avoid re-trying the same bad ideas.
- **LLM decides keep/discard, not a scalar rule.** Backtest Sharpe on a
  finite window is noisy. Rather than `if new_sharpe > old_sharpe: keep`,
  the agent reads the full summary block and decides based on sharpe +
  drawdown + trade count + its own read on the asset.

## License

MIT.
