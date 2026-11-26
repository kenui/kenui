"""Hourly and 15-minute bars of the portfolio on aligned UTC indexes.

Each market keeps its own bars (no forward-filled prices are traded); the aligned return
matrix used for correlations fills a closed market with a zero return, which uses no future data.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from prop.config.quant import Q
from prop.data.data_loader import load
from prop.strategies.regime_detector import resample


def validate(df: pd.DataFrame, name: str) -> pd.DataFrame:
    """Integrity checks and outlier treatment: drop broken bars, clip impossible wicks."""
    df = df[~df.index.duplicated()].sort_index()
    ok = (df[["open", "high", "low", "close"]] > 0).all(axis=1) & (df["high"] >= df["low"])
    df = df[ok].copy()
    body_hi, body_lo = df[["open", "close"]].max(axis=1), df[["open", "close"]].min(axis=1)
    med = (df["high"] - df["low"]).rolling(96, min_periods=20).median()
    cap = 15 * med.fillna((df["high"] - df["low"]).median())
    df["high"] = np.minimum(df["high"], body_hi + cap)   # a wick 15x the usual range is a bad print
    df["low"] = np.maximum(df["low"], body_lo - cap)
    if len(df) < 1000:
        raise ValueError(f"{name}: not enough clean bars")
    return df


def load_portfolio(assets: tuple[str, ...] = Q.assets) -> tuple[dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    """(fast 15m bars, signal-timeframe bars) per asset."""
    fast = {a: validate(load(a), a) for a in assets}
    slow = {a: resample(fast[a], Q.timeframe) for a in assets}
    return fast, slow


def aligned_returns(slow: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Hourly log returns of every asset on the union index; closed market = 0."""
    r = pd.concat({a: np.log(df["close"]).diff() for a, df in slow.items()}, axis=1, sort=True)
    return r.fillna(0.0)
