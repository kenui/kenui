"""Run an engine on a slower timeframe while orders are still simulated on the fast bars.

A slow bar stamped T closes at T + tf. Its signal is placed on the LAST fast bar inside it,
so the backtest fills it at the next fast open, which is exactly T + tf.
"""
from __future__ import annotations

from typing import Callable

import pandas as pd

from prop.strategies.indicators import empty_signals
from prop.strategies.regime_detector import resample

SLOWER = {"15min": "1h", "1h": "4h", "4h": "1D"}  # regime timeframe for each trading timeframe


def signals_on(df: pd.DataFrame, engine: Callable[..., pd.DataFrame], tf: str = "15min", **params) -> pd.DataFrame:
    """Signals of `engine` computed on `tf` bars, aligned to the index of the fast bars `df`."""
    step = df.index[1] - df.index[0]
    if pd.Timedelta(tf) <= step:
        return engine(df, **params)
    slow = resample(df, tf)
    sg = engine(slow, **params)
    sg = sg[sg["side"] != 0].copy()
    sg.index = sg.index + pd.Timedelta(tf) - step
    sg["max_bars"] = sg["max_bars"] * int(pd.Timedelta(tf) / step)
    out = empty_signals(df.index)
    sg = sg[sg.index.isin(df.index)]
    for col in sg.columns:
        if col not in out.columns:
            out[col] = 0
        out.loc[sg.index, col] = sg[col]
    return out
