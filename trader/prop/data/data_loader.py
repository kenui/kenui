"""Download and cache OHLCV history for the three markets.

The cloud environment only reaches Binance public data, so each market uses a Binance proxy:
EUR/USD -> EURUSDT spot, XAU/USD -> PAXGUSDT spot (tokenised gold), BTC/USD -> BTCUSDT spot.
Forex and gold bars between Friday 22:00 UTC and Sunday 22:00 UTC are dropped, because the
prop-firm market is closed then (the proxy trades 24/7).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from kenui_trader.data import DATA_DIR, VISION, _fetch_zip
from prop.config.settings import INSTRUMENTS, SETTINGS, Instrument

FUTURES = "https://data.binance.vision/data/futures/um"


def _month_url(inst: Instrument, interval: str, month: date) -> str:
    base = VISION if inst.market == "spot" else FUTURES
    return f"{base}/monthly/klines/{inst.source}/{interval}/{inst.source}-{interval}-{month:%Y-%m}.zip"


def _day_url(inst: Instrument, interval: str, day: date) -> str:
    base = VISION if inst.market == "spot" else FUTURES
    return f"{base}/daily/klines/{inst.source}/{interval}/{inst.source}-{interval}-{day:%Y-%m-%d}.zip"


def download(inst: Instrument, interval: str, start: date, end: date) -> pd.DataFrame:
    """Monthly archives, then daily archives for the months Binance has not packed yet."""
    frames: list[pd.DataFrame] = []
    cur = date(start.year, start.month, 1)
    while cur <= end:
        nxt = date(cur.year + cur.month // 12, cur.month % 12 + 1, 1)
        df = _fetch_zip(_month_url(inst, interval, cur))
        if df is not None:
            frames.append(df)
        else:
            for d in pd.date_range(cur, min(end, nxt - pd.Timedelta(days=1))):
                day = _fetch_zip(_day_url(inst, interval, d.date()))
                if day is not None:
                    frames.append(day)
        cur = nxt
    if not frames:
        raise RuntimeError(f"no data for {inst.source}")
    out = pd.concat(frames).sort_index()
    out = out[~out.index.duplicated()]
    return out.loc[str(start):str(end), ["open", "high", "low", "close", "volume"]].astype(float)


def drop_weekend(df: pd.DataFrame) -> pd.DataFrame:
    """Remove Fri 22:00 UTC -> Sun 22:00 UTC, when forex and gold are closed."""
    wd, hr = df.index.weekday, df.index.hour
    closed = ((wd == 4) & (hr >= 22)) | (wd == 5) | ((wd == 6) & (hr < 22))
    return df[~closed]


def load(name: str, interval: str | None = None, start: date | None = None, end: date | None = None,
         refresh: bool = False, cache_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Candles for one instrument, UTC index, from the local cache when present."""
    inst = INSTRUMENTS[name]
    interval = interval or SETTINGS.timeframe
    start, end = start or SETTINGS.start, end or SETTINGS.end
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"prop_{inst.source}_{inst.market}_{interval}_{start}_{end}.parquet"
    if path.exists() and not refresh:
        df = pd.read_parquet(path)
    else:
        df = download(inst, interval, start, end)
        df.to_parquet(path)
    df = df[df["volume"] > 0]
    return drop_weekend(df) if inst.closes_weekend else df


def load_all(names: list[str] | None = None, **kw) -> dict[str, pd.DataFrame]:
    return {n: load(n, **kw) for n in (names or list(INSTRUMENTS))}
