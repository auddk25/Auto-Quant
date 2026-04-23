from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENRICHED_ROOT = PROJECT_ROOT / "user_data" / "data" / "_cache" / "enriched" / "binance"


def merge_external_factors(
    dataframe: pd.DataFrame,
    metadata: dict[str, Any],
    *,
    columns: list[str],
    enriched_root: Path | None = None,
) -> pd.DataFrame:
    merged = dataframe.copy()
    merged["date"] = pd.to_datetime(merged["date"], utc=True)

    pair = metadata.get("pair", "")
    if not pair:
        for column in columns:
            if column not in merged.columns:
                merged[column] = np.nan
        return merged

    root = _resolve_enriched_root(enriched_root)
    sidecar_path = root / f"{pair.replace('/', '_')}-1h.feather"
    factors = _load_sidecar(sidecar_path)

    if factors is None:
        for column in columns:
            if column not in merged.columns:
                merged[column] = np.nan
        return merged

    available_columns = [column for column in columns if column in factors.columns]
    selected = factors.loc[:, ["date", *available_columns]].copy()
    selected["date"] = pd.to_datetime(selected["date"], utc=True)

    result = merged.merge(selected, on="date", how="left")
    for column in columns:
        if column not in result.columns:
            result[column] = np.nan
    return result


@lru_cache(maxsize=16)
def _load_sidecar(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    return pd.read_feather(path)


def _resolve_enriched_root(enriched_root: Path | None) -> Path:
    if enriched_root is not None:
        return enriched_root.resolve()
    env_root = os.environ.get("AUTOQ_ENRICHED_ROOT")
    if env_root:
        return Path(env_root).resolve()
    return DEFAULT_ENRICHED_ROOT.resolve()
