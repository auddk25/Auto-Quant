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
STATE_PATH = REPO / ".tmp" / "autoresearch_state_round2.json"
SAFE_GIT = ["git", "-c", "safe.directory=E:/code/AutoQuant"]
RUNNER = [str(REPO / ".venv" / "Scripts" / "python.exe"), "run.py"]

INITIAL_PARAMS = {
    "rsi_period": 21,
    "rsi_entry": 40,
    "rsi_exit": 60,
    "roi": 0.008,
    "stoploss": -0.08,
    "bb_period": 24,
    "bb_dev": 2.2,
    "trend_mode": "ema200",
    "pullback_mode": "bb_lower",
    "entry_buffer": 0.998,
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
    "commit": "07e5087",
    "sharpe": 0.3433,
    "total_profit_pct": 18.9134,
    "max_drawdown_pct": -8.5362,
    "trade_count": 95,
    "profit_factor": 1.9781,
    "utility": 0.447072,
}


def _candidate_specs() -> list[dict]:
    specs: list[dict] = []

    def add(label: str, rationale: str, **updates) -> None:
        specs.append({"label": label, "rationale": rationale, "updates": updates})

    add("exit_rsi_58", "test a slightly earlier conjunctive exit", rsi_exit=58)
    add("exit_rsi_59", "test a minimally earlier conjunctive exit", rsi_exit=59)
    add("exit_rsi_61", "test a minimally later conjunctive exit", rsi_exit=61)
    add("exit_rsi_62", "test a slightly later conjunctive exit", rsi_exit=62)
    add("exit_rsi_63", "test a later conjunctive exit without changing the BB-mid requirement", rsi_exit=63)
    add("exit_rsi_64", "push the RSI leg later while keeping the BB-mid requirement", rsi_exit=64)
    add("roi_0_007", "lower ROI a touch inside the winning family", roi=0.007)
    add("roi_0_0075", "lower ROI slightly inside the winning family", roi=0.0075)
    add("roi_0_0085", "raise ROI slightly inside the winning family", roi=0.0085)
    add("roi_0_009", "raise ROI a touch inside the winning family", roi=0.009)
    add("roi_0_0095", "raise ROI further while keeping the current exit conjunction", roi=0.0095)
    add("exit59_roi0075", "pair a minimally earlier RSI exit with a slightly lower ROI", rsi_exit=59, roi=0.0075)
    add("exit61_roi0075", "pair a minimally later RSI exit with a slightly lower ROI", rsi_exit=61, roi=0.0075)
    add("exit59_roi0085", "pair a minimally earlier RSI exit with a slightly higher ROI", rsi_exit=59, roi=0.0085)
    add("exit61_roi0085", "pair a minimally later RSI exit with a slightly higher ROI", rsi_exit=61, roi=0.0085)
    add("exit62_roi009", "pair a slightly later RSI exit with a modestly higher ROI", rsi_exit=62, roi=0.009)

    add("bb_period_23", "shorten the Bollinger period by one candle", bb_period=23)
    add("bb_period_25", "lengthen the Bollinger period by one candle", bb_period=25)
    add("bb_period_26", "lengthen the Bollinger period by two candles", bb_period=26)
    add("bb_dev_2_1", "narrow the Bollinger width slightly around the winning family", bb_dev=2.1)
    add("bb_dev_2_15", "narrow the Bollinger width very slightly", bb_dev=2.15)
    add("bb_dev_2_25", "widen the Bollinger width very slightly", bb_dev=2.25)
    add("bb_dev_2_3", "widen the Bollinger width slightly", bb_dev=2.3)
    add("entry_buffer_0_997", "require a deeper lower-band break", entry_buffer=0.997)
    add("entry_buffer_0_999", "require a slightly shallower lower-band break", entry_buffer=0.999)
    add("entry_buffer_0_9975", "split the difference toward a deeper lower-band break", entry_buffer=0.9975)
    add("entry_buffer_0_9985", "split the difference toward a shallower lower-band break", entry_buffer=0.9985)
    add("bb23_dev21", "combine a slightly faster band with a slightly narrower width", bb_period=23, bb_dev=2.1)
    add("bb23_dev225", "combine a slightly faster band with a slightly wider width", bb_period=23, bb_dev=2.25)
    add("bb25_dev215", "combine a slightly slower band with a slightly narrower width", bb_period=25, bb_dev=2.15)
    add("bb25_dev225", "combine a slightly slower band with a slightly wider width", bb_period=25, bb_dev=2.25)
    add("bb26_dev23", "combine the slowest local band with the widest local width", bb_period=26, bb_dev=2.3)
    add("dev215_buf997", "pair a slightly narrower width with a deeper band break", bb_dev=2.15, entry_buffer=0.997)
    add("dev225_buf999", "pair a slightly wider width with a shallower band break", bb_dev=2.25, entry_buffer=0.999)
    add("bb25_buf997", "pair a slightly slower band with a deeper band break", bb_period=25, entry_buffer=0.997)
    add("bb23_buf999", "pair a slightly faster band with a shallower band break", bb_period=23, entry_buffer=0.999)

    add("entry_39", "tighten RSI entry by one point inside the winning family", rsi_entry=39)
    add("entry_41", "loosen RSI entry by one point inside the winning family", rsi_entry=41)
    add("rsi_period_20", "shorten RSI by one bar", rsi_period=20)
    add("rsi_period_22", "lengthen RSI by one bar", rsi_period=22)
    add("rsi_period_24", "lengthen RSI modestly while keeping the new band family", rsi_period=24)
    add("rsi_period_19", "shorten RSI by two bars", rsi_period=19)
    add("rsi_period_23", "lengthen RSI by two bars", rsi_period=23)
    add("rsi20_entry39", "pair slightly faster RSI with a slightly tighter threshold", rsi_period=20, rsi_entry=39)
    add("rsi20_entry41", "pair slightly faster RSI with a slightly looser threshold", rsi_period=20, rsi_entry=41)
    add("rsi22_entry39", "pair slightly slower RSI with a slightly tighter threshold", rsi_period=22, rsi_entry=39)
    add("rsi22_entry41", "pair slightly slower RSI with a slightly looser threshold", rsi_period=22, rsi_entry=41)
    add("rsi24_entry39", "pair slower RSI with a slightly tighter threshold", rsi_period=24, rsi_entry=39)
    add("rsi24_entry41", "pair slower RSI with a slightly looser threshold", rsi_period=24, rsi_entry=41)
    add("rsi19_entry39", "pair the fastest local RSI with a slightly tighter threshold", rsi_period=19, rsi_entry=39)
    add("rsi23_entry41", "pair a mildly slower RSI with a slightly looser threshold", rsi_period=23, rsi_entry=41)
    add("entry39_buf997", "pair a slightly tighter RSI threshold with a deeper band break", rsi_entry=39, entry_buffer=0.997)

    add("sl_0_075", "tighten stoploss by half a percent", stoploss=-0.075)
    add("sl_0_085", "loosen stoploss by half a percent", stoploss=-0.085)
    add("sl_0_070", "tighten stoploss by a full percent", stoploss=-0.07)
    add("sl_0_090", "loosen stoploss by a full percent", stoploss=-0.09)
    add("sl075_roi0075", "pair a slightly tighter stop with a slightly lower ROI", stoploss=-0.075, roi=0.0075)
    add("sl085_roi0075", "pair a slightly looser stop with a slightly lower ROI", stoploss=-0.085, roi=0.0075)
    add("sl075_roi0085", "pair a slightly tighter stop with a slightly higher ROI", stoploss=-0.075, roi=0.0085)
    add("sl085_roi0085", "pair a slightly looser stop with a slightly higher ROI", stoploss=-0.085, roi=0.0085)
    add("sl075_exit59", "pair a slightly tighter stop with a minimally earlier RSI exit", stoploss=-0.075, rsi_exit=59)
    add("sl075_exit61", "pair a slightly tighter stop with a minimally later RSI exit", stoploss=-0.075, rsi_exit=61)
    add("sl085_exit59", "pair a slightly looser stop with a minimally earlier RSI exit", stoploss=-0.085, rsi_exit=59)
    add("sl085_exit61", "pair a slightly looser stop with a minimally later RSI exit", stoploss=-0.085, rsi_exit=61)
    add("sl070_roi0075", "pair the tightest local stop with a slightly lower ROI", stoploss=-0.07, roi=0.0075)
    add("sl090_roi0085", "pair the loosest local stop with a slightly higher ROI", stoploss=-0.09, roi=0.0085)
    add("sl070_exit59", "pair the tightest local stop with a minimally earlier RSI exit", stoploss=-0.07, rsi_exit=59)
    add("sl090_exit61", "pair the loosest local stop with a minimally later RSI exit", stoploss=-0.09, rsi_exit=61)

    add("bbmid_exit_0_999", "allow exits a hair below the Bollinger midline", bbmid_exit_buffer=0.999)
    add("bbmid_exit_1_001", "require price to clear the Bollinger midline by a hair before exit", bbmid_exit_buffer=1.001)
    add("bbmid_exit_1_002", "require a clearer Bollinger-mid reclaim before exit", bbmid_exit_buffer=1.002)
    add("bbmid_exit_0_998", "allow an even earlier near-midline exit", bbmid_exit_buffer=0.998)
    add("exit59_bbmid0999", "pair a minimally earlier RSI exit with a slightly earlier BB-mid threshold", rsi_exit=59, bbmid_exit_buffer=0.999)
    add("exit59_bbmid1001", "pair a minimally earlier RSI exit with a slightly stricter BB-mid threshold", rsi_exit=59, bbmid_exit_buffer=1.001)
    add("exit61_bbmid0999", "pair a minimally later RSI exit with a slightly earlier BB-mid threshold", rsi_exit=61, bbmid_exit_buffer=0.999)
    add("exit61_bbmid1001", "pair a minimally later RSI exit with a slightly stricter BB-mid threshold", rsi_exit=61, bbmid_exit_buffer=1.001)
    add("exit_cross", "require a clean cross back above the BB midline on the exit leg", exit_mode="rsi_and_bbmid_cross")
    add("exit_cross_0999", "require a clean cross above a slightly easier BB-mid threshold", exit_mode="rsi_and_bbmid_cross", bbmid_exit_buffer=0.999)
    add("exit_cross_1001", "require a clean cross above a slightly stricter BB-mid threshold", exit_mode="rsi_and_bbmid_cross", bbmid_exit_buffer=1.001)
    add("exit_and_ema20_59", "swap the price leg to EMA20 with a minimally earlier RSI threshold", exit_mode="rsi_and_ema20", rsi_exit=59)
    add("exit_and_ema20_61", "swap the price leg to EMA20 with a minimally later RSI threshold", exit_mode="rsi_and_ema20", rsi_exit=61)
    add("exit_and_ema20_cross", "require both RSI normalization and an EMA20 cross", exit_mode="rsi_and_ema20_cross")
    add("exit_and_bbupper_59", "require both RSI normalization and an upper-band reclaim", exit_mode="rsi_and_bbupper", rsi_exit=59)
    add("exit_rsi_only_59", "retest RSI-only exits inside the current local family", exit_mode="rsi_only", rsi_exit=59)

    add("combo_bb25_dev225_buf997", "stack a slightly slower wider band with a deeper band break", bb_period=25, bb_dev=2.25, entry_buffer=0.997)
    add("combo_bb23_dev21_buf999", "stack a slightly faster narrower band with a shallower band break", bb_period=23, bb_dev=2.1, entry_buffer=0.999)
    add("combo_bb26_dev225_buf9975", "test the slowest local band with a slightly wider width and mid-depth break", bb_period=26, bb_dev=2.25, entry_buffer=0.9975)
    add("combo_bb24_dev215_buf9975", "test a slightly narrower width with a mid-depth band break", bb_dev=2.15, entry_buffer=0.9975)
    add("combo_bb24_dev23_buf9985", "test a slightly wider width with a slightly shallower band break", bb_dev=2.3, entry_buffer=0.9985)
    add("combo_roi0075_exit59_bb25", "pair slightly lower ROI and earlier RSI exit with a slower band", roi=0.0075, rsi_exit=59, bb_period=25)
    add("combo_roi0075_exit61_bb23", "pair slightly lower ROI and later RSI exit with a faster band", roi=0.0075, rsi_exit=61, bb_period=23)
    add("combo_roi0085_exit59_dev215", "pair slightly higher ROI and earlier RSI exit with a narrower band", roi=0.0085, rsi_exit=59, bb_dev=2.15)
    add("combo_roi0085_exit61_dev225", "pair slightly higher ROI and later RSI exit with a wider band", roi=0.0085, rsi_exit=61, bb_dev=2.25)
    add("combo_sl075_bb25", "pair a slightly tighter stop with a slightly slower band", stoploss=-0.075, bb_period=25)
    add("combo_sl085_bb23", "pair a slightly looser stop with a slightly faster band", stoploss=-0.085, bb_period=23)
    add("combo_entry39_dev225", "pair a slightly tighter RSI entry with a slightly wider band", rsi_entry=39, bb_dev=2.25)
    add("combo_entry41_dev215", "pair a slightly looser RSI entry with a slightly narrower band", rsi_entry=41, bb_dev=2.15)
    add("combo_rsi20_dev225", "pair a slightly faster RSI with a slightly wider band", rsi_period=20, bb_dev=2.25)
    add("combo_rsi22_buf9975", "pair a slightly slower RSI with a mid-depth band break", rsi_period=22, entry_buffer=0.9975)
    add("combo_entry39_roi0075", "pair a slightly tighter RSI entry with a slightly lower ROI", rsi_entry=39, roi=0.0075)

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

            minimal_roi = {{"0": {params["roi"]:.3f}}}
            stoploss = {params["stoploss"]:.2f}

            trailing_stop = {trailing_stop}
            trailing_stop_positive = {params["trailing_stop_positive"]:.3f}
            trailing_stop_positive_offset = {params["trailing_stop_positive_offset"]:.3f}
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
                bands = ta.BBANDS(dataframe, timeperiod={params["bb_period"]}, nbdevup={params["bb_dev"]:.1f}, nbdevdn={params["bb_dev"]:.1f})
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
    lower_expr = f'(dataframe["close"] < dataframe["bb_lower"] * {params["entry_buffer"]:.3f})'
    ema20_pullback = '(dataframe["close"] < dataframe["ema20"] * 0.990)'
    mode = params["pullback_mode"]
    if mode == "bb_lower":
        return lower_expr
    if mode == "ema20_pullback":
        return ema20_pullback
    if mode == "bbmid_pullback":
        return f'(dataframe["close"] < dataframe["bb_middle"] * {params["entry_buffer"]:.3f})'
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
    bbmid = f'(dataframe["close"] > dataframe["bb_middle"] * {params["bbmid_exit_buffer"]:.3f})'
    ema20 = '(dataframe["close"] > dataframe["ema20"])'
    bbupper = '(dataframe["close"] > dataframe["bb_upper"])'
    bbmid_cross = f'((dataframe["close"] > dataframe["bb_middle"] * {params["bbmid_exit_buffer"]:.3f}) & (dataframe["close"].shift(1) <= dataframe["bb_middle"].shift(1) * {params["bbmid_exit_buffer"]:.3f}))'
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
