"""Stationary features (V2). No raw price ever reaches the models; every value at bar t uses
bars up to and including t."""
from __future__ import annotations

import numpy as np
import pandas as pd

from prop.strategies.indicators import atr, bb_width, rsi

RET_WINDOWS = (1, 3, 5, 12, 24)


def yang_zhang(df: pd.DataFrame, n: int = 24) -> pd.Series:
    """Yang-Zhang realised volatility per bar (overnight + open-to-close + Rogers-Satchell)."""
    lo, lh, ll, lc = (np.log(df[k]) for k in ("open", "high", "low", "close"))
    over = lo - lc.shift()
    oc = lc - lo
    rs = (lh - lc) * (lh - lo) + (ll - lc) * (ll - lo)
    k = 0.34 / (1.34 + (n + 1) / (n - 1))
    var = over.rolling(n).var() + k * oc.rolling(n).var() + (1 - k) * rs.rolling(n).mean()
    return np.sqrt(var.clip(lower=0))


def base_features(df: pd.DataFrame) -> pd.DataFrame:
    c, lc = df["close"], np.log(df["close"])
    f = pd.DataFrame(index=df.index)
    for w in RET_WINDOWS:
        f[f"ret_{w}"] = lc.diff(w)
    f["vol_yz"] = yang_zhang(df, 24)
    f["vol_ratio"] = f["vol_yz"] / yang_zhang(df, 120)
    f["atr_pct"] = atr(df, 14) / c
    for n in (20, 50):
        f[f"z_{n}"] = (c - c.rolling(n).mean()) / c.rolling(n).std()
    f["bb_width"] = bb_width(c, 20)
    f["bb_width_rel"] = f["bb_width"] / f["bb_width"].rolling(240).median()
    f["rel_volume"] = df["volume"] / df["volume"].rolling(24).mean()
    f["rsi"] = (rsi(c, 14) - 50) / 50
    hour = df.index.hour + df.index.minute / 60
    f["hour_sin"], f["hour_cos"] = np.sin(2 * np.pi * hour / 24), np.cos(2 * np.pi * hour / 24)
    return f.replace([np.inf, -np.inf], np.nan)
