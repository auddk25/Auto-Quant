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
STATE_PATH = REPO / ".tmp" / "autoresearch_state_round3.json"
SAFE_GIT = ["git", "-c", "safe.directory=E:/code/AutoQuant"]
RUNNER = [str(REPO / ".venv" / "Scripts" / "python.exe"), "run.py"]

INITIAL_PARAMS = {
    "rsi_period": 20,
    "rsi_entry": 39,
    "rsi_exit": 60,
    "roi": 0.007,
    "stoploss": -0.08,
    "bb_period": 25,
    "bb_dev": 2.2,
    "trend_mode": "ema200",
    "pullback_mode": "bb_lower",
    "entry_buffer": 0.997,
    "bbmid_exit_buffer": 1.0,
    "exit_mode": "rsi_and_bbmid",
    "require_rsi_rising": False,
    "require_green_candle": False,
    "require_close_above_ema50": False,
    "require_ema20_above_ema50": False,
    "trailing_stop": False,
    "trailing_stop_positive": 0.0,
    "trailing_stop_positive_offset": 0.0,
    "trailing_only_offset_is_reached": False,
    "use_exit_signal": True,
    "exit_profit_only": False,
    "ignore_roi_if_entry_signal": True,
}

INITIAL_BEST = {
    "commit": "187e595",
    "sharpe": 0.4319,
    "total_profit_pct": 16.7821,
    "max_drawdown_pct": -4.0550,
    "trade_count": 75,
    "profit_factor": 2.8001,
    "utility": 0.559171,
}


def _candidate_specs() -> list[dict]:
    specs: list[dict] = []

    def add(label: str, rationale: str, **updates) -> None:
        specs.append({"label": label, "rationale": rationale, "updates": updates})

    # Single-axis local sweeps around the current best.
    add("rsi_period_19", "shorten RSI by one bar around the current winner", rsi_period=19)
    add("rsi_period_21", "lengthen RSI by one bar around the current winner", rsi_period=21)
    add("rsi_period_18", "shorten RSI by two bars around the current winner", rsi_period=18)
    add("rsi_period_22", "lengthen RSI by two bars around the current winner", rsi_period=22)

    add("rsi_entry_38", "tighten entry threshold by one point", rsi_entry=38)
    add("rsi_entry_40", "loosen entry threshold by one point", rsi_entry=40)
    add("rsi_entry_37", "tighten entry threshold by two points", rsi_entry=37)
    add("rsi_entry_41", "loosen entry threshold by two points", rsi_entry=41)

    add("rsi_exit_59", "test a minimally earlier conjunctive exit", rsi_exit=59)
    add("rsi_exit_61", "test a minimally later conjunctive exit", rsi_exit=61)
    add("rsi_exit_58", "test an earlier conjunctive exit", rsi_exit=58)
    add("rsi_exit_62", "test a later conjunctive exit", rsi_exit=62)

    add("roi_0_0060", "lower ROI materially while staying near the winner", roi=0.0060)
    add("roi_0_0065", "lower ROI slightly while staying near the winner", roi=0.0065)
    add("roi_0_0075", "raise ROI slightly while staying near the winner", roi=0.0075)
    add("roi_0_0080", "raise ROI to the previous local winner", roi=0.0080)
    add("roi_0_0085", "raise ROI above the previous local winner", roi=0.0085)

    add("stoploss_0_075", "tighten stoploss by half a percent", stoploss=-0.075)
    add("stoploss_0_070", "tighten stoploss by a full percent", stoploss=-0.07)
    add("stoploss_0_085", "loosen stoploss by half a percent", stoploss=-0.085)
    add("stoploss_0_090", "loosen stoploss by a full percent", stoploss=-0.09)

    add("bb_period_24", "shorten the Bollinger period by one candle", bb_period=24)
    add("bb_period_26", "lengthen the Bollinger period by one candle", bb_period=26)
    add("bb_period_27", "lengthen the Bollinger period by two candles", bb_period=27)

    add("bb_dev_2_15", "narrow the Bollinger width slightly", bb_dev=2.15)
    add("bb_dev_2_18", "narrow the Bollinger width very slightly", bb_dev=2.18)
    add("bb_dev_2_22", "widen the Bollinger width very slightly", bb_dev=2.22)
    add("bb_dev_2_25", "widen the Bollinger width slightly", bb_dev=2.25)
    add("bb_dev_2_28", "widen the Bollinger width more aggressively", bb_dev=2.28)
    add("bb_dev_2_30", "widen the Bollinger width to the prior local winner", bb_dev=2.30)

    add("entry_buffer_0_9960", "require a deeper lower-band break", entry_buffer=0.9960)
    add("entry_buffer_0_9965", "require a slightly deeper lower-band break", entry_buffer=0.9965)
    add("entry_buffer_0_9975", "allow a slightly shallower lower-band break", entry_buffer=0.9975)
    add("entry_buffer_0_9980", "allow a shallower lower-band break", entry_buffer=0.9980)

    add("bbmid_exit_0_999", "allow exits a hair below the Bollinger midline", bbmid_exit_buffer=0.999)
    add("bbmid_exit_1_001", "require price to clear the Bollinger midline by a hair", bbmid_exit_buffer=1.001)
    add("bbmid_exit_1_002", "require a clearer Bollinger-mid reclaim before exit", bbmid_exit_buffer=1.002)
    add("bbmid_exit_0_998", "allow an even earlier near-midline exit", bbmid_exit_buffer=0.998)

    add("exit_mode_cross", "require a clean BB-mid cross for the price leg", exit_mode="rsi_and_bbmid_cross")
    add("exit_mode_ema20", "swap the price leg to EMA20", exit_mode="rsi_and_ema20")
    add("exit_mode_rsi_only", "drop the price leg and use RSI-only exits", exit_mode="rsi_only")
    add("exit_mode_bbupper", "use the upper band as the price leg", exit_mode="rsi_and_bbupper")

    add("ignore_roi_false", "retest disabling ROI-ignore inside the tightened family", ignore_roi_if_entry_signal=False)

    # Local 2D/3D combinations near the winning family.
    add("bb24_dev225_buf997", "slightly faster band with slightly wider width", bb_period=24, bb_dev=2.25, entry_buffer=0.997)
    add("bb26_dev220_buf997", "slightly slower band with the current width", bb_period=26, bb_dev=2.20, entry_buffer=0.997)
    add("bb25_dev225_buf9965", "current period with wider width and deeper break", bb_period=25, bb_dev=2.25, entry_buffer=0.9965)
    add("bb25_dev225_buf9975", "current period with wider width and shallower break", bb_period=25, bb_dev=2.25, entry_buffer=0.9975)
    add("bb25_dev218_buf9965", "current period with slightly narrower width and deeper break", bb_period=25, bb_dev=2.18, entry_buffer=0.9965)
    add("bb25_dev222_buf9965", "current period with slightly wider width and deeper break", bb_period=25, bb_dev=2.22, entry_buffer=0.9965)
    add("bb25_dev218_buf9975", "current period with slightly narrower width and shallower break", bb_period=25, bb_dev=2.18, entry_buffer=0.9975)
    add("bb25_dev222_buf9975", "current period with slightly wider width and shallower break", bb_period=25, bb_dev=2.22, entry_buffer=0.9975)
    add("bb24_dev218_buf9965", "slightly faster narrower band with deeper break", bb_period=24, bb_dev=2.18, entry_buffer=0.9965)
    add("bb26_dev222_buf9965", "slightly slower wider band with deeper break", bb_period=26, bb_dev=2.22, entry_buffer=0.9965)
    add("bb24_dev225_buf9975", "slightly faster wider band with shallower break", bb_period=24, bb_dev=2.25, entry_buffer=0.9975)
    add("bb26_dev215_buf997", "slightly slower narrower band", bb_period=26, bb_dev=2.15, entry_buffer=0.997)

    add("entry38_roi0065", "tighter entry plus slightly lower ROI", rsi_entry=38, roi=0.0065)
    add("entry38_roi0075", "tighter entry plus slightly higher ROI", rsi_entry=38, roi=0.0075)
    add("entry40_roi0065", "looser entry plus slightly lower ROI", rsi_entry=40, roi=0.0065)
    add("entry40_roi0075", "looser entry plus slightly higher ROI", rsi_entry=40, roi=0.0075)
    add("rsi19_entry39_roi0065", "slightly faster RSI with lower ROI", rsi_period=19, rsi_entry=39, roi=0.0065)
    add("rsi21_entry39_roi0065", "slightly slower RSI with lower ROI", rsi_period=21, rsi_entry=39, roi=0.0065)
    add("rsi19_entry38_roi0070", "faster RSI with tighter entry and base ROI", rsi_period=19, rsi_entry=38, roi=0.0070)
    add("rsi21_entry40_roi0070", "slower RSI with looser entry and base ROI", rsi_period=21, rsi_entry=40, roi=0.0070)

    add("exit59_roi0065", "earlier RSI exit plus lower ROI", rsi_exit=59, roi=0.0065)
    add("exit61_roi0065", "later RSI exit plus lower ROI", rsi_exit=61, roi=0.0065)
    add("exit59_roi0075", "earlier RSI exit plus higher ROI", rsi_exit=59, roi=0.0075)
    add("exit61_roi0075", "later RSI exit plus higher ROI", rsi_exit=61, roi=0.0075)
    add("exit59_buf0999", "earlier RSI exit with slightly easier BB-mid threshold", rsi_exit=59, bbmid_exit_buffer=0.999)
    add("exit61_buf0999", "later RSI exit with slightly easier BB-mid threshold", rsi_exit=61, bbmid_exit_buffer=0.999)
    add("exit59_buf1001", "earlier RSI exit with slightly stricter BB-mid threshold", rsi_exit=59, bbmid_exit_buffer=1.001)
    add("exit61_buf1001", "later RSI exit with slightly stricter BB-mid threshold", rsi_exit=61, bbmid_exit_buffer=1.001)
    add("exit59_period24", "earlier RSI exit with slightly faster band", rsi_exit=59, bb_period=24)
    add("exit61_period26", "later RSI exit with slightly slower band", rsi_exit=61, bb_period=26)

    add("sl075_roi0065", "slightly tighter stop with lower ROI", stoploss=-0.075, roi=0.0065)
    add("sl075_roi0075", "slightly tighter stop with higher ROI", stoploss=-0.075, roi=0.0075)
    add("sl085_roi0065", "slightly looser stop with lower ROI", stoploss=-0.085, roi=0.0065)
    add("sl085_roi0075", "slightly looser stop with higher ROI", stoploss=-0.085, roi=0.0075)
    add("sl075_dev225", "slightly tighter stop with wider band", stoploss=-0.075, bb_dev=2.25)
    add("sl085_dev225", "slightly looser stop with wider band", stoploss=-0.085, bb_dev=2.25)
    add("sl075_buf9965", "slightly tighter stop with deeper break", stoploss=-0.075, entry_buffer=0.9965)
    add("sl085_buf9975", "slightly looser stop with shallower break", stoploss=-0.085, entry_buffer=0.9975)

    add("ignore_false_roi0065", "disable ROI-ignore and lower ROI further", ignore_roi_if_entry_signal=False, roi=0.0065)
    add("ignore_false_exit59", "disable ROI-ignore and exit slightly earlier", ignore_roi_if_entry_signal=False, rsi_exit=59)
    add("ignore_false_bb24", "disable ROI-ignore with slightly faster band", ignore_roi_if_entry_signal=False, bb_period=24)
    add("ignore_false_entry38", "disable ROI-ignore with tighter entry", ignore_roi_if_entry_signal=False, rsi_entry=38)

    add("ema20_exit59", "EMA20 price leg with earlier RSI threshold", exit_mode="rsi_and_ema20", rsi_exit=59)
    add("ema20_exit60", "EMA20 price leg at the current RSI threshold", exit_mode="rsi_and_ema20", rsi_exit=60)
    add("ema20_exit61", "EMA20 price leg with later RSI threshold", exit_mode="rsi_and_ema20", rsi_exit=61)
    add("cross_exit59", "BB-mid cross price leg with earlier RSI threshold", exit_mode="rsi_and_bbmid_cross", rsi_exit=59)
    add("cross_exit60", "BB-mid cross price leg at the current RSI threshold", exit_mode="rsi_and_bbmid_cross", rsi_exit=60)
    add("cross_exit61", "BB-mid cross price leg with later RSI threshold", exit_mode="rsi_and_bbmid_cross", rsi_exit=61)
    add("bbupper_exit59", "upper-band price leg with earlier RSI threshold", exit_mode="rsi_and_bbupper", rsi_exit=59)
    add("bbupper_exit60", "upper-band price leg at the current RSI threshold", exit_mode="rsi_and_bbupper", rsi_exit=60)

    add("bb27_dev225", "slowest local band with slightly wider width", bb_period=27, bb_dev=2.25)
    add("bb26_dev228", "slightly slower band with mid-wide width", bb_period=26, bb_dev=2.28)
    add("bb24_dev228", "slightly faster band with mid-wide width", bb_period=24, bb_dev=2.28)
    add("bb25_dev230_buf9965", "current period with widest local band and deeper break", bb_period=25, bb_dev=2.30, entry_buffer=0.9965)
    add("bb25_dev230_buf9975", "current period with widest local band and shallower break", bb_period=25, bb_dev=2.30, entry_buffer=0.9975)
    add("rsi20_entry38_dev225", "current RSI period with tighter entry and wider band", rsi_period=20, rsi_entry=38, bb_dev=2.25)
    add("rsi20_entry38_buf9965", "current RSI period with tighter entry and deeper break", rsi_period=20, rsi_entry=38, entry_buffer=0.9965)

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
                bands = ta.BBANDS(dataframe, timeperiod={params["bb_period"]}, nbdevup={py_literal(params["bb_dev"])}, nbdevdn={py_literal(params["bb_dev"])})
                dataframe["bb_upper"] = bands["upperband"]
                dataframe["bb_middle"] = bands["middleband"]
                dataframe["bb_lower"] = bands["lowerband"]
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
    if not extras:
        return ""
    return "\n        ".join(extras)


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
