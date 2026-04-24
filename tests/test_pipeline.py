from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from autoq_data.pipeline import prepare_enriched_datasets
from autoq_data.transforms import CORE_OHLCV_COLUMNS


def _write_base_pair(path: Path) -> None:
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(
                [
                    "2023-01-02 00:00:00+00:00",
                    "2023-01-02 01:00:00+00:00",
                    "2023-01-03 00:00:00+00:00",
                ],
                utc=True,
            ),
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
            "volume": [10.0, 11.0, 12.0],
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_feather(path)


class FakeSourceClient:
    def __init__(self) -> None:
        self.optional_failures: dict[str, str] = {
            "dvol": "deribit unavailable",
            "stablecoins": "defillama unavailable",
        }
        self.funding_symbols: list[str] = []
        self.open_interest_symbols: list[str] = []

    def load_pair_spot_klines(self, symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "date": pd.to_datetime(
                    [
                        "2023-01-02 00:00:00+00:00",
                        "2023-01-02 01:00:00+00:00",
                        "2023-01-03 00:00:00+00:00",
                    ],
                    utc=True,
                ),
                "volume": [10.0, 11.0, 12.0],
                "taker_buy_base_volume": [7.0, 4.0, 6.0],
            }
        )

    def load_funding_rate(self, symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        self.funding_symbols.append(symbol)
        return pd.DataFrame(
            {
                "date": pd.to_datetime(["2023-01-02 00:00:00+00:00"], utc=True),
                "funding_rate": [0.001],
            }
        )

    def load_open_interest(self, symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        self.open_interest_symbols.append(symbol)
        return pd.DataFrame(
            {
                "date": pd.to_datetime(
                    ["2023-01-02 00:00:00+00:00", "2023-01-02 01:00:00+00:00"], utc=True
                ),
                "open_interest": [1000.0, 1001.0],
            }
        )

    def load_macro_liquidity(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "date": pd.to_datetime(["2023-01-01 00:00:00+00:00", "2023-01-02 00:00:00+00:00"], utc=True),
                "us10y_close": [3.80, 3.90],
                "dxy_close": [103.0, 104.0],
                "fed_net_liquidity": [5000.0, 4900.0],
            }
        )

    def load_dvol(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        raise RuntimeError(self.optional_failures["dvol"])

    def load_stablecoin_marketcap(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        raise RuntimeError(self.optional_failures["stablecoins"])


class RequiredSourceFailureClient(FakeSourceClient):
    def load_macro_liquidity(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        raise RuntimeError("fred unavailable")


def test_prepare_enriched_datasets_writes_enriched_files_and_manifest(tmp_path: Path) -> None:
    data_dir = tmp_path / "user_data" / "data"
    canonical_dir = data_dir / "binance"
    _write_base_pair(canonical_dir / "BTC_USDT-1h.feather")
    _write_base_pair(canonical_dir / "ETH_USDT-1h.feather")

    prepare_enriched_datasets(
        data_dir=data_dir,
        exchange="binance",
        pairs=["BTC/USDT", "ETH/USDT"],
        source_client=FakeSourceClient(),
        download_ohlcv=lambda: None,
    )

    btc = pd.read_feather(canonical_dir / "BTC_USDT-1h.feather")
    eth = pd.read_feather(canonical_dir / "ETH_USDT-1h.feather")
    mirror = pd.read_feather(data_dir / "BTC_USDT-1h.feather")
    enriched_btc = pd.read_feather(data_dir / "_cache" / "enriched" / "binance" / "BTC_USDT-1h.feather")
    manifest = json.loads((data_dir / "_cache" / "factor_manifest.json").read_text(encoding="utf-8"))

    required_columns = {
        "taker_buy_base_volume",
        "taker_sell_base_volume",
        "taker_delta_volume",
        "cvd",
        "funding_rate",
        "open_interest",
        "us10y_close",
        "dxy_close",
        "fed_net_liquidity",
        "btc_dvol",
        "stablecoin_mcap",
        "stablecoin_mcap_growth",
    }

    assert list(btc.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert list(eth.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert list(mirror.columns) == list(btc.columns)
    assert len(enriched_btc) == len(btc)
    assert enriched_btc["date"].tolist() == btc["date"].tolist()
    assert list(enriched_btc.loc[:, CORE_OHLCV_COLUMNS].columns) == list(btc.columns)
    assert required_columns.issubset(set(enriched_btc.columns))
    assert manifest["optional_sources"]["dvol"]["status"] == "unavailable"
    assert manifest["optional_sources"]["stablecoins"]["status"] == "unavailable"


def test_prepare_enriched_datasets_is_idempotent_for_schema_and_row_count(tmp_path: Path) -> None:
    data_dir = tmp_path / "user_data" / "data"
    canonical_dir = data_dir / "binance"
    _write_base_pair(canonical_dir / "BTC_USDT-1h.feather")
    _write_base_pair(canonical_dir / "ETH_USDT-1h.feather")

    kwargs = {
        "data_dir": data_dir,
        "exchange": "binance",
        "pairs": ["BTC/USDT", "ETH/USDT"],
        "source_client": FakeSourceClient(),
        "download_ohlcv": lambda: None,
    }

    prepare_enriched_datasets(**kwargs)
    first = pd.read_feather(canonical_dir / "BTC_USDT-1h.feather")

    prepare_enriched_datasets(**kwargs)
    second = pd.read_feather(canonical_dir / "BTC_USDT-1h.feather")

    assert len(first) == len(second)
    assert list(first.columns) == list(second.columns)
    assert first["date"].tolist() == second["date"].tolist()


def test_prepare_enriched_datasets_uses_pair_specific_perpetual_symbols(tmp_path: Path) -> None:
    data_dir = tmp_path / "user_data" / "data"
    canonical_dir = data_dir / "binance"
    _write_base_pair(canonical_dir / "BTC_USDT-1h.feather")
    _write_base_pair(canonical_dir / "ETH_USDT-1h.feather")
    source_client = FakeSourceClient()

    prepare_enriched_datasets(
        data_dir=data_dir,
        exchange="binance",
        pairs=["BTC/USDT", "ETH/USDT"],
        source_client=source_client,
        download_ohlcv=lambda: None,
    )

    assert source_client.funding_symbols == ["BTCUSDT", "ETHUSDT"]
    assert source_client.open_interest_symbols == ["BTCUSDT", "ETHUSDT"]


def test_prepare_enriched_datasets_aborts_when_required_source_fails(tmp_path: Path) -> None:
    data_dir = tmp_path / "user_data" / "data"
    canonical_dir = data_dir / "binance"
    _write_base_pair(canonical_dir / "BTC_USDT-1h.feather")
    _write_base_pair(canonical_dir / "ETH_USDT-1h.feather")

    with pytest.raises(RuntimeError, match="Required source failed: macro_liquidity"):
        prepare_enriched_datasets(
            data_dir=data_dir,
            exchange="binance",
            pairs=["BTC/USDT", "ETH/USDT"],
            source_client=RequiredSourceFailureClient(),
            download_ohlcv=lambda: None,
        )
