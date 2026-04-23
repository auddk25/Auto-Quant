from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
ROUND7_PATH = REPO / ".tmp" / "autoresearch_batch_round7.py"


def load_round7_module():
    spec = importlib.util.spec_from_file_location("autoresearch_batch_round7_base", ROUND7_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def build_candidates() -> list[dict]:
    specs: list[dict] = []

    def add(label: str, rationale: str, **updates) -> None:
        specs.append({"label": label, "rationale": rationale, "updates": updates})

    roi_values = [0.0085, 0.0090, 0.0100, 0.0120]
    rsi_exit_values = [58, 59, 61, 62, 64]
    exit_modes = [
        "rsi_or_bbmid",
        "rsi_only",
        "bbmid_only",
        "rsi_and_bbmid_cross",
        "rsi_and_ema20",
        "rsi_and_bbupper",
        "bbmid_or_ema20",
        "rsi_or_bbupper",
    ]

    add("single_roi0085", "raise ROI modestly above the new winner to see if profits can run further", roi=0.0085)
    add("single_roi0090", "raise ROI to 0.009 to probe a more ambitious take-profit in the ADX winner family", roi=0.0090)
    add("single_roi0100", "raise ROI to 0.010 to test whether the new winner still exits too early", roi=0.0100)
    add("single_roi0120", "push ROI noticeably higher to see whether the ADX winner can carry a wider profit target", roi=0.0120)
    add("single_exit58", "make the RSI side of the exit a bit earlier while keeping the same price leg", rsi_exit=58)
    add("single_exit59", "make the RSI side of the exit slightly earlier around the current winner", rsi_exit=59)
    add("single_exit61", "make the RSI side of the exit slightly later around the current winner", rsi_exit=61)
    add("single_exit62", "make the RSI side of the exit later to hold winners a bit longer", rsi_exit=62)
    add("single_exit64", "make the RSI side of the exit materially later to test a more patient release", rsi_exit=64)
    add("single_mode_rsi_or_bbmid", "let either RSI or a mid-band reclaim trigger the exit", exit_mode="rsi_or_bbmid")
    add("single_mode_rsi_only", "use only RSI for exits so price no longer has to confirm the release", exit_mode="rsi_only")
    add("single_mode_bbmid_only", "use only the Bollinger-mid reclaim for exits", exit_mode="bbmid_only")
    add("single_mode_bbmid_cross", "require a clean mid-band cross instead of any close above the mid-band", exit_mode="rsi_and_bbmid_cross")
    add("single_mode_ema20", "swap the price side of the exit to EMA20 reclaim", exit_mode="rsi_and_ema20")
    add("single_mode_bbupper", "make the price side of the exit much more patient by requiring the upper band", exit_mode="rsi_and_bbupper")
    add("single_mode_bbmid_or_ema20", "allow either a mid-band or EMA20 reclaim to release the trade", exit_mode="bbmid_or_ema20")
    add("single_mode_rsi_or_bbupper", "allow either RSI or an upper-band touch to release the trade", exit_mode="rsi_or_bbupper")
    add("single_no_exit_signal", "disable strategy exits entirely and let ROI or stoploss manage trades", use_exit_signal=False)
    add("single_profit_only", "allow exit signals only when trades are already profitable", exit_profit_only=True)
    add("single_no_exit_tight_stop", "disable exit signals but tighten stoploss so losers cannot drift for long", use_exit_signal=False, stoploss=-0.03)

    for roi in roi_values:
        for rsi_exit in rsi_exit_values:
            add(
                f"roi_{str(roi).replace('.', '_')}_exit{rsi_exit}",
                "map how a higher profit target interacts with different RSI release thresholds",
                roi=roi,
                rsi_exit=rsi_exit,
            )

    for roi in roi_values:
        for exit_mode in exit_modes:
            add(
                f"roi_{str(roi).replace('.', '_')}_{exit_mode}",
                "map how a higher ROI interacts with different exit architectures in the ADX winner family",
                roi=roi,
                exit_mode=exit_mode,
            )

    for roi in roi_values:
        add(
            f"noexit_roi_{str(roi).replace('.', '_')}",
            "disable exit signals and let ROI plus stoploss manage trades at this profit target",
            roi=roi,
            use_exit_signal=False,
        )
        add(
            f"profitonly_roi_{str(roi).replace('.', '_')}",
            "keep exit signals only when the trade is already green at this profit target",
            roi=roi,
            exit_profit_only=True,
        )
        add(
            f"noexit_stop03_roi_{str(roi).replace('.', '_')}",
            "disable exit signals and pair the higher ROI with a tight stoploss",
            roi=roi,
            use_exit_signal=False,
            stoploss=-0.03,
        )
        add(
            f"noexit_stop05_roi_{str(roi).replace('.', '_')}",
            "disable exit signals and pair the higher ROI with a medium stoploss",
            roi=roi,
            use_exit_signal=False,
            stoploss=-0.05,
        )
        add(
            f"profitonly_exit58_roi_{str(roi).replace('.', '_')}",
            "keep profit-only exits and make the RSI release slightly earlier",
            roi=roi,
            exit_profit_only=True,
            rsi_exit=58,
        )
        add(
            f"profitonly_exit62_roi_{str(roi).replace('.', '_')}",
            "keep profit-only exits and make the RSI release slightly later",
            roi=roi,
            exit_profit_only=True,
            rsi_exit=62,
        )

    add("focus_roi009_exit58_orbbmid", "pair a slightly higher ROI with an earlier and more active release", roi=0.0090, rsi_exit=58, exit_mode="rsi_or_bbmid")
    add("focus_roi009_exit62_cross", "pair a slightly higher ROI with a later and more confirmation-heavy release", roi=0.0090, rsi_exit=62, exit_mode="rsi_and_bbmid_cross")
    add("focus_roi010_exit58_bbmidonly", "push ROI higher but allow mid-band reclaim alone to bank profits", roi=0.0100, rsi_exit=58, exit_mode="bbmid_only")
    add("focus_roi010_exit62_bbupper", "push ROI higher and require a very patient price release", roi=0.0100, rsi_exit=62, exit_mode="rsi_and_bbupper")
    add("focus_roi012_noexit_stop03", "test whether the ADX winner can run much further with only ROI and a tight safety stop", roi=0.0120, use_exit_signal=False, stoploss=-0.03)
    add("focus_roi012_profitonly_exit58", "combine a much higher ROI with profit-only exits that release a bit earlier", roi=0.0120, exit_profit_only=True, rsi_exit=58)
    add("focus_roi0085_exit59_orbbupper", "slightly raise ROI and allow either RSI or an upper-band touch to release", roi=0.0085, rsi_exit=59, exit_mode="rsi_or_bbupper")
    add("focus_roi010_exit61_bbmidorema20", "push ROI higher and allow either mid-band or EMA20 reclaim to close", roi=0.0100, rsi_exit=61, exit_mode="bbmid_or_ema20")
    add("focus_roi009_noexit_stop05", "slightly higher ROI with no exit signal and a medium stop to contain drift", roi=0.0090, use_exit_signal=False, stoploss=-0.05)
    add("focus_roi012_exit64_rsionly", "much higher ROI with a very patient RSI-only release", roi=0.0120, rsi_exit=64, exit_mode="rsi_only")

    if len(specs) < 100:
        raise RuntimeError(f"Expected at least 100 candidates, got {len(specs)}")
    return specs


def configure_round8(mod) -> None:
    mod.STATE_PATH = REPO / ".tmp" / "autoresearch_state_round8.json"
    mod.INITIAL_PARAMS = {
        "rsi_period": 20,
        "rsi_entry": 40,
        "rsi_exit": 60,
        "roi": 0.008,
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
        "adx_period": 14,
        "adx_min": 19,
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
    mod.INITIAL_BEST = {
        "commit": "dd3793c",
        "sharpe": 1.6576,
        "total_profit_pct": 28.1364,
        "max_drawdown_pct": -1.3658,
        "trade_count": 66,
        "profit_factor": 15.4635,
        "utility": 1.925306,
    }
    mod.CANDIDATES = build_candidates()


def main() -> int:
    mod = load_round7_module()
    configure_round8(mod)
    return mod.main()


if __name__ == "__main__":
    sys.exit(main())
