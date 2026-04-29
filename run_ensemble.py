"""run_ensemble.py — Run ensemble strategy backtest."""
from __future__ import annotations
import sys
from pathlib import Path

import aiohttp.connector, aiohttp.resolver
aiohttp.connector.DefaultResolver = aiohttp.resolver.ThreadedResolver

from freqtrade.configuration import Configuration
from freqtrade.enums import RunMode
from freqtrade.optimize.backtesting import Backtesting

PROJECT = Path(__file__).parent
USER_DATA = PROJECT / "user_data"
STRATEGIES = USER_DATA / "strategies"
CONFIG = PROJECT / "config.json"
DATA = USER_DATA / "data"


def main():
    args = {
        "config": [str(CONFIG)], "user_data_dir": str(USER_DATA),
        "datadir": str(DATA), "strategy": "MtfTrendCbbiMomentumEnsemble",
        "strategy_path": str(STRATEGIES), "timerange": "20230101-20251231",
        "export": "none", "exportfilename": None, "cache": "none",
    }
    config = Configuration(args, RunMode.BACKTEST).get_config()
    bt = Backtesting(config)
    bt.start()

    results = bt.results
    strat = results.get("strategy", {}).get("MtfTrendCbbiMomentumEnsemble", {})
    per_pair = strat.get("results_per_pair", []) or []
    for e in per_pair:
        if e.get("key") == "BTC/USDT":
            print(f"Profit: {e.get('profit_total_pct', 0):.1f}%")
            print(f"Trades: {e.get('trades', 0)}")
            print(f"Win rate: {e.get('winrate', 0)*100:.1f}%")
            print(f"Profit factor: {e.get('profit_factor', 0):.2f}")
            print(f"Max DD: {e.get('max_drawdown_account', 0)*100:.1f}%")
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
