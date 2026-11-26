"""Live public market data from Binance REST (no API key), in the same shape as the archive files.

Hosts: spot from api.binance.com (fallback data-api.binance.vision), futures from fapi.binance.com.
Binance blocks US IP addresses (HTTP 451): run this from Brazil or a non-US server.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd
import requests

SPOT = ["https://api.binance.com", "https://data-api.binance.vision"]
FUT = ["https://fapi.binance.com"]
_s = requests.Session()
KC = ["open_time", "open", "high", "low", "close", "volume", "close_time",
      "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"]
KEEP = ["open", "high", "low", "close", "volume", "quote_volume", "trades", "taker_buy_base", "taker_buy_quote"]


def get(hosts, path, params=None, tries=3):
    last = None
    for attempt in range(tries):
        for h in hosts:
            try:
                r = _s.get(h + path, params=params, timeout=15)
                if r.status_code == 200:
                    return r.json()
                last = f"{h}{path}: HTTP {r.status_code} {r.text[:120]}"
                if r.status_code in (418, 429):
                    time.sleep(10 * (attempt + 1))
            except requests.RequestException as e:
                last = f"{h}{path}: {e}"
        time.sleep(1 + attempt)
    raise RuntimeError(last)


def _kl(rows) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=KEEP)
    df = pd.DataFrame(rows).iloc[:, :12].set_axis(KC, axis=1)
    df.index = pd.to_datetime(pd.to_numeric(df["open_time"]), unit="ms", utc=True)
    df.index.name = "time"
    return df[KEEP].apply(pd.to_numeric, errors="coerce")


def _closed(df: pd.DataFrame) -> pd.DataFrame:
    """Drop the candle that is still forming."""
    now = pd.Timestamp.now(tz="UTC")
    return df[df.index + pd.Timedelta(minutes=5) <= now]


def spot_klines(sym, limit=100, start=None):
    p = {"symbol": sym, "interval": "5m", "limit": limit}
    if start is not None:
        p["startTime"] = int(start.timestamp() * 1000)
    return _closed(_kl(get(SPOT, "/api/v3/klines", p)))


def fut_klines(sym, limit=100, start=None, kind="klines"):
    p = {"symbol": sym, "interval": "5m", "limit": limit}
    if start is not None:
        p["startTime"] = int(start.timestamp() * 1000)
    return _closed(_kl(get(FUT, f"/fapi/v1/{kind}", p)))


def funding(sym, limit=200):
    rows = get(FUT, "/fapi/v1/fundingRate", {"symbol": sym, "limit": limit})
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["funding_interval_hours", "last_funding_rate"])
    df.index = pd.to_datetime(pd.to_numeric(df["fundingTime"]), unit="ms", utc=True).floor("min")
    df.index.name = "time"
    return pd.DataFrame({"funding_interval_hours": np.nan,
                         "last_funding_rate": pd.to_numeric(df["fundingRate"])}, index=df.index)


def metrics(sym, limit=30, start=None):
    """Open interest + long/short ratios, 5-minute snapshots, archive column names."""
    p = {"symbol": sym, "period": "5m", "limit": limit}
    if start is not None:
        p["startTime"] = int(start.timestamp() * 1000)
    out = {}
    spec = [("openInterestHist", {"sumOpenInterest": "sum_open_interest", "sumOpenInterestValue": "sum_open_interest_value"}),
            ("topLongShortAccountRatio", {"longShortRatio": "count_toptrader_long_short_ratio"}),
            ("topLongShortPositionRatio", {"longShortRatio": "sum_toptrader_long_short_ratio"}),
            ("globalLongShortAccountRatio", {"longShortRatio": "count_long_short_ratio"})]
    for ep, cols in spec:
        rows = get(FUT, f"/futures/data/{ep}", p)
        df = pd.DataFrame(rows)
        if df.empty:
            continue
        df.index = pd.to_datetime(pd.to_numeric(df["timestamp"]), unit="ms", utc=True).floor("5min")
        for a, b in cols.items():
            out[b] = pd.to_numeric(df[a])
    m = pd.DataFrame(out)
    m.index.name = "time"
    return m[~m.index.duplicated()].sort_index()


def book(symbols: list[str]) -> pd.DataFrame:
    """Best bid/ask right now for spot symbols."""
    rows = get(SPOT, "/api/v3/ticker/bookTicker")
    df = pd.DataFrame(rows).set_index("symbol")
    return df.loc[[s for s in symbols if s in df.index], ["bidPrice", "askPrice"]].astype(float)
