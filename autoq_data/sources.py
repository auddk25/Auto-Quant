from __future__ import annotations

import io
import json
import math
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
import pandas_datareader.data as pdr
import yfinance as yf


BINANCE_DATA_ROOT = "https://data.binance.vision/data"
BINANCE_SPOT_REST = "https://api.binance.com/api/v3/klines"
DERIBIT_DVOL_URL = "https://www.deribit.com/api/v2/public/get_volatility_index_data"
DEFILLAMA_STABLECOINS_URL = "https://stablecoins.llama.fi/stablecoincharts/all"


def normalize_binance_epoch_series(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    use_microseconds = numeric.abs() >= 10**15
    parsed = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns, UTC]")
    if (~use_microseconds).any():
        parsed.loc[~use_microseconds] = pd.to_datetime(
            numeric.loc[~use_microseconds], unit="ms", utc=True
        )
    if use_microseconds.any():
        parsed.loc[use_microseconds] = pd.to_datetime(
            numeric.loc[use_microseconds], unit="us", utc=True
        )
    return parsed


@dataclass(frozen=True)
class CacheKey:
    name: str
    start: str
    end: str

    def as_filename(self) -> str:
        return f"{self.name}_{self.start}_{self.end}.feather"


class SourceClient:
    def __init__(self, cache_dir: Path, timeout: int = 30, max_workers: int = 8) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.max_workers = max_workers

    def load_pair_spot_klines(
        self, symbol: str, start: pd.Timestamp, end: pd.Timestamp
    ) -> pd.DataFrame:
        key = CacheKey(f"spot_klines_{symbol}_1h", start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
        cached = self._read_cache(key)
        if cached is not None:
            return cached

        months = self._month_starts(start, end)
        frames = [self._read_binance_spot_month(symbol, month) for month in months]
        combined = pd.concat(frames, ignore_index=True)
        combined["date"] = normalize_binance_epoch_series(combined["open_time"])
        combined["volume"] = pd.to_numeric(combined["volume"], errors="coerce")
        combined["taker_buy_base_volume"] = pd.to_numeric(
            combined["taker_buy_base_volume"], errors="coerce"
        )
        result = combined.loc[
            (combined["date"] >= start) & (combined["date"] <= end),
            ["date", "volume", "taker_buy_base_volume"],
        ].drop_duplicates(subset=["date"]).sort_values("date")
        self._write_cache(key, result)
        return result.reset_index(drop=True)

    def load_funding_rate(self, symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        key = CacheKey(f"funding_rate_{symbol}", start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
        cached = self._read_cache(key)
        if cached is not None:
            return cached

        months = self._month_starts(start, end)
        frames: list[pd.DataFrame] = []
        for month in months:
            try:
                frames.append(self._read_binance_funding_month(symbol, month))
            except RuntimeError:
                # Monthly archive not yet published (in-progress month) — fall back to daily files.
                days = pd.date_range(month, periods=32, freq="D", tz="UTC")
                for day in days:
                    if day.month != month.month or day > end:
                        break
                    try:
                        frames.append(self._read_binance_funding_day(symbol, day))
                    except RuntimeError:
                        break
        if not frames:
            raise RuntimeError(f"No funding rate data could be fetched for {symbol} ({start} – {end})")
        combined = pd.concat(frames, ignore_index=True)
        combined["date"] = pd.to_datetime(combined["calc_time"], unit="ms", utc=True).dt.floor("h")
        combined["funding_rate"] = pd.to_numeric(combined["last_funding_rate"], errors="coerce")
        hourly_index = pd.date_range(start=start.floor("h"), end=end.floor("h"), freq="1h", tz="UTC")
        result = (
            combined.loc[:, ["date", "funding_rate"]]
            .dropna(subset=["date"])
            .drop_duplicates(subset=["date"], keep="last")
            .set_index("date")
            .reindex(hourly_index)
            .ffill()
            .rename_axis("date")
            .reset_index()
        )
        self._write_cache(key, result)
        return result

    def load_open_interest(self, symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        key = CacheKey(f"open_interest_{symbol}", start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
        cached = self._read_cache(key)
        if cached is not None:
            return cached

        days = pd.date_range(start.normalize(), end.normalize(), freq="1D", tz="UTC")
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            frames = list(executor.map(lambda day: self._read_binance_metrics_day(symbol, day), days))

        combined = pd.concat(frames, ignore_index=True)
        combined["date"] = pd.to_datetime(combined["create_time"], utc=True).dt.floor("h")
        combined["open_interest"] = pd.to_numeric(combined["sum_open_interest"], errors="coerce")
        result = (
            combined.loc[:, ["date", "open_interest"]]
            .groupby("date", as_index=False)
            .last()
            .sort_values("date")
        )
        result = result.loc[(result["date"] >= start) & (result["date"] <= end)].reset_index(drop=True)
        self._write_cache(key, result)
        return result

    def load_macro_liquidity(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        key = CacheKey("macro_liquidity", start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
        cached = self._read_cache(key)
        if cached is not None:
            return cached

        start_date = (start - pd.Timedelta(days=14)).date()
        end_date = (end + pd.Timedelta(days=7)).date()

        tnx = self._download_yfinance_close("^TNX", start_date, end_date, "us10y_close")
        dxy = self._download_yfinance_close("DX-Y.NYB", start_date, end_date, "dxy_close")

        fred = pdr.DataReader(["WALCL", "WTREGEN", "RRPONTSYD"], "fred", start_date, end_date)
        fred.index = pd.to_datetime(fred.index, utc=True)
        fred = fred.rename_axis("date").reset_index()
        fred["fed_net_liquidity"] = (
            pd.to_numeric(fred["WALCL"], errors="coerce")
            - pd.to_numeric(fred["WTREGEN"], errors="coerce")
            - pd.to_numeric(fred["RRPONTSYD"], errors="coerce") * 1000.0
        )
        fred = fred.loc[:, ["date", "fed_net_liquidity"]]

        daily_index = pd.date_range(start.normalize(), end.normalize(), freq="1D", tz="UTC")
        macro = (
            pd.DataFrame({"date": daily_index})
            .merge(tnx, on="date", how="left")
            .merge(dxy, on="date", how="left")
            .merge(fred, on="date", how="left")
            .sort_values("date")
            .ffill()
        )
        self._write_cache(key, macro)
        return macro

    def load_dvol(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        key = CacheKey("btc_dvol", start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
        cached = self._read_cache(key)
        if cached is not None:
            return cached

        frames: list[pd.DataFrame] = []
        start_ms = int(start.timestamp() * 1000)
        cursor_end = int(end.timestamp() * 1000)
        while cursor_end >= start_ms:
            payload = self._get_json(
                DERIBIT_DVOL_URL,
                {
                    "currency": "BTC",
                    "start_timestamp": start_ms,
                    "end_timestamp": cursor_end,
                    "resolution": 3600,
                },
            )
            result = payload.get("result", {})
            data = result.get("data", [])
            if not data:
                break

            frame = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close"])
            frames.append(frame)
            continuation = result.get("continuation")
            if continuation is None:
                break
            cursor_end = int(continuation)

        if not frames:
            raise RuntimeError("Deribit returned no DVOL history for requested range")

        combined = pd.concat(frames, ignore_index=True)
        combined["date"] = pd.to_datetime(combined["timestamp"], unit="ms", utc=True)
        combined["btc_dvol"] = pd.to_numeric(combined["close"], errors="coerce")
        result = (
            combined.loc[:, ["date", "btc_dvol"]]
            .drop_duplicates(subset=["date"], keep="last")
            .sort_values("date")
        )
        result = result.loc[(result["date"] >= start) & (result["date"] <= end)].reset_index(drop=True)
        self._write_cache(key, result)
        return result

    def load_stablecoin_marketcap(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        key = CacheKey("stablecoins_all", start.strftime("%Y%m%d"), end.strftime("%Y%m%d"))
        cached = self._read_cache(key)
        if cached is not None:
            return cached

        payload = self._get_json(DEFILLAMA_STABLECOINS_URL)
        frame = pd.DataFrame(payload)
        frame["date"] = pd.to_datetime(frame["date"].astype("int64"), unit="s", utc=True)
        frame["stablecoin_mcap"] = frame["totalCirculatingUSD"].map(
            lambda value: value.get("peggedUSD") if isinstance(value, dict) else math.nan
        )
        result = frame.loc[:, ["date", "stablecoin_mcap"]].sort_values("date").reset_index(drop=True)
        result["stablecoin_mcap"] = pd.to_numeric(result["stablecoin_mcap"], errors="coerce")
        result["stablecoin_mcap_growth"] = result["stablecoin_mcap"].pct_change()
        result = result.loc[
            (result["date"] >= start.normalize() - pd.Timedelta(days=2))
            & (result["date"] <= end.normalize())
        ].reset_index(drop=True)
        self._write_cache(key, result)
        return result

    def _download_yfinance_close(
        self, symbol: str, start_date: date, end_date: date, column_name: str
    ) -> pd.DataFrame:
        frame = yf.download(
            symbol,
            start=start_date.isoformat(),
            end=(end_date + timedelta(days=1)).isoformat(),
            auto_adjust=False,
            progress=False,
            interval="1d",
        )
        if frame.empty:
            raise RuntimeError(f"yfinance returned no data for {symbol}")
        if isinstance(frame.columns, pd.MultiIndex):
            close_series = frame["Close"].iloc[:, 0]
        else:
            close_series = frame["Close"]
        result = close_series.reset_index()
        result.columns = ["date", column_name]
        result["date"] = pd.to_datetime(result["date"], utc=True)
        result[column_name] = pd.to_numeric(result[column_name], errors="coerce")
        return result

    def _read_binance_spot_month(self, symbol: str, month_start: pd.Timestamp) -> pd.DataFrame:
        month_token = month_start.strftime("%Y-%m")
        url = (
            f"{BINANCE_DATA_ROOT}/spot/monthly/klines/{symbol}/1h/"
            f"{symbol}-1h-{month_token}.zip"
        )
        columns = [
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_volume",
            "trade_count",
            "taker_buy_base_volume",
            "taker_buy_quote_volume",
            "ignore",
        ]
        return self._read_zip_csv(url, columns=columns, header=None)

    def _read_binance_funding_month(self, symbol: str, month_start: pd.Timestamp) -> pd.DataFrame:
        month_token = month_start.strftime("%Y-%m")
        url = (
            f"{BINANCE_DATA_ROOT}/futures/um/monthly/fundingRate/{symbol}/"
            f"{symbol}-fundingRate-{month_token}.zip"
        )
        return self._read_zip_csv(url)

    def _read_binance_funding_day(self, symbol: str, day: pd.Timestamp) -> pd.DataFrame:
        day_token = day.strftime("%Y-%m-%d")
        url = (
            f"{BINANCE_DATA_ROOT}/futures/um/daily/fundingRate/{symbol}/"
            f"{symbol}-fundingRate-{day_token}.zip"
        )
        return self._read_zip_csv(url)

    def _read_binance_metrics_day(self, symbol: str, day: pd.Timestamp) -> pd.DataFrame:
        day_token = day.strftime("%Y-%m-%d")
        url = (
            f"{BINANCE_DATA_ROOT}/futures/um/daily/metrics/{symbol}/"
            f"{symbol}-metrics-{day_token}.zip"
        )
        return self._read_zip_csv(url)

    def _read_zip_csv(
        self,
        url: str,
        columns: list[str] | None = None,
        header: int | None = 0,
    ) -> pd.DataFrame:
        request = Request(url, headers={"User-Agent": "AutoQuant/0.4.0"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw_bytes = response.read()
        except HTTPError as exc:
            raise RuntimeError(f"Failed to fetch archive: {url} ({exc.code})") from exc

        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as archive:
            names = [name for name in archive.namelist() if name.endswith(".csv")]
            if not names:
                raise RuntimeError(f"Archive contained no CSV files: {url}")
            with archive.open(names[0]) as csv_file:
                return pd.read_csv(csv_file, names=columns, header=header)

    def _get_json(self, url: str, params: dict[str, object] | None = None) -> dict | list:
        final_url = url
        if params:
            final_url = f"{url}?{urlencode(params)}"
        request = Request(
            final_url,
            headers={"User-Agent": "AutoQuant/0.4.0", "Accept": "application/json"},
        )
        with urlopen(request, timeout=self.timeout) as response:
            return json.load(response)

    def _read_cache(self, key: CacheKey) -> pd.DataFrame | None:
        path = self.cache_dir / key.as_filename()
        if not path.exists():
            return None
        return pd.read_feather(path)

    def _write_cache(self, key: CacheKey, frame: pd.DataFrame) -> None:
        frame.to_feather(self.cache_dir / key.as_filename())

    @staticmethod
    def _month_starts(start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
        start_month = start.normalize().replace(day=1)
        end_month = end.normalize().replace(day=1)
        return list(pd.date_range(start=start_month, end=end_month, freq="MS", tz="UTC"))
