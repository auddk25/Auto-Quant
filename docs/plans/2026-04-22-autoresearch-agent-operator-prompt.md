# AutoResearch Operator Prompt

This document is for handing `E:\code\AutoQuant` to another coding agent and making it do real experimental work instead of talking about work.

## Copy-Paste Prompt

Use the prompt below as-is.

```text
You are taking over an active autoresearch run in E:\code\AutoQuant.

Your job is not to discuss ideas. Your job is to execute real experiments.

You must continue the research loop on the current branch and keep going until interrupted. Do not stop to ask whether to continue. Do not pause after a few runs. Do not switch into planning-only mode.
You must also obey the hard session-rotation rule in `program.md`: each agent session stops after 100 newly logged experiments, then a fresh session rereads the repo state and continues.

Read these files first:
- README.md
- program.md
- claude-progress.txt
- results.tsv
- user_data/strategies/AutoResearch.py

Environment facts you must respect:
- Use the existing virtualenv at `.venv`
- On this machine, use `.\.venv\Scripts\python.exe` instead of assuming `uv run` works
- Data already exists and `prepare.py` is already passing
- Git safe.directory may be problematic globally, so prefer:
  `git -c safe.directory=E:/code/AutoQuant ...`

Current state:
- Active branch: `autoresearch/apr22`
- Current best kept commit: `80d21b5`
- Fresh verified metrics on `80d21b5`:
  - sharpe: 0.0223
  - total_profit_pct: 1.0291
  - max_drawdown_pct: -11.7194
  - trade_count: 121
- Do not switch back to `master`. Continue on the active `autoresearch/*` branch.

Hard rules:
1. Only modify `user_data/strategies/AutoResearch.py`.
2. Do not modify `prepare.py`, `run.py`, or `config.json`.
3. Every experiment must include a real code change, a real git commit, a real backtest run, and a real `results.tsv` row.
4. If you have not produced a new commit hash and a new parsed `---` summary block from `run.py`, then you did not complete an experiment.
5. Do not batch many code ideas into one experiment. One experiment = one coherent change set.
6. Do not claim “this should help” without running the backtest.
7. Do not leave discarded experiments on the branch. Record them in `results.tsv`, then `git reset --hard HEAD~1`.
8. If a run crashes, inspect `run.log`, fix obvious implementation mistakes if the idea still makes sense, rerun once, and if it still fails record `crash` and move on.
9. Keep `results.tsv` uncommitted.
10. Prefer simple strategy logic over complexity unless the metrics clearly justify complexity.
11. Stop the current session after 100 newly logged experiments. Do not continue in the same long-lived context past that boundary.
12. Before stopping at the 100-experiment boundary, update `claude-progress.txt` with the current branch, best commit, best metrics, failed directions, and next directions.
13. The next session must start fresh by rereading `README.md`, `program.md`, `claude-progress.txt`, `results.tsv`, and the current strategy file before doing any new experiment.

Definition of done for each experiment:
- `user_data/strategies/AutoResearch.py` changed
- committed to git
- `.\.venv\Scripts\python.exe run.py > run.log 2>&1` executed
- summary parsed from `run.log`
- one new line appended to `results.tsv`
- branch either keeps the commit or resets it

Definition of done for each session batch:
- 100 new experiment rows have been added to `results.tsv` in this session
- `claude-progress.txt` has been updated for handoff
- the session stops cleanly so a fresh agent can continue

Loop exactly like this:
1. Inspect current branch head and latest rows in `results.tsv`
2. Choose one concrete strategy idea
3. Edit only `user_data/strategies/AutoResearch.py`
4. Commit it with a short message
5. Run:
   `.\.venv\Scripts\python.exe run.py > run.log 2>&1`
6. Parse the full summary block from `run.log`
7. Decide keep or discard based on sharpe, total profit, max drawdown, profit factor, and trade count
8. Append one tab-separated row to `results.tsv`:
   `commit	sharpe	max_dd	status	description`
9. If discard: `git reset --hard HEAD~1`
10. If this session has logged fewer than 100 new experiments, start the next experiment immediately
11. If this session has logged 100 new experiments, update `claude-progress.txt` and stop. A fresh session must continue.

Guardrails against fake progress:
- Do not spend multiple messages “thinking” without producing experiments
- Do not summarize broad strategy categories unless you already ran them
- Do not rewrite a plan the repo already has in `program.md`
- Do not keep one bloated session alive forever; stop at the 100-experiment session boundary
- At any point, the user should be able to open `results.tsv` and see that the line count is increasing because you actually ran things

What counts as a good experiment:
- It changes one or two related levers only
- It is motivated by the previous results, not random churn
- It produces enough trades to be interpretable
- It either improves utility meaningfully or teaches something specific

What counts as failure:
- Talking about what you might test next without testing it
- Editing strategy code without committing and running it
- Running backtests without recording the result
- Keeping bad commits on the branch
- Asking the user whether to continue before being interrupted

Suggested next search directions from the first 100 experiments:
- Refine the current winning family around `EMA200 + RSI(21) + lower Bollinger band`
- Sweep exit logic around `bb_middle`, `ema20`, and hybrid exits
- Test narrower entry bands around the current profitable regime rather than jumping to unrelated indicators
- Explore stoploss and ROI around the current winner in small increments
- Try regime-sensitive exits before trying brand-new entry systems

Start now. Do not restate this prompt back to the user. Produce actual experiments.
```

## Operator Notes

The prompt above is deliberately strict because the common failure mode is fake progress:

- The agent proposes ideas instead of running them.
- The agent edits code but does not commit and backtest each iteration.
- The agent gives status updates that are not backed by a new row in `results.tsv`.

If you want a simple acceptance test for whether the agent is behaving correctly, use this:

1. Open `results.tsv`.
2. Wait 10 to 20 minutes.
3. Open it again.

If the line count is not increasing and the descriptions are not changing, the agent is not actually doing the job.

## Known Environment Notes

- This machine already has a working environment.
- `prepare.py` and `run.py` are working through the existing `.venv`.
- `aiodns` and `pycares` were removed from the virtualenv because they broke DNS resolution for Binance in this Windows environment.
- The current strategy file is the profitable `80d21b5` variant and is the right starting point for further search.

## Expected Command Set

These are the commands the agent should be using repeatedly:

```powershell
git -c safe.directory=E:/code/AutoQuant status --short --branch
git -c safe.directory=E:/code/AutoQuant rev-parse --short HEAD
Get-Content results.tsv -Tail 10
.\.venv\Scripts\python.exe run.py > run.log 2>&1
Get-Content run.log | Select-String "^---|^strategy:|^commit:|^timerange:|^sharpe:|^sortino:|^calmar:|^total_profit_pct:|^max_drawdown_pct:|^trade_count:|^win_rate_pct:|^profit_factor:|^pairs:"
git -c safe.directory=E:/code/AutoQuant commit -am "<experiment message>"
git -c safe.directory=E:/code/AutoQuant reset --hard HEAD~1
```

## Current Benchmark

The current benchmark the next agent should try to beat is:

- Commit: `80d21b5`
- Sharpe: `0.0223`
- Total profit: `1.0291%`
- Max drawdown: `11.7194%`
- Trade count: `121`

Beating this means more than just a tiny Sharpe bump with 5 trades. The replacement should still be interpretable and should not explode drawdown.
