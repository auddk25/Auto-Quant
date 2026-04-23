from __future__ import annotations

import json
from pathlib import Path
import tomllib


def test_binance_async_ccxt_uses_trust_env_for_dns_resolution() -> None:
    config = json.loads(Path("config.json").read_text(encoding="utf-8"))
    exchange = config["exchange"]

    assert exchange["ccxt_async_config"]["aiohttp_trust_env"] is True


def test_project_metadata_tracks_v030_release() -> None:
    metadata = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert metadata["project"]["version"] == "0.3.0"
