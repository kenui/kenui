"""Bulk downloader for Binance public dumps (data.binance.vision), spot and USD-M futures.

Everything is public market data, no API key. Files are cached as parquet in data/vision/.

Datasets used in step 2:
  spot klines            - price, volume and taker (aggressive) buy volume
  futures klines         - same for the perpetual contract
  premiumIndexKlines     - perp price minus index price (basis)
  fundingRate            - funding paid every 8h (or 4h)
  metrics                - open interest and long/short ratios every 5 minutes
"""
from __future__ import annotations

import io
import re
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

BASE = "https://data.binance.vision/data"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
CACHE = Path(__file__).resolve().parent.parent / "data" / "vision"
KCOLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
         "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"]

_session = requests.Session()
_adapter = requests.adapters.HTTPAdapter(pool_connections=64, pool_maxsize=64, max_retries=3)
_session.mount("https://", _adapter)


def s3_list(prefix: str, dirs: bool = True) -> list[str]:
    """List sub-prefixes (dirs=True) or keys under a bucket prefix."""
    out, marker = [], ""
    while True:
        r = _session.get(S3, params={"delimiter": "/", "prefix": prefix, "marker": marker}, timeout=60)
        r.raise_for_status()
        tag = "Prefix" if dirs else "Key"
        found = re.findall(rf"<{tag}>([^<]+)</{tag}>", r.text)
        found = [f for f in found if f != prefix]
        out.extend(found)
        if "<IsTruncated>true</IsTruncated>" not in r.text:
            break
        nm = re.search(r"<NextMarker>([^<]+)</NextMarker>", r.text)
        marker = nm.group(1) if nm else found[-1]
    return out


def symbols(market: str = "futures/um") -> list[str]:
    pre = f"data/{market}/monthly/klines/"
    return [p[len(pre):-1] for p in s3_list(pre)]


def _zip_csv(url: str) -> pd.DataFrame | None:
    for attempt in range(4):
        try:
            r = _session.get(url, timeout=90)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                with z.open(z.namelist()[0]) as f:
                    head = f.read(64)
                    f.seek(0)
                    has_header = not head[:1].isdigit()
                    return pd.read_csv(f, header=0 if has_header else None)
        except Exception:
            if attempt == 3:
                raise
    return None


def _months(start: date, end: date):
    cur = date(start.year, start.month, 1)
    while cur <= end:
        yield cur
        cur = date(cur.year + cur.month // 12, cur.month % 12 + 1, 1)


def _days(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def _urls(market: str, kind: str, symbol: str, interval: str | None,
          start: date, end: date, daily_only: bool) -> list[str]:
    """Monthly files for complete months, daily files for the last (partial) month."""
    iv = f"/{interval}" if interval else ""
    tag = f"-{interval}" if interval else f"-{kind}"
    urls = []
    last_month = date(end.year, end.month, 1)
    for m in _months(start, end):
        if daily_only or m == last_month:
            lo, hi = max(m, start), min(end, date(m.year + m.month // 12, m.month % 12 + 1, 1) - timedelta(days=1))
            urls += [f"{BASE}/{market}/daily/{kind}/{symbol}{iv}/{symbol}{tag}-{d:%Y-%m-%d}.zip"
                     for d in _days(lo, hi)]
        else:
            urls.append(f"{BASE}/{market}/monthly/{kind}/{symbol}{iv}/{symbol}{tag}-{m:%Y-%m}.zip")
    return urls


def _to_time(s: pd.Series) -> pd.DatetimeIndex:
    t = pd.to_numeric(s)
    unit = "us" if t.iloc[0] > 1e14 else "ms"
    return pd.to_datetime(t, unit=unit, utc=True)


def fetch(market: str, kind: str, symbol: str, start: date, end: date,
          interval: str | None = None, workers: int = 16, refresh: bool = False) -> pd.DataFrame:
    """Download one dataset for one symbol, cached on disk.

    market: 'spot' or 'futures/um'; kind: klines, premiumIndexKlines, fundingRate, metrics.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    name = f"{market.replace('/', '_')}_{kind}_{symbol}_{interval or 'na'}_{start}_{end}.parquet"
    path = CACHE / name
    if path.exists() and not refresh:
        return pd.read_parquet(path)
    daily_only = kind == "metrics"
    urls = _urls(market, kind, symbol, interval, start, end, daily_only)
    if kind == "fundingRate":  # only monthly files exist
        urls = [u for u in urls if "/monthly/" in u]
    with ThreadPoolExecutor(workers) as ex:
        frames = [f for f in ex.map(_zip_csv, urls) if f is not None and len(f)]
    if not frames:
        df = pd.DataFrame()
    elif kind in ("klines", "premiumIndexKlines"):
        frames = [f.iloc[:, :12].set_axis(KCOLS, axis=1) for f in frames]
        parts = []
        for f in frames:  # units differ between files (ms before 2025, us after, spot only)
            f = f.copy()
            f.index = _to_time(f["open_time"])
            parts.append(f)
        df = pd.concat(parts)
        df.index.name = "time"
        df = df[["open", "high", "low", "close", "volume", "quote_volume", "trades",
                 "taker_buy_base", "taker_buy_quote"]].apply(pd.to_numeric, errors="coerce")
    elif kind == "fundingRate":
        df = pd.concat(frames)
        df.index = pd.to_datetime(pd.to_numeric(df["calc_time"]), unit="ms", utc=True).dt.floor("min")
        df.index.name = "time"
        df = df[["funding_interval_hours", "last_funding_rate"]].apply(pd.to_numeric, errors="coerce")
    elif kind == "metrics":
        df = pd.concat(frames)
        df.index = pd.to_datetime(df["create_time"], utc=True).dt.floor("5min")
        df.index.name = "time"
        df = df.drop(columns=["create_time", "symbol"]).apply(pd.to_numeric, errors="coerce")
    else:
        raise ValueError(kind)
    if len(df):
        df = df[~df.index.duplicated()].sort_index()
    df.to_parquet(path)
    return df
