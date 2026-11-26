"""Engine 1: volatility breakout / momentum.

Trades only when a compressed market breaks out of its recent channel with above-average volume,
inside the London or New York session. Long and short.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from prop.strategies.indicators import atr, bb_width, empty_signals, in_hours

LONDON_NY = ((7.0, 10.5), (12.5, 16.0))  # UTC


def signals(df: pd.DataFrame, channel: int = 20, squeeze_q: float = 0.30, squeeze_look: int = 480,
            squeeze_recent: int = 8, vol_mult: float = 1.2, atr_k: float = 1.5, rr: float = 2.0,
            max_bars: int = 48, sessions: tuple[tuple[float, float], ...] = LONDON_NY) -> pd.DataFrame:
    """Entry on the close that breaks the `channel`-bar high/low after a squeeze.

    stop = atr_k x ATR(14), target = rr x stop, time stop after `max_bars` bars.
    """
    c = df["close"]
    width = bb_width(c, 20)
    squeezed = width < width.rolling(squeeze_look).quantile(squeeze_q)
    was_squeezed = squeezed.shift(1).rolling(squeeze_recent).max().fillna(0).astype(bool)
    hi = df["high"].rolling(channel).max().shift(1)
    lo = df["low"].rolling(channel).min().shift(1)
    vol_ok = df["volume"] > df["volume"].rolling(channel).mean().shift(1) * vol_mult
    ok = (was_squeezed & vol_ok).to_numpy() & in_hours(df.index, sessions)
    a = atr(df, 14)

    out = empty_signals(df.index)
    side = np.where(ok & (c > hi).to_numpy(), 1, np.where(ok & (c < lo).to_numpy(), -1, 0))
    out["side"] = side.astype(np.int8)
    out["stop_dist"] = atr_k * a
    out["tp_dist"] = rr * atr_k * a
    out["max_bars"] = max_bars
    out["engine"] = "breakout"
    return out


GRID = [dict(channel=ch, squeeze_q=q, vol_mult=v, atr_k=k, rr=rr)
        for ch in (20, 48) for q in (0.2, 0.4) for v in (1.0, 1.5) for k in (1.5, 2.5) for rr in (1.5, 3.0)]
