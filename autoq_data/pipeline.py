from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .sources import SourceClient
from .transforms import core_ohlcv_view, enrich_pair_dataframe


PAIR_SYMBOLS = {
    "BTC/USDT": {"spot": "BTCUSDT", "perp": "BTCUSDT"},
    "ETH/USDT": {"spot": "ETHUSDT", "perp": "ETHUSDT"},
}

REQUIRED_SOURCE_NAMES = ["spot_klines", "funding_rate", "open_interest", "macro_liquidity"]
OPTIONAL_SOURCE_NAMES = ["dvol", "stablecoins"]


@dataclass
class SourceStatus:
    status: str
    detail: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"status": self.status}
        if self.detail:
            payload["detail"] = self.detail
        return payload


def prepare_enriched_datasets(
    *,
    data_dir: Path,
    exchange: str,
    pairs: list[str],
    source_client: SourceClient | None = None,
    download_ohlcv: callable | None = None,
) -> dict[str, Any]:
    if download_ohlcv is not None:
        download_ohlcv()

    canonical_dir = data_dir / exchange
    canonical_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = data_dir / "_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    enriched_dir = cache_dir / "enriched" / exchange
    enriched_dir.mkdir(parents=True, exist_ok=True)

    client = source_client or SourceClient(cache_dir=cache_dir)
    pair_frames = {
        pair: core_ohlcv_view(pd.read_feather(canonical_dir / _pair_filename(pair))) for pair in pairs
    }

    ranges = pd.concat([frame.loc[:, ["date"]] for frame in pair_frames.values()], ignore_index=True)
    start = ranges["date"].min()
    end = ranges["date"].max()

    required_status: dict[str, SourceStatus] = {}
    optional_status: dict[str, SourceStatus] = {}

    macro_frame = _load_required(
        required_status,
        "macro_liquidity",
        lambda: client.load_macro_liquidity(start, end),
    )
    try:
        dvol_frame = client.load_dvol(start, end)
        optional_status["dvol"] = SourceStatus("ok")
    except Exception as exc:  # noqa: BLE001
        dvol_frame = None
        optional_status["dvol"] = SourceStatus("unavailable", str(exc))

    try:
        stablecoin_frame = client.load_stablecoin_marketcap(start, end)
        optional_status["stablecoins"] = SourceStatus("ok")
    except Exception as exc:  # noqa: BLE001
        stablecoin_frame = None
        optional_status["stablecoins"] = SourceStatus("unavailable", str(exc))

    written_files: dict[str, dict[str, str]] = {}
    for pair in pairs:
        symbol_map = PAIR_SYMBOLS[pair]
        spot_frame = _load_required(
            required_status,
            f"spot_klines:{symbol_map['spot']}",
            lambda symbol=symbol_map["spot"]: client.load_pair_spot_klines(symbol, start, end),
        )
        funding_frame = _load_required(
            required_status,
            f"funding_rate:{symbol_map['perp']}",
            lambda symbol=symbol_map["perp"]: client.load_funding_rate(symbol, start, end),
        )
        open_interest_frame = _load_required(
            required_status,
            f"open_interest:{symbol_map['perp']}",
            lambda symbol=symbol_map["perp"]: client.load_open_interest(symbol, start, end),
        )

        enriched = enrich_pair_dataframe(
            base_frame=pair_frames[pair],
            spot_frame=spot_frame,
            funding_frame=funding_frame,
            open_interest_frame=open_interest_frame,
            macro_frame=macro_frame,
            dvol_frame=dvol_frame,
            stablecoin_frame=stablecoin_frame,
        )
        canonical_frame = core_ohlcv_view(pair_frames[pair])

        canonical_path = canonical_dir / _pair_filename(pair)
        mirror_path = data_dir / _pair_filename(pair)
        enriched_path = enriched_dir / _pair_filename(pair)
        canonical_frame.to_feather(canonical_path)
        canonical_frame.to_feather(mirror_path)
        enriched.to_feather(enriched_path)
        written_files[pair] = {
            "canonical": str(canonical_path),
            "mirror": str(mirror_path),
            "enriched": str(enriched_path),
        }

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "pairs": pairs,
        "required_sources": {name: status.as_dict() for name, status in required_status.items()},
        "optional_sources": {name: status.as_dict() for name, status in optional_status.items()},
        "written_files": written_files,
    }
    (cache_dir / "factor_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _load_required(
    status_map: dict[str, SourceStatus], name: str, loader: callable
) -> pd.DataFrame:
    try:
        frame = loader()
    except Exception as exc:  # noqa: BLE001
        status_map[name] = SourceStatus("failed", str(exc))
        raise RuntimeError(f"Required source failed: {name}: {exc}") from exc
    status_map[name] = SourceStatus("ok")
    return frame


def _pair_filename(pair: str) -> str:
    return f"{pair.replace('/', '_')}-1h.feather"
