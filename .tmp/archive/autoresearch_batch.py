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
STATE_PATH = REPO / ".tmp" / "autoresearch_state.json"
SAFE_GIT = ["git", "-c", "safe.directory=E:/code/AutoQuant"]
RUNNER = [str(REPO / ".venv" / "Scripts" / "python.exe"), "run.py"]

INITIAL_PARAMS = {
    "rsi_period": 21,
    "rsi_entry": 40,
    "rsi_exit": 65,
    "roi": 0.010,
    "stoploss": -0.08,
    "bb_period": 20,
    "bb_dev": 2.0,
    "trend_mode": "ema200",
    "pullback_mode": "bb_lower",
    "entry_buffer": 1.0,
    "exit_mode": "rsi_or_bbmid",
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
    "ignore_roi_if_entry_signal": False,
}

INITIAL_BEST = {
    "commit": "80d21b5",
    "sharpe": 0.0223,
    "total_profit_pct": 1.0291,
    "max_drawdown_pct": -11.7194,
    "trade_count": 121,
    "profit_factor": 1.0918,
    "utility": -0.084603,
}


def _candidate_specs() -> list[dict]:
    specs: list[dict] = []

    def add(label: str, rationale: str, **updates) -> None:
        specs.append({"label": label, "rationale": rationale, "updates": updates})

    add("exit_rsi_62", "tighten RSI profit-taking a bit earlier", rsi_exit=62)
    add("exit_rsi_68", "let winners run slightly longer before RSI exit", rsi_exit=68)
    add("exit_rsi_60", "test clearly earlier RSI exit against the BB mid exit", rsi_exit=60)
    add("exit_rsi_70", "test clearly later RSI exit against the BB mid exit", rsi_exit=70)
    add("exit_and_bbmid_60", "require both RSI and BB-mid recovery to avoid premature exits", exit_mode="rsi_and_bbmid", rsi_exit=60)
    add("exit_bbmid_only", "strip RSI exit and trust mean reversion to the BB midline", exit_mode="bbmid_only")
    add("exit_rsi_only_65", "strip price-based exit and rely on RSI normalization only", exit_mode="rsi_only", rsi_exit=65)
    add("exit_rsi_or_ema20", "swap BB mid exit for EMA20 as a faster trend-aware exit", exit_mode="rsi_or_ema20")
    add("exit_ema20_only", "use EMA20 reclaim alone as the exit trigger", exit_mode="ema20_only")
    add("exit_rsi_or_bbupper", "hold until stronger reversion by using upper band exits", exit_mode="rsi_or_bbupper")
    add("exit_bbupper_only", "test full-band mean reversion without RSI exit help", exit_mode="bbupper_only")
    add("exit_and_ema20_60", "require RSI and EMA20 reclaim together for more selective exits", exit_mode="rsi_and_ema20", rsi_exit=60)
    add("exit_bbmid_or_ema20", "broaden exit options with either BB mid or EMA20 reclaim", exit_mode="bbmid_or_ema20")
    add("exit_rsi_72", "push RSI exit later to see whether the BB midline is already enough", rsi_exit=72)
    add("exit_rsi_58", "push RSI exit earlier to reduce giveback after entries", rsi_exit=58)

    add("entry_rsi18", "shorten RSI lookback for faster oversold detection", rsi_period=18)
    add("entry_rsi24", "lengthen RSI lookback for smoother oversold signals", rsi_period=24)
    add("entry_rsi28", "test even slower RSI smoothing for regime stability", rsi_period=28)
    add("entry_thresh_38", "tighten entry threshold slightly below the current setting", rsi_entry=38)
    add("entry_thresh_42", "loosen entry threshold slightly for more pullback trades", rsi_entry=42)
    add("entry_thresh_44", "loosen entry threshold more aggressively for higher participation", rsi_entry=44)
    add("entry_thresh_36", "tighten entry threshold more aggressively for stronger oversold setups", rsi_entry=36)
    add("entry_rsi18_thresh42", "combine faster RSI with a looser threshold to retain trade flow", rsi_period=18, rsi_entry=42)
    add("entry_rsi24_thresh38", "combine smoother RSI with a tighter threshold to filter noise", rsi_period=24, rsi_entry=38)
    add("entry_rsi28_thresh44", "pair slow RSI with a loose threshold to avoid starvation", rsi_period=28, rsi_entry=44)
    add("entry_rsi18_thresh38", "test fast RSI plus tighter threshold for sharper reversals", rsi_period=18, rsi_entry=38)
    add("entry_rsi24_thresh42", "test smoother RSI plus looser threshold for balanced flow", rsi_period=24, rsi_entry=42)
    add("entry_rsi_rising", "require RSI to turn up before entering mean reversion", require_rsi_rising=True)
    add("entry_green_candle", "require a green confirmation candle before entering", require_green_candle=True)
    add("entry_rising_green", "stack RSI-up and green-candle confirmation to reduce knife-catching", require_rsi_rising=True, require_green_candle=True)

    add("bb_period_18", "shorten Bollinger period for more reactive pullback bands", bb_period=18)
    add("bb_period_22", "lengthen Bollinger period slightly for smoother pullback bands", bb_period=22)
    add("bb_period_24", "lengthen Bollinger period further for more stable bands", bb_period=24)
    add("bb_dev_1_8", "tighten Bollinger width to catch shallower pullbacks", bb_dev=1.8)
    add("bb_dev_2_2", "widen Bollinger width to require deeper pullbacks", bb_dev=2.2)
    add("bb_dev_2_4", "widen Bollinger width further for rarer but deeper setups", bb_dev=2.4)
    add("bb18_dev1_8", "test a faster and tighter band together", bb_period=18, bb_dev=1.8)
    add("bb22_dev1_8", "test smoother but tighter bands", bb_period=22, bb_dev=1.8)
    add("bb18_dev2_2", "test faster but deeper pullback bands", bb_period=18, bb_dev=2.2)
    add("bb24_dev2_2", "test slower and deeper pullback bands", bb_period=24, bb_dev=2.2)
    add("entry_buffer_1_003", "allow entries slightly above the lower band to avoid missing near-touches", entry_buffer=1.003)
    add("entry_buffer_0_998", "require a cleaner break below the lower band", entry_buffer=0.998)
    add("entry_buffer_1_006", "allow even looser lower-band touches to increase sample size", entry_buffer=1.006)
    add("pullback_bb_or_ema20", "allow either a lower-band touch or a 1 percent EMA20 pullback", pullback_mode="bb_or_ema20pullback")
    add("pullback_ema20_only", "use only an EMA20 pullback instead of a lower-band breach", pullback_mode="ema20_pullback")
    add("pullback_bbmid", "enter on weaker pullbacks below the Bollinger midline", pullback_mode="bbmid_pullback")
    add("pullback_bb_and_ema20", "require both lower-band and EMA20 pullback confirmation", pullback_mode="bb_lower_and_ema20pullback")

    add("roi_0_008", "lower ROI target slightly to realize quicker mean-reversion wins", roi=0.008)
    add("roi_0_012", "raise ROI target slightly to let more moves develop", roi=0.012)
    add("roi_0_015", "raise ROI target more aggressively to see if stronger mean reversion pays", roi=0.015)
    add("sl_0_06", "tighten stoploss to cap downside sooner", stoploss=-0.06)
    add("sl_0_07", "tighten stoploss slightly", stoploss=-0.07)
    add("sl_0_09", "loosen stoploss slightly to avoid shakeouts", stoploss=-0.09)
    add("sl_0_10", "loosen stoploss more aggressively to tolerate deeper pullbacks", stoploss=-0.10)
    add("roi_0_008_sl_0_07", "pair quicker profit-taking with a slightly tighter stop", roi=0.008, stoploss=-0.07)
    add("roi_0_012_sl_0_09", "pair wider target with slightly looser stop for longer holds", roi=0.012, stoploss=-0.09)
    add(
        "trail_0_5_1_5",
        "turn on a light trailing stop once profit is established",
        trailing_stop=True,
        trailing_stop_positive=0.005,
        trailing_stop_positive_offset=0.015,
        trailing_only_offset_is_reached=True,
    )
    add(
        "trail_0_8_2_0",
        "test a slightly wider trailing stop to preserve trend continuation",
        trailing_stop=True,
        trailing_stop_positive=0.008,
        trailing_stop_positive_offset=0.020,
        trailing_only_offset_is_reached=True,
    )
    add(
        "trail_1_0_2_5",
        "test a wider trailing stop and offset for bigger reversions",
        trailing_stop=True,
        trailing_stop_positive=0.010,
        trailing_stop_positive_offset=0.025,
        trailing_only_offset_is_reached=True,
    )
    add(
        "trail_0_5_1_2",
        "engage a faster trailing stop to lock profits earlier",
        trailing_stop=True,
        trailing_stop_positive=0.005,
        trailing_stop_positive_offset=0.012,
        trailing_only_offset_is_reached=True,
    )
    add(
        "trail_0_8_1_5",
        "use a medium trailing stop with a smaller activation buffer",
        trailing_stop=True,
        trailing_stop_positive=0.008,
        trailing_stop_positive_offset=0.015,
        trailing_only_offset_is_reached=True,
    )
    add(
        "roi_0_008_trail",
        "combine lower ROI with a light trail to exit quicker while still protecting winners",
        roi=0.008,
        trailing_stop=True,
        trailing_stop_positive=0.005,
        trailing_stop_positive_offset=0.015,
        trailing_only_offset_is_reached=True,
    )
    add(
        "roi_0_012_trail",
        "combine higher ROI with a medium trail to keep upside open",
        roi=0.012,
        trailing_stop=True,
        trailing_stop_positive=0.008,
        trailing_stop_positive_offset=0.020,
        trailing_only_offset_is_reached=True,
    )

    add("trend_ema200_ema50", "require EMA50 to stay above EMA200 inside the current long regime", trend_mode="ema200_ema50")
    add("trend_ema200_ema20", "require price to reclaim EMA20 in addition to staying above EMA200", trend_mode="ema200_ema20")
    add("trend_ema200_slope6", "require EMA200 to slope up over the last 6 candles", trend_mode="ema200_slope6")
    add("trend_ema200_slope12", "require EMA200 to slope up over the last 12 candles", trend_mode="ema200_slope12")
    add("trend_ema50_200_slope", "require both EMA stack and EMA50 upslope", trend_mode="ema50_200_slope")
    add("trend_close_above_ema50", "require the pullback to stay above EMA50", require_close_above_ema50=True)
    add("trend_ema20_above_ema50", "require EMA20 to stay above EMA50 as a stronger local regime filter", require_ema20_above_ema50=True)
    add("trend_ema200_plus_ema20_gt_ema50", "stack EMA200 regime with EMA20 above EMA50", require_ema20_above_ema50=True)
    add("trend_ema200_slope24", "require a slower EMA200 upslope over the last 24 candles", trend_mode="ema200_slope24")
    add("trend_ema200_ema50_entry42", "test EMA50 stack with a slightly looser entry threshold", trend_mode="ema200_ema50", rsi_entry=42)
    add("trend_close_above_ema50_buffer", "pair looser band touches with an EMA50 floor", require_close_above_ema50=True, entry_buffer=1.003)
    add("trend_rsi_rising", "pair the regime filter with RSI turning up", require_rsi_rising=True)
    add("trend_green_candle", "pair the regime filter with green-candle confirmation", require_green_candle=True)
    add("trend_ema200_ema20_exit_ema20", "use EMA20-aware entry and exit together", trend_mode="ema200_ema20", exit_mode="rsi_or_ema20")
    add("trend_slope12_bb18", "pair an EMA200 upslope check with a faster Bollinger band", trend_mode="ema200_slope12", bb_period=18)

    add("exit_bbmid_cross", "exit only when price crosses back above the BB midline", exit_mode="bbmid_cross_only")
    add("exit_ema20_cross", "exit only when price crosses back above EMA20", exit_mode="ema20_cross_only")
    add("exit_rsi_or_bbmid_cross", "use RSI exit or a clean BB-mid cross instead of any close above midline", exit_mode="rsi_or_bbmid_cross")
    add("exit_rsi_or_ema20_cross", "use RSI exit or a clean EMA20 cross instead of any close above EMA20", exit_mode="rsi_or_ema20_cross")
    add("exit_bbupper_only_repeat", "retest upper-band exits from the current base state", exit_mode="bbupper_only")
    add("exit_rsi_or_bbupper_repeat", "retest RSI plus upper-band exits from the current base state", exit_mode="rsi_or_bbupper")
    add("exit_bbmid_only_repeat", "retest BB-mid-only exits from the current base state", exit_mode="bbmid_only")
    add("exit_ema20_only_repeat", "retest EMA20-only exits from the current base state", exit_mode="ema20_only")
    add("exit_rsi_only_60", "use only a faster RSI exit without price-based exits", exit_mode="rsi_only", rsi_exit=60)
    add("exit_rsi_only_70", "use only a slower RSI exit without price-based exits", exit_mode="rsi_only", rsi_exit=70)

    add("profit_only_true", "only honor exits when the trade is profitable", exit_profit_only=True)
    add(
        "profit_only_trail",
        "combine profit-only exits with a light trailing stop",
        exit_profit_only=True,
        trailing_stop=True,
        trailing_stop_positive=0.005,
        trailing_stop_positive_offset=0.015,
        trailing_only_offset_is_reached=True,
    )
    add("ignore_roi_on_reentry", "ignore ROI while the entry condition still holds", ignore_roi_if_entry_signal=True)
    add("ignore_roi_with_ema20_exit", "ignore ROI under persistent entry conditions while exiting on EMA20 reclaims", ignore_roi_if_entry_signal=True, exit_mode="rsi_or_ema20")
    add("no_exit_signal", "disable indicator exits and rely only on ROI or stoploss", use_exit_signal=False)
    add("no_exit_signal_roi_0_008", "disable indicator exits and lower ROI to test pure mean-reversion harvesting", use_exit_signal=False, roi=0.008)
    add("no_exit_signal_sl_0_06", "disable indicator exits and tighten the stop to reduce pure stoploss bleed", use_exit_signal=False, stoploss=-0.06)
    add("entry_rising_and_exit_and", "pair RSI-up entry confirmation with a stricter exit confirmation", require_rsi_rising=True, exit_mode="rsi_and_bbmid", rsi_exit=60)
    add("entry_buffer_upper_exit", "allow looser lower-band touches and exit on stronger upper-band reversions", entry_buffer=1.002, exit_mode="rsi_or_bbupper")
    add("combo_42_and_ema20_exit", "loosen entries a bit and use EMA20-aware exits with a tighter stop", rsi_entry=42, exit_mode="rsi_and_ema20", rsi_exit=60, stoploss=-0.07)
    add("combo_38_bb18_roi12", "tighten entries while using faster bands and a slightly larger target", rsi_entry=38, bb_period=18, roi=0.012)
    add("combo_44_buffer_exit62", "loosen entries slightly, allow near-band touches, and exit a bit earlier on RSI", rsi_entry=44, entry_buffer=1.003, rsi_exit=62)

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
    bbmid = '(dataframe["close"] > dataframe["bb_middle"])'
    ema20 = '(dataframe["close"] > dataframe["ema20"])'
    bbupper = '(dataframe["close"] > dataframe["bb_upper"])'
    bbmid_cross = '((dataframe["close"] > dataframe["bb_middle"]) & (dataframe["close"].shift(1) <= dataframe["bb_middle"].shift(1)))'
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
    if mode == "bbmid_or_ema20":
        return f"({bbmid} | {ema20})"
    if mode == "rsi_or_bbupper":
        return f"({rsi} | {bbupper})"
    if mode == "bbupper_only":
        return bbupper
    if mode == "bbmid_cross_only":
        return bbmid_cross
    if mode == "ema20_cross_only":
        return ema20_cross
    if mode == "rsi_or_bbmid_cross":
        return f"({rsi} | {bbmid_cross})"
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
    result = run([*SAFE_GIT, "commit", "-m", message, "--", str(STRATEGY_PATH.relative_to(REPO))], capture_output=True)
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
