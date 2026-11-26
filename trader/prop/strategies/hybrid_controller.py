"""The brain: lets Engine 1 trade only in TREND, Engine 2 only in RANGE, nothing when undefined.

Each engine may run on its own timeframe; its regime is read one timeframe above it.
"""
from __future__ import annotations

import pandas as pd

from prop.strategies import engine_breakout, engine_mean_reversion, regime_detector
from prop.strategies.timeframe import SLOWER, signals_on

ALL_DAY = ((0.0, 24.0),)


def engine_signals(df: pd.DataFrame, kind: str, spec: dict) -> pd.DataFrame:
    """Signals of one engine. `spec` = {"tf": "1h", "params": {...}}."""
    mod = engine_breakout if kind == "breakout" else engine_mean_reversion
    tf, params = spec.get("tf", "15min"), dict(spec.get("params", {}))
    if tf == "4h":  # a 4h bar spans several sessions, so the session filter is dropped
        params["sessions"] = ALL_DAY
    return signals_on(df, mod.signals, tf, **params)


def signals(df: pd.DataFrame, breakout: dict, reversion: dict, regime: dict | None = None) -> pd.DataFrame:
    regime = regime or {}
    b = engine_signals(df, "breakout", breakout)
    m = engine_signals(df, "reversion", reversion)
    reg_b = regime_detector.detect(df, rule=SLOWER[breakout.get("tf", "15min")], **regime).to_numpy()
    reg_m = regime_detector.detect(df, rule=SLOWER[reversion.get("tf", "15min")], **regime).to_numpy()
    use_b = (reg_b == regime_detector.TREND) & (b["side"].to_numpy() != 0)
    use_m = (reg_m == regime_detector.RANGE) & (m["side"].to_numpy() != 0) & ~use_b
    out = b.copy()
    out.loc[~use_b, "side"] = 0
    out.loc[use_m, :] = m.loc[use_m, :]
    return out


REGIME_GRID = [dict(adx_trend=t, adx_range=r) for t in (20.0, 25.0, 30.0) for r in (15.0, 20.0, 25.0) if r <= t]
