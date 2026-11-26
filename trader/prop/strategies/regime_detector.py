"""Market regime classifier: TREND (expansion), RANGE (compression) or UNDEFINED.

It works on a slower timeframe (1h by default) built from the trading bars, and each trading bar
only sees the last COMPLETED slow bar, so there is no look-ahead.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from prop.strategies.indicators import adx, atr, bb_width

TREND, RANGE, UNDEFINED = 1, -1, 0


def resample(df: pd.DataFrame, rule: str = "1h") -> pd.DataFrame:
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    return df.resample(rule).agg(agg).dropna(subset=["close"])


def detect(df: pd.DataFrame, rule: str = "1h", adx_n: int = 14, adx_trend: float = 25.0,
           adx_range: float = 20.0, atr_fast: int = 14, atr_slow: int = 100,
           width_n: int = 20, width_look: int = 240) -> pd.Series:
    """Regime per trading bar.

    TREND: ADX above `adx_trend` and volatility expanding (fast ATR above slow ATR).
    RANGE: ADX below `adx_range` and Bollinger width in the lower half of its recent history.
    """
    slow = resample(df, rule)
    a = adx(slow, adx_n)
    expanding = atr(slow, atr_fast) > atr(slow, atr_slow)
    w = bb_width(slow["close"], width_n)
    narrow = w < w.rolling(width_look).median()
    regime = pd.Series(UNDEFINED, index=slow.index, dtype=np.int8)
    regime[(a >= adx_trend) & expanding] = TREND
    regime[(a <= adx_range) & narrow] = RANGE
    # a slow bar stamped 10:00 closes at 11:00, so it becomes visible from 11:00 on
    step = pd.Timedelta(rule)
    visible = pd.Series(regime.to_numpy(), index=slow.index + step)
    return visible.reindex(df.index, method="ffill").fillna(UNDEFINED).astype(np.int8)
