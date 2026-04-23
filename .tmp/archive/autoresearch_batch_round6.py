from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import textwrap
from copy import deepcopy
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
STRATEGY_PATH = REPO / "user_data" / "strategies" / "AutoResearch.py"
RESULTS_PATH = REPO / "results.tsv"
RUN_LOG_PATH = REPO / "run.log"
STATE_PATH = REPO / ".tmp" / "autoresearch_state_round6.json"
SAFE_GIT = ["git", "-c", "safe.directory=E:/code/AutoQuant"]
RUNNER = [str(REPO / ".venv" / "Scripts" / "python.exe"), "run.py"]

INITIAL_PARAMS = {
    "rsi_period": 20,
    "rsi_entry": 39,
    "rsi_exit": 60,
    "roi": 0.0075,
    "stoploss": -0.08,
    "bb_period": 25,
    "bb_dev": 2.18,
    "trend_mode": "ema200",
    "pullback_mode": "bb_lower",
    "entry_buffer": 0.997,
    "bbmid_exit_buffer": 1.0,
    "exit_mode": "rsi_and_bbmid",
    "require_rsi_rising": False,
    "require_green_candle": False,
    "require_close_above_ema50": False,
    "require_ema20_above_ema50": False,
    "adx_min": 0.0,
    "bb_width_min": 0.0,
    "bb_width_max": 999.0,
    "mfi_max": 100.0,
    "cci_max": 999.0,
    "atr_pct_min": 0.0,
    "trailing_stop": False,
    "trailing_stop_positive": 0.0,
    "trailing_stop_positive_offset": 0.0,
    "trailing_only_offset_is_reached": False,
    "use_exit_signal": True,
    "exit_profit_only": False,
    "ignore_roi_if_entry_signal": True,
}

INITIAL_BEST = {
    "commit": "a566569",
    "sharpe": 0.4836,
    "total_profit_pct": 19.0141,
    "max_drawdown_pct": -4.0548,
    "trade_count": 76,
    "profit_factor": 3.0178,
    "utility": 0.633193,
}


def _candidate_specs() -> list[dict]:
    specs: list[dict] = []

    def add(label: str, rationale: str, **updates) -> None:
        specs.append({"label": label, "rationale": rationale, "updates": updates})

    adx_values = [14, 16, 18, 20, 22]
    mfi_values = [25, 30, 35, 40, 45]
    cci_values = [-80, -100, -120, -140, -160]
    bb_width_values = [0.020, 0.025, 0.030, 0.035, 0.040]
    atr_pct_values = [0.010, 0.012, 0.014, 0.016]
    adx_entries = [(39, 0.9970), (40, 0.9970), (40, 0.9972), (41, 0.9970), (41, 0.9972)]
    confirm_entries = [(38, 0.9968), (39, 0.9970), (40, 0.9970)]
    volatility_entries = [(39, 0.9970), (40, 0.9970), (40, 0.9972)]
    atr_entries = [(39, 0.9970), (40, 0.9970), (41, 0.9970)]

    # Single probes for genuinely new filter families.
    add("single_adx16", "require a modest ADX floor to keep only stronger-trend pullbacks", adx_min=16)
    add("single_adx18", "raise the ADX floor a bit more to focus on stronger-trend pullbacks", adx_min=18)
    add("single_adx20", "test a clear trend-strength floor before entering mean reversion", adx_min=20)
    add("single_bbw0025", "require minimum Bollinger width so entries avoid flat volatility regimes", bb_width_min=0.025)
    add("single_bbw0030", "raise minimum Bollinger width to avoid quieter mean-reversion setups", bb_width_min=0.030)
    add("single_bbw0035", "test a higher Bollinger-width floor for only broader pullbacks", bb_width_min=0.035)
    add("single_mfi35", "require money-flow oversold confirmation before entering", mfi_max=35)
    add("single_mfi30", "require deeper money-flow oversold confirmation before entering", mfi_max=30)
    add("single_cci100", "require CCI to show a clear downside extension before entering", cci_max=-100)
    add("single_cci120", "require even deeper CCI downside extension before entering", cci_max=-120)
    add("single_atr0012", "require a minimum ATR percent so trades only happen in active volatility", atr_pct_min=0.012)
    add("single_atr0014", "raise the ATR percent floor to focus on more active pullbacks", atr_pct_min=0.014)

    # Looser entries rescued by trend-strength filters.
    for adx_min in adx_values:
        for rsi_entry, entry_buffer in adx_entries:
            if adx_min == 20 and rsi_entry == 39 and entry_buffer == 0.9970:
                continue
            add(
                f"adx{adx_min}_e{rsi_entry}_buf{str(entry_buffer).replace('.', '')}",
                "combine a looser entry with an ADX trend-strength floor to see if stronger trends rescue quality",
                adx_min=adx_min,
                rsi_entry=rsi_entry,
                entry_buffer=entry_buffer,
            )

    # Money-flow oversold confirmation around the winner family.
    for mfi_max in mfi_values:
        for rsi_entry, entry_buffer in confirm_entries:
            add(
                f"mfi{mfi_max}_e{rsi_entry}_buf{str(entry_buffer).replace('.', '')}",
                "require money-flow oversold confirmation while retuning entry tightness around the winner",
                mfi_max=mfi_max,
                rsi_entry=rsi_entry,
                entry_buffer=entry_buffer,
            )

    # CCI downside extension confirmation around the winner family.
    for cci_max in cci_values:
        for rsi_entry, entry_buffer in confirm_entries:
            add(
                f"cci{str(cci_max).replace('-', 'n')}_e{rsi_entry}_buf{str(entry_buffer).replace('.', '')}",
                "require CCI downside extension confirmation while retuning entry tightness around the winner",
                cci_max=cci_max,
                rsi_entry=rsi_entry,
                entry_buffer=entry_buffer,
            )

    # Volatility width filters around base and looser entries.
    for bb_width_min in bb_width_values:
        for rsi_entry, entry_buffer in volatility_entries:
            add(
                f"bbw{str(bb_width_min).replace('.', '')}_e{rsi_entry}_buf{str(entry_buffer).replace('.', '')}",
                "require minimum Bollinger width to avoid dead volatility regimes while retuning entry tightness",
                bb_width_min=bb_width_min,
                rsi_entry=rsi_entry,
                entry_buffer=entry_buffer,
            )

    # ATR percent filters around base and looser entries.
    for atr_pct_min in atr_pct_values:
        for rsi_entry, entry_buffer in atr_entries:
            add(
                f"atr{str(atr_pct_min).replace('.', '')}_e{rsi_entry}_buf{str(entry_buffer).replace('.', '')}",
                "require a minimum ATR percent to keep only more active pullback regimes",
                atr_pct_min=atr_pct_min,
                rsi_entry=rsi_entry,
                entry_buffer=entry_buffer,
            )

    # Focused mixed confirmations.
    add("focus_adx18_mfi40_e40", "pair a moderate ADX floor with modest money-flow oversold confirmation on a looser entry", adx_min=18, mfi_max=40, rsi_entry=40, entry_buffer=0.9970)
    add("focus_adx20_bbw0030_base", "pair a stronger ADX floor with a moderate Bollinger-width floor on the base entry", adx_min=20, bb_width_min=0.030)
    add("focus_mfi35_cci100_base", "stack money-flow and CCI downside confirmation on the current winner family", mfi_max=35, cci_max=-100)
    add("focus_cci120_atr0012_base", "stack deeper CCI downside extension with a moderate ATR percent floor", cci_max=-120, atr_pct_min=0.012)
    add("focus_adx16_atr0012_e40", "use lighter ADX and ATR floors to see if active trends can support a looser entry", adx_min=16, atr_pct_min=0.012, rsi_entry=40, entry_buffer=0.9970)
    add("focus_bbw0025_mfi40_base", "combine a moderate width floor with light money-flow oversold confirmation on the base entry", bb_width_min=0.025, mfi_max=40)
    add("focus_adx22_mfi45_e38", "test whether a very strong trend floor plus light money-flow confirmation works better with a tighter entry", adx_min=22, mfi_max=45, rsi_entry=38, entry_buffer=0.9968)

    if len(specs) != 100:
        raise RuntimeError(f"Expected 100 candidates, got {len(specs)}")
    return specs


CANDIDATES = _candidate_specs()


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=REPO, text=True, check=False, **kwargs)


def git_output(*args: str) -> str:
    result = run([*SAFE_GIT, *args], capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def load_state() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {
        "session_experiments": 0,
        "candidate_index": 0,
        "base_params": deepcopy(INITIAL_PARAMS),
        "best": deepcopy(INITIAL_BEST),
        "kept_commits": [INITIAL_BEST["commit"]],
    }


def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=True), encoding="utf-8")


def fmt_float(value: float, digits: int = 4) -> str:
    return f"{value:.{digits}f}"


def py_literal(value) -> str:
    return repr(value)


def format_strategy(params: dict) -> str:
    trailing_stop = "True" if params["trailing_stop"] else "False"
    trailing_only_offset = "True" if params["trailing_only_offset_is_reached"] else "False"
    use_exit_signal = "True" if params["use_exit_signal"] else "False"
    exit_profit_only = "True" if params["exit_profit_only"] else "False"
    ignore_roi = "True" if params["ignore_roi_if_entry_signal"] else "False"

    return textwrap.dedent(
        f'''\
        """
        AutoResearch — the single file the agent iterates on.
        """

        from pandas import DataFrame
        import talib.abstract as ta

        from freqtrade.strategy import IStrategy


        class AutoResearch(IStrategy):
            INTERFACE_VERSION = 3

            timeframe = "1h"
            can_short = False

            minimal_roi = {{"0": {py_literal(params["roi"])}}}
            stoploss = {py_literal(params["stoploss"])}

            trailing_stop = {trailing_stop}
            trailing_stop_positive = {py_literal(params["trailing_stop_positive"])}
            trailing_stop_positive_offset = {py_literal(params["trailing_stop_positive_offset"])}
            trailing_only_offset_is_reached = {trailing_only_offset}
            process_only_new_candles = True

            use_exit_signal = {use_exit_signal}
            exit_profit_only = {exit_profit_only}
            ignore_roi_if_entry_signal = {ignore_roi}

            startup_candle_count: int = 200

            def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
                dataframe["rsi"] = ta.RSI(dataframe, timeperiod={params["rsi_period"]})
                dataframe["ema20"] = ta.EMA(dataframe, timeperiod=20)
                dataframe["ema50"] = ta.EMA(dataframe, timeperiod=50)
                dataframe["ema200"] = ta.EMA(dataframe, timeperiod=200)
                dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
                dataframe["mfi"] = ta.MFI(dataframe, timeperiod=14)
                dataframe["cci"] = ta.CCI(dataframe, timeperiod=20)
                dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
                bands = ta.BBANDS(dataframe, timeperiod={params["bb_period"]}, nbdevup={py_literal(params["bb_dev"])}, nbdevdn={py_literal(params["bb_dev"])})
                dataframe["bb_upper"] = bands["upperband"]
                dataframe["bb_middle"] = bands["middleband"]
                dataframe["bb_lower"] = bands["lowerband"]
                dataframe["bb_width"] = (dataframe["bb_upper"] - dataframe["bb_lower"]) / dataframe["bb_middle"]
                dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]
                return dataframe

            def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
                condition = {render_trend_condition(params)}
                condition &= dataframe["rsi"] < {params["rsi_entry"]}
                condition &= {render_pullback_condition(params)}
                {render_entry_extras(params)}
                dataframe.loc[condition, "enter_long"] = 1
                return dataframe

            def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
                exit_condition = {render_exit_condition(params)}
                dataframe.loc[exit_condition, "exit_long"] = 1
                return dataframe
        '''
    )


def render_trend_condition(params: dict) -> str:
    mode = params["trend_mode"]
    if mode == "ema200":
        return '(dataframe["close"] > dataframe["ema200"])'
    if mode == "ema200_ema50":
        return '((dataframe["close"] > dataframe["ema200"]) & (dataframe["ema50"] > dataframe["ema200"]))'
    if mode == "ema200_ema20":
        return '((dataframe["close"] > dataframe["ema200"]) & (dataframe["close"] > dataframe["ema20"]))'
    if mode == "ema200_slope6":
        return '((dataframe["close"] > dataframe["ema200"]) & (dataframe["ema200"] > dataframe["ema200"].shift(6)))'
    if mode == "ema200_slope12":
        return '((dataframe["close"] > dataframe["ema200"]) & (dataframe["ema200"] > dataframe["ema200"].shift(12)))'
    if mode == "ema200_slope24":
        return '((dataframe["close"] > dataframe["ema200"]) & (dataframe["ema200"] > dataframe["ema200"].shift(24)))'
    if mode == "ema50_200_slope":
        return '((dataframe["close"] > dataframe["ema200"]) & (dataframe["ema50"] > dataframe["ema200"]) & (dataframe["ema50"] > dataframe["ema50"].shift(6)))'
    raise ValueError(f"Unsupported trend mode: {mode}")


def render_pullback_condition(params: dict) -> str:
    lower_expr = f'(dataframe["close"] < dataframe["bb_lower"] * {py_literal(params["entry_buffer"])})'
    ema20_pullback = '(dataframe["close"] < dataframe["ema20"] * 0.990)'
    mode = params["pullback_mode"]
    if mode == "bb_lower":
        return lower_expr
    if mode == "ema20_pullback":
        return ema20_pullback
    if mode == "bbmid_pullback":
        return f'(dataframe["close"] < dataframe["bb_middle"] * {py_literal(params["entry_buffer"])})'
    if mode == "bb_or_ema20pullback":
        return f"({lower_expr} | {ema20_pullback})"
    if mode == "bb_lower_and_ema20pullback":
        return f"({lower_expr} & {ema20_pullback})"
    raise ValueError(f"Unsupported pullback mode: {mode}")


def render_entry_extras(params: dict) -> str:
    extras: list[str] = []
    if params["require_rsi_rising"]:
        extras.append('condition &= dataframe["rsi"] > dataframe["rsi"].shift(1)')
    if params["require_green_candle"]:
        extras.append('condition &= dataframe["close"] > dataframe["open"]')
    if params["require_close_above_ema50"]:
        extras.append('condition &= dataframe["close"] > dataframe["ema50"]')
    if params["require_ema20_above_ema50"]:
        extras.append('condition &= dataframe["ema20"] > dataframe["ema50"]')
    if params["adx_min"] > 0:
        extras.append(f'condition &= dataframe["adx"] > {py_literal(params["adx_min"])}')
    if params["bb_width_min"] > 0:
        extras.append(f'condition &= dataframe["bb_width"] > {py_literal(params["bb_width_min"])}')
    if params["bb_width_max"] < 999:
        extras.append(f'condition &= dataframe["bb_width"] < {py_literal(params["bb_width_max"])}')
    if params["mfi_max"] < 100:
        extras.append(f'condition &= dataframe["mfi"] < {py_literal(params["mfi_max"])}')
    if params["cci_max"] < 999:
        extras.append(f'condition &= dataframe["cci"] < {py_literal(params["cci_max"])}')
    if params["atr_pct_min"] > 0:
        extras.append(f'condition &= dataframe["atr_pct"] > {py_literal(params["atr_pct_min"])}')
    if not extras:
        return ""
    return "\n                ".join(extras)


def render_exit_condition(params: dict) -> str:
    rsi = f'(dataframe["rsi"] > {params["rsi_exit"]})'
    bbmid = f'(dataframe["close"] > dataframe["bb_middle"] * {py_literal(params["bbmid_exit_buffer"])})'
    ema20 = '(dataframe["close"] > dataframe["ema20"])'
    bbupper = '(dataframe["close"] > dataframe["bb_upper"])'
    bbmid_cross = f'((dataframe["close"] > dataframe["bb_middle"] * {py_literal(params["bbmid_exit_buffer"])}) & (dataframe["close"].shift(1) <= dataframe["bb_middle"].shift(1) * {py_literal(params["bbmid_exit_buffer"])}))'
    ema20_cross = '((dataframe["close"] > dataframe["ema20"]) & (dataframe["close"].shift(1) <= dataframe["ema20"].shift(1)))'

    mode = params["exit_mode"]
    if mode == "rsi_or_bbmid":
        return f"({rsi} | {bbmid})"
    if mode == "rsi_and_bbmid":
        return f"({rsi} & {bbmid})"
    if mode == "bbmid_only":
        return bbmid
    if mode == "rsi_only":
        return rsi
    if mode == "rsi_or_ema20":
        return f"({rsi} | {ema20})"
    if mode == "ema20_only":
        return ema20
    if mode == "rsi_and_ema20":
        return f"({rsi} & {ema20})"
    if mode == "rsi_and_ema20_cross":
        return f"({rsi} & {ema20_cross})"
    if mode == "bbmid_or_ema20":
        return f"({bbmid} | {ema20})"
    if mode == "rsi_or_bbupper":
        return f"({rsi} | {bbupper})"
    if mode == "rsi_and_bbupper":
        return f"({rsi} & {bbupper})"
    if mode == "bbupper_only":
        return bbupper
    if mode == "bbmid_cross_only":
        return bbmid_cross
    if mode == "ema20_cross_only":
        return ema20_cross
    if mode == "rsi_or_bbmid_cross":
        return f"({rsi} | {bbmid_cross})"
    if mode == "rsi_and_bbmid_cross":
        return f"({rsi} & {bbmid_cross})"
    if mode == "rsi_or_ema20_cross":
        return f"({rsi} | {ema20_cross})"
    raise ValueError(f"Unsupported exit mode: {mode}")


def parse_summary() -> dict:
    content = RUN_LOG_PATH.read_text(encoding="utf-8", errors="replace")
    summary: dict[str, str] = {}
    for line in content.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key in {
            "strategy",
            "commit",
            "timerange",
            "sharpe",
            "sortino",
            "calmar",
            "total_profit_pct",
            "max_drawdown_pct",
            "trade_count",
            "win_rate_pct",
            "profit_factor",
            "pairs",
        }:
            summary[key] = value.strip()
    required = {"commit", "sharpe", "total_profit_pct", "max_drawdown_pct", "trade_count", "profit_factor"}
    if not required.issubset(summary):
        raise RuntimeError("Malformed summary block")
    return {
        "commit": summary["commit"],
        "sharpe": float(summary["sharpe"]),
        "total_profit_pct": float(summary["total_profit_pct"]),
        "max_drawdown_pct": float(summary["max_drawdown_pct"]),
        "trade_count": int(summary["trade_count"]),
        "profit_factor": float(summary["profit_factor"]),
    }


def utility(metrics: dict) -> float:
    return metrics["sharpe"] + (metrics["total_profit_pct"] + metrics["max_drawdown_pct"]) / 100.0


def append_result(commit: str, sharpe: float, max_dd_abs: float, status: str, description: str) -> None:
    if RESULTS_PATH.exists():
        content = RESULTS_PATH.read_text(encoding="utf-8")
        if content and not content.endswith("\n"):
            RESULTS_PATH.write_text(content + "\n", encoding="utf-8")
    with RESULTS_PATH.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow([commit, fmt_float(sharpe), fmt_float(max_dd_abs), status, description])


def safe_discard_last_commit() -> None:
    result = run([*SAFE_GIT, "reset", "--soft", "HEAD~1"], capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git reset --soft HEAD~1 failed")
    result = run([*SAFE_GIT, "restore", "--source=HEAD", "--staged", "--worktree", "--", str(STRATEGY_PATH.relative_to(REPO))], capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git restore strategy failed")


def write_strategy(params: dict) -> None:
    STRATEGY_PATH.write_text(format_strategy(params), encoding="utf-8")


def run_backtest() -> tuple[int, str]:
    with RUN_LOG_PATH.open("w", encoding="utf-8") as handle:
        proc = subprocess.run(
            RUNNER,
            cwd=REPO,
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=300,
            check=False,
        )
    return proc.returncode, RUN_LOG_PATH.read_text(encoding="utf-8", errors="replace")


def description_for_result(spec: dict, metrics: dict | None, best_before: dict, keep: bool, crash_note: str | None = None) -> str:
    if metrics is None:
        return f'{spec["label"]}: {spec["rationale"]}. Crash after one rerun attempt: {crash_note}'
    current_utility = utility(metrics)
    reason = (
        f"utility improved from {best_before['utility']:.3f} to {current_utility:.3f}"
        if keep
        else f"utility {current_utility:.3f} below best {best_before['utility']:.3f}"
    )
    return (
        f'{spec["label"]}: {spec["rationale"]}. {reason}; sharpe {metrics["sharpe"]:.4f}, '
        f'profit {metrics["total_profit_pct"]:.2f}%, dd {abs(metrics["max_drawdown_pct"]):.2f}%, '
        f'trades {metrics["trade_count"]}, pf {metrics["profit_factor"]:.2f}.'
    )


def keep_candidate(metrics: dict, best: dict) -> bool:
    current_utility = utility(metrics)
    if metrics["trade_count"] < 60:
        return current_utility > best["utility"] + 0.030 and metrics["total_profit_pct"] > best["total_profit_pct"]
    if current_utility <= best["utility"] + 0.005:
        return False
    if metrics["profit_factor"] < 1.0 and metrics["sharpe"] < best["sharpe"] + 0.02:
        return False
    return True


def apply_updates(base_params: dict, updates: dict) -> dict:
    candidate = deepcopy(base_params)
    candidate.update(updates)
    if not candidate["trailing_stop"]:
        candidate["trailing_stop_positive"] = 0.0
        candidate["trailing_stop_positive_offset"] = 0.0
        candidate["trailing_only_offset_is_reached"] = False
    return candidate


def commit_strategy(message: str) -> None:
    result = run([*SAFE_GIT, "add", "--", str(STRATEGY_PATH.relative_to(REPO))], capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git add failed")
    result = run([*SAFE_GIT, "commit", "--quiet", "-m", message, "--", str(STRATEGY_PATH.relative_to(REPO))], capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git commit failed")


def execute_one(state: dict) -> dict:
    if state["candidate_index"] >= len(CANDIDATES):
        raise RuntimeError("Ran out of candidate experiments")

    spec = CANDIDATES[state["candidate_index"]]
    best_before = deepcopy(state["best"])
    candidate_params = apply_updates(state["base_params"], spec["updates"])

    write_strategy(candidate_params)
    commit_strategy(spec["label"])

    metrics = None
    try:
        code, log_text = run_backtest()
        if code != 0:
            code, log_text = run_backtest()
        if code != 0:
            raise RuntimeError(log_text.splitlines()[-20:])
        metrics = parse_summary()
    except Exception as exc:
        crash_note = str(exc)
        commit = git_output("rev-parse", "--short", "HEAD")
        append_result(commit, 0.0, 0.0, "crash", description_for_result(spec, None, best_before, False, crash_note))
        safe_discard_last_commit()
        state["session_experiments"] += 1
        state["candidate_index"] += 1
        save_state(state)
        return {
            "label": spec["label"],
            "status": "crash",
            "commit": commit,
            "best_commit": state["best"]["commit"],
        }

    commit = metrics["commit"]
    keep = keep_candidate(metrics, best_before)
    append_result(commit, metrics["sharpe"], abs(metrics["max_drawdown_pct"]), "keep" if keep else "discard", description_for_result(spec, metrics, best_before, keep))

    if keep:
        state["base_params"] = candidate_params
        state["best"] = {**metrics, "utility": utility(metrics)}
        state["kept_commits"].append(commit)
    else:
        safe_discard_last_commit()

    state["session_experiments"] += 1
    state["candidate_index"] += 1
    save_state(state)
    return {
        "label": spec["label"],
        "status": "keep" if keep else "discard",
        "commit": commit,
        "utility": utility(metrics),
        "best_commit": state["best"]["commit"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, required=True)
    args = parser.parse_args()

    state = load_state()
    remaining = 100 - state["session_experiments"]
    if remaining <= 0:
        print(json.dumps({"done": True, "state": state}, indent=2))
        return 0

    count = min(args.count, remaining)
    batch_results = []
    for _ in range(count):
        batch_results.append(execute_one(state))

    print(json.dumps({"done": state["session_experiments"] >= 100, "batch_results": batch_results, "state": state}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
