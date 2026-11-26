"""Indicators shared by the engines. All use only past and current bars."""
from __future__ import annotations

import numpy as np
import pandas as pd

from kenui_trader.strategies import atr, ema, rsi  # noqa: F401  (re-exported)


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    """(middle, upper, lower) bands."""
    mid = close.rolling(n).mean()
    sd = close.rolling(n).std()
    return mid, mid + k * sd, mid - k * sd


def bb_width(close: pd.Series, n: int = 20) -> pd.Series:
    """Band width relative to price: small = compressed market."""
    return 4 * close.rolling(n).std() / close.rolling(n).mean()


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Wilder's ADX: strength of the trend, whatever its direction."""
    up, dn = df["high"].diff(), -df["low"].diff()
    plus = pd.Series(np.where((up > dn) & (up > 0), up, 0.0), index=df.index)
    minus = pd.Series(np.where((dn > up) & (dn > 0), dn, 0.0), index=df.index)
    tr = atr(df, n)
    pdi = 100 * plus.ewm(alpha=1 / n, adjust=False).mean() / tr
    mdi = 100 * minus.ewm(alpha=1 / n, adjust=False).mean() / tr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False).mean()


def in_hours(index: pd.DatetimeIndex, windows: tuple[tuple[float, float], ...]) -> np.ndarray:
    """True where the bar's UTC hour falls in any [start, end) window; windows may wrap midnight."""
    h = index.hour + index.minute / 60
    ok = np.zeros(len(index), bool)
    for a, b in windows:
        ok |= ((h >= a) & (h < b)) if a < b else ((h >= a) | (h < b))
    return ok


def empty_signals(index: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame({"side": np.zeros(len(index), np.int8), "stop_dist": np.nan, "tp_dist": np.nan,
                         "max_bars": 0, "engine": ""}, index=index)
