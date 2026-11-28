"""Pieces shared by the intraday fronts: per-bar cost and daily volatility, all known before the bar."""
from __future__ import annotations

import numpy as np
import pandas as pd

from prop.research import mt5_study as S

SLIP = 0.25          # slippage per side, as a share of the spread


def bar_cost(m: S.Market, sym: str, h: pd.DataFrame) -> np.ndarray:
    """Cost of one side at each hourly bar: half of that bar's spread (never below the symbol's running
    median, because the file keeps one spread per bar), slippage and commission. Fraction of notional."""
    spec = m.spec.get(sym, {})
    point = float(spec.get("point") or 0.0)
    floor = {"fx": 0.00004, "metal": 0.00010, "index": 0.00010}[m.kind(sym)]
    if not point:
        return np.full(len(h), floor * (0.5 + SLIP) + S.COMMISSION)
    raw = h["spread"].astype(float)
    med = raw.rolling(2000, min_periods=100).median().shift(1).bfill()
    spread = np.maximum(np.maximum(raw, med) * point / h["open"], floor)
    return (spread * (0.5 + SLIP) + S.COMMISSION).to_numpy()


def daily_vol(h: pd.DataFrame) -> np.ndarray:
    """Volatility of one day, from past hourly returns only."""
    r = np.log(h["close"]).diff()
    return (r.ewm(span=24 * 30, min_periods=24 * 10).std().shift(1) * np.sqrt(24)).to_numpy()
