"""Engine 2: mean reversion.

Fades a stretched price (outside the Bollinger band with an extreme RSI) during the quiet
Asian hours, aiming for the middle band. Long and short.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from prop.strategies.indicators import atr, bollinger, empty_signals, in_hours, rsi

ASIA = ((22.5, 6.0),)  # UTC, after the daily rollover spread spike


def signals(df: pd.DataFrame, bb_n: int = 20, bb_k: float = 2.0, rsi_n: int = 14, rsi_low: float = 30.0,
            atr_k: float = 2.0, min_tp_atr: float = 0.5, max_bars: int = 16,
            sessions: tuple[tuple[float, float], ...] = ASIA) -> pd.DataFrame:
    """Buy below the lower band with RSI < rsi_low, sell above the upper band with RSI > 100 - rsi_low.

    target = distance back to the middle band (skipped when smaller than min_tp_atr x ATR),
    stop = atr_k x ATR(14), time stop after `max_bars` bars.
    """
    c = df["close"]
    mid, up, lo = bollinger(c, bb_n, bb_k)
    r = rsi(c, rsi_n)
    a = atr(df, 14)
    sess = in_hours(df.index, sessions)
    long_ = ((c < lo) & (r < rsi_low)).to_numpy() & sess
    short = ((c > up) & (r > 100 - rsi_low)).to_numpy() & sess
    tp = (mid - c).abs()
    worth = (tp >= min_tp_atr * a).to_numpy()

    out = empty_signals(df.index)
    out["side"] = np.where(long_ & worth, 1, np.where(short & worth, -1, 0)).astype(np.int8)
    out["stop_dist"] = atr_k * a
    out["tp_dist"] = tp
    out["max_bars"] = max_bars
    out["engine"] = "reversion"
    return out


GRID = [dict(bb_n=n, bb_k=k, rsi_low=r, atr_k=s, max_bars=m)
        for n in (20, 40) for k in (2.0, 2.5) for r in (25.0, 35.0) for s in (1.5, 3.0) for m in (8, 24)]
