"""V5 gate for the primary signals: each engine only fires where the physics of the series
supports it. Trend/breakout needs persistence (Hurst > 0.54) and a dominant trend regime;
mean reversion needs anti-persistence (Hurst < 0.46) and an OU half-life of 4 to 24 bars."""
from __future__ import annotations

import numpy as np
import pandas as pd

from prop.strategies.primary_signals import BREAKOUT, REVERSION


def gate(events: pd.DataFrame, hurst_trend: float = 0.54, hurst_revert: float = 0.46,
         tau_window: tuple[float, float] = (4.0, 24.0)) -> np.ndarray:
    """Boolean mask over the event table (needs kind, hurst, ou_tau and the HMM probabilities)."""
    trend_dominant = (events["p_trend"] >= events[["p_compress", "p_shock"]].max(axis=1)).to_numpy()
    bo = (events["kind"] == BREAKOUT).to_numpy() & (events["hurst"] > hurst_trend).to_numpy() & trend_dominant
    tau = events["ou_tau"].to_numpy()
    mr = (events["kind"] == REVERSION).to_numpy() & (events["hurst"] < hurst_revert).to_numpy() \
        & (tau >= tau_window[0]) & (tau <= tau_window[1])
    return bo | mr
