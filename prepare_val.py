"""
prepare_val.py

Download BTC/USDT and ETH/USDT 1h OHLCV for the 2026 out-of-sample validation
window, then build enriched factor sidecar files in user_data/data_val/.

Run this once before the first `uv run val.py`. Re-running is safe (idempotent).

Usage:
    uv run prepare_val.py
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import talib  # noqa: F401
except ImportError:
    print(
        "ERROR: TA-Lib is not installed.\n"
        "Two install paths (see README.md):\n"
        "  1. Native: `brew install ta-lib` then `uv sync`\n"
        "  2. Docker fallback: `docker compose run --rm freqtrade ...`\n",
        file=sys.stderr,
    )
    sys.exit(1)

from freqtrade.commands.data_commands import start_download_data  # noqa: E402

from autoq_data import prepare_enriched_datasets  # noqa: E402

PROJECT_DIR = Path(__file__).parent.resolve()
USER_DATA = PROJECT_DIR / "user_data"
CONFIG = PROJECT_DIR / "config.json"

EXCHANGE = "binance"
PAIRS = ["BTC/USDT", "ETH/USDT"]
TIMEFRAMES = ["1h"]
TIMERANGE = "20260101-20260420"
VAL_DATA_DIR = USER_DATA / "data_val"


def data_exists() -> bool:
    data_dir = VAL_DATA_DIR / EXCHANGE
    for pair in PAIRS:
        filename = f"{pair.replace('/', '_')}-1h.feather"
        if not (data_dir / filename).exists():
            return False
    return True


def download() -> None:
    args = {
        "config": [str(CONFIG)],
        "user_data_dir": str(USER_DATA),
        "datadir": str(VAL_DATA_DIR),
        "exchange": EXCHANGE,
        "pairs": PAIRS,
        "timeframes": TIMEFRAMES,
        "timerange": TIMERANGE,
        "dataformat_ohlcv": "feather",
        "dataformat_trades": "feather",
        "download_trades": False,
        "trading_mode": "spot",
        "prepend_data": False,
        "erase": False,
        "include_inactive_pairs": False,
        "new_pairs_days": 30,
    }
    start_download_data(args)


def main() -> None:
    print(f"Exchange:   {EXCHANGE}")
    print(f"Pairs:      {PAIRS}")
    print(f"Timeframes: {TIMEFRAMES}")
    print(f"Timerange:  {TIMERANGE}")
    print(f"Dest:       {VAL_DATA_DIR / EXCHANGE}")
    print()

    if data_exists():
        print("Base OHLCV already present. Refreshing enriched factors.")
    else:
        download()

    if not data_exists():
        print(
            "ERROR: download appeared to succeed but expected files are missing.\n"
            f"Check {VAL_DATA_DIR / EXCHANGE}/",
            file=sys.stderr,
        )
        sys.exit(1)

    prepare_enriched_datasets(
        data_dir=VAL_DATA_DIR,
        exchange=EXCHANGE,
        pairs=PAIRS,
        download_ohlcv=None,
    )

    print()
    print("Ready.")


if __name__ == "__main__":
    main()
