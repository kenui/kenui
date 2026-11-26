"""Other strategy families on the same markets, each with a small declared grid:
cross-sectional momentum/reversal between cryptos, hour-of-week seasonality, and reversal
after extreme hourly moves. Returns are net of CFD-style costs; position sizes are
volatility-scaled like in `trend`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from prop.research.trend import ALT_COST, COSTS, SPLIT, daily, vol


def cost_of(a: str) -> tuple[float, float]:
    return COSTS.get(a, ALT_COST)


def cross_section(data: dict[str, pd.DataFrame], lookback: int, hold: int, reversal: bool, top: int = 4) -> pd.Series:
    """Market-neutral crypto basket: long the `top` strongest and short the `top` weakest over
    `lookback` days (or the opposite when `reversal`), rebalanced every `hold` days."""
    cr = [a for a in data if a not in ("PAXG", "EUR")]
    d = {a: daily(data[a]) for a in cr}
    close = pd.DataFrame({a: x["close"] for a, x in d.items()})
    opn = pd.DataFrame({a: x["open"] for a, x in d.items()})
    v = pd.DataFrame({a: vol(x) for a, x in d.items()})
    score = close.pct_change(lookback) / (v * np.sqrt(lookback))
    rank = score.rank(axis=1, ascending=False)
    n = score.notna().sum(axis=1)
    w = pd.DataFrame(0.0, index=close.index, columns=cr)
    w[rank.le(top)] = 1.0
    w[rank.gt(n.to_numpy()[:, None] - top)] = -1.0
    w[score.isna()] = 0.0
    w[n < 2 * top + 2] = 0.0
    if reversal:
        w = -w
    w = (w * (0.01 / v).clip(upper=3.0) / top)
    keep = np.arange(len(w)) % hold != 0
    w[keep] = np.nan
    w = w.ffill().shift(1).fillna(0.0)
    oo = opn.shift(-1) / opn - 1.0
    cost = pd.Series({a: cost_of(a)[0] for a in cr})
    swap = pd.Series({a: cost_of(a)[1] for a in cr})
    net = (w * oo).sum(axis=1) - ((w - w.shift(1).fillna(0.0)).abs() * cost).sum(axis=1) - (w.abs() * swap).sum(axis=1)
    return net.iloc[:-1]


def hour_of_week(data: dict[str, pd.DataFrame], asset: str, top: int) -> pd.Series:
    """Trade the `top` best and `top` worst hours of the week, chosen before SPLIT, one hour each."""
    h = data[asset]
    r = h["close"] / h["open"] - 1.0
    key = h.index.dayofweek * 24 + h.index.hour
    mean_is = r[h.index < SPLIT].groupby(key[h.index < SPLIT]).mean()
    best, worst = mean_is.nlargest(top).index, mean_is.nsmallest(top).index
    side = pd.Series(0.0, index=h.index)
    side[np.isin(key, best)] = 1.0
    side[np.isin(key, worst)] = -1.0
    hv = np.log(h["close"]).diff().ewm(span=24 * 30, min_periods=24 * 10).std().shift(1)
    w = side * (0.01 / (hv * np.sqrt(24))).clip(upper=3.0)
    net = w * r - w.abs() * 2 * cost_of(asset)[0]
    return net.resample("1D").sum()


def extreme_reversal(data: dict[str, pd.DataFrame], asset: str, z: float, hold: int) -> pd.Series:
    """Fade an hourly move larger than `z` standard deviations; hold `hold` hours."""
    h = data[asset]
    lr = np.log(h["close"]).diff()
    sd = lr.ewm(span=24 * 30, min_periods=24 * 10).std().shift(1)
    sig = pd.Series(np.where(lr > z * sd, -1.0, np.where(lr < -z * sd, 1.0, 0.0)), index=h.index)
    fwd = h["close"].shift(-hold) / h["close"] - 1.0             # enter at this close (next open)
    w = sig * (0.01 / (sd * np.sqrt(24))).clip(upper=3.0)
    net = (w * fwd - w.abs() * 2 * cost_of(asset)[0]) / hold     # overlapping holds, averaged
    return net.resample("1D").sum()
