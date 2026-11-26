"""Download historical candles (klines) from Binance public data.

Two sources:
  * data.binance.vision  - monthly/daily zip dumps, fast for long history
  * data-api.binance.vision / api.binance.com REST - recent candles

Only public market data is used here; no API key is needed.
"""
from __future__ import annotations

import io
import time
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

VISION = "https://data.binance.vision/data/spot"
REST_HOSTS = ["https://data-api.binance.vision", "https://api.binance.com"]
COLUMNS = [
    "open_time", "open", "high", "low", "close", "volume", "close_time",
    "quote_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore",
]
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _rest_get(path: str, params: dict | None = None, timeout: int = 20):
    last = None
    for host in REST_HOSTS:
        try:
            r = requests.get(host + path, params=params, timeout=timeout)
            if r.status_code == 200:
                return r.json()
            last = f"{host}: HTTP {r.status_code} {r.text[:200]}"
        except requests.RequestException as e:  # try next host
            last = f"{host}: {e}"
    raise RuntimeError(f"Binance REST failed: {last}")


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.iloc[:, :12].copy()
    df.columns = COLUMNS
    t = pd.to_numeric(df["open_time"])
    # Binance switched spot dumps to microseconds in 2025.
    unit = "us" if t.iloc[0] > 1e14 else "ms"
    df.index = pd.to_datetime(t, unit=unit, utc=True)
    df.index.name = "time"
    for c in ["open", "high", "low", "close", "volume", "quote_volume",
              "taker_buy_base", "taker_buy_quote"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["trades"] = pd.to_numeric(df["trades"], errors="coerce").astype("Int64")
    return df[["open", "high", "low", "close", "volume", "quote_volume",
               "trades", "taker_buy_base", "taker_buy_quote"]]


def _fetch_zip(url: str) -> pd.DataFrame | None:
    r = requests.get(url, timeout=60)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        with z.open(z.namelist()[0]) as f:
            raw = pd.read_csv(f, header=None)
    if not str(raw.iloc[0, 0]).isdigit():  # some files carry a header row
        raw = raw.iloc[1:]
    return _normalize(raw)


def download_vision(symbol: str, interval: str, start: date, end: date) -> pd.DataFrame:
    """Monthly dumps for whole months, daily dumps for the current month."""
    frames = []
    cur = date(start.year, start.month, 1)
    today = datetime.now(timezone.utc).date()
    while cur <= end:
        nxt = date(cur.year + cur.month // 12, cur.month % 12 + 1, 1)
        if nxt <= today.replace(day=1):
            url = f"{VISION}/monthly/klines/{symbol}/{interval}/{symbol}-{interval}-{cur:%Y-%m}.zip"
            df = _fetch_zip(url)
            if df is not None:
                frames.append(df)
        else:
            d = cur
            while d < min(today, end + timedelta(days=1)):
                url = f"{VISION}/daily/klines/{symbol}/{interval}/{symbol}-{interval}-{d:%Y-%m-%d}.zip"
                df = _fetch_zip(url)
                if df is not None:
                    frames.append(df)
                d += timedelta(days=1)
        cur = nxt
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames).sort_index()
    out = out[~out.index.duplicated()]
    return out.loc[str(start):str(end)]


def download_rest(symbol: str, interval: str, start_ms: int, end_ms: int | None = None) -> pd.DataFrame:
    rows, cursor = [], start_ms
    end_ms = end_ms or int(time.time() * 1000)
    while cursor < end_ms:
        batch = _rest_get("/api/v3/klines", {
            "symbol": symbol, "interval": interval, "startTime": cursor,
            "endTime": end_ms, "limit": 1000})
        if not batch:
            break
        rows.extend(batch)
        cursor = batch[-1][0] + 1
        if len(batch) < 1000:
            break
        time.sleep(0.2)
    if not rows:
        return pd.DataFrame()
    return _normalize(pd.DataFrame(rows))


def load(symbol: str, interval: str = "5m", days: int = 180, refresh: bool = False) -> pd.DataFrame:
    """Load candles from the local cache, downloading what is missing."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{symbol}_{interval}.csv.gz"
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    if path.exists() and not refresh:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        if len(df) and df.index[0].date() <= start:
            return df.loc[str(start):]
    df = download_vision(symbol, interval, start, end)
    if df.empty:
        df = download_rest(symbol, interval,
                           int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp() * 1000))
    df.to_csv(path, compression="gzip")
    return df


def top_volatile(n: int = 15, quote: str = "USDT", min_quote_volume: float = 20e6) -> pd.DataFrame:
    """Rank liquid spot pairs by 24h range (high-low)/low."""
    tick = pd.DataFrame(_rest_get("/api/v3/ticker/24hr"))
    tick = tick[tick["symbol"].str.endswith(quote)]
    # skip stablecoin and leveraged-token pairs
    bad = ("USDCUSDT", "FDUSDUSDT", "TUSDUSDT", "USDPUSDT", "DAIUSDT", "EURUSDT",
           "USD1USDT", "RLUSDUSDT", "UUSDT", "PAXGUSDT", "XAUTUSDT", "WBTCUSDT")
    tick = tick[~tick["symbol"].isin(bad) & ~tick["symbol"].str.contains("UP|DOWN|BULL|BEAR")]
    for c in ["highPrice", "lowPrice", "quoteVolume", "priceChangePercent", "count"]:
        tick[c] = pd.to_numeric(tick[c])
    tick = tick[(tick["quoteVolume"] >= min_quote_volume) & (tick["lowPrice"] > 0)]
    tick["range_pct"] = (tick["highPrice"] - tick["lowPrice"]) / tick["lowPrice"] * 100
    cols = ["symbol", "range_pct", "priceChangePercent", "quoteVolume", "count"]
    return tick.sort_values("range_pct", ascending=False)[cols].head(n).reset_index(drop=True)


def historical_volatility(symbols: list[str], interval: str = "1h", days: int = 90) -> pd.DataFrame:
    """Rank symbols by realized volatility of returns over a longer window."""
    out = []
    for s in symbols:
        df = load(s, interval, days)
        if df.empty:
            continue
        r = df["close"].pct_change().dropna()
        bars_per_day = {"1m": 1440, "5m": 288, "15m": 96, "1h": 24}.get(interval, 24)
        out.append({
            "symbol": s,
            "daily_vol_pct": r.std() * (bars_per_day ** 0.5) * 100,
            "avg_daily_range_pct": (lambda d: ((d["high"] - d["low"]) / d["low"]).mean() * 100)(
                df.resample("1D").agg({"high": "max", "low": "min"}).dropna()),
            "avg_quote_vol_24h": df["quote_volume"].resample("1D").sum().mean(),
        })
    return pd.DataFrame(out).sort_values("daily_vol_pct", ascending=False).reset_index(drop=True)
