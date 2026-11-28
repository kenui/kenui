"""Front 2: calm mean reversion in the Asian session.

Instruments: EURGBP, USDCAD and AUDNZD (built from AUDUSD and NZDUSD, so it pays two spreads).
At each hourly close between 01:00 and 06:00 broker time the price is compared with its own
moving level (exponential average of `span` hours, which is the steady-state Kalman filter of a
local-level model). z = (price - level) / residual deviation. Enter against the deviation when
|z| > entry; leave when z returns to zero, when |z| > entry + 2.5 (stop) or, in any case, at the
open of the 09:00 bar, one hour before London opens (10:00 broker time). Nothing is held across
midnight, so there is no swap and no rollover window.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from prop.fronts.common import bar_cost, daily_vol
from prop.research import mt5_study as S

INSTRUMENTS = [("EURGBP",), ("USDCAD",), ("AUDUSD", "NZDUSD")]
SPANS = (12, 24, 48)
ENTRIES = (1.5, 2.0)
FIRST_HOUR, LAST_ENTRY_HOUR, EXIT_HOUR = 1, 6, 9
STOP_GAP = 2.5


def one(m: S.Market, legs: tuple[str, ...], span: int, entry: float) -> tuple[pd.Series, list[float]]:
    """Daily account return (position worth 1% of a daily move) and the net result of each trade."""
    bars = [m.bars(s, "H1") for s in legs]
    idx = bars[0].index
    for b in bars[1:]:
        idx = idx.intersection(b.index)
    bars = [b.loc[idx] for b in bars]
    sign = [1.0, -1.0][:len(legs)]
    close = sum(sg * np.log(b["close"].to_numpy()) for sg, b in zip(sign, bars))
    opn = sum(sg * np.log(b["open"].to_numpy()) for sg, b in zip(sign, bars))
    cost = sum(bar_cost(m, s, b) for s, b in zip(legs, bars))
    c = pd.Series(close)
    level = c.ewm(span=span, min_periods=span).mean()
    resid = c - level
    z = (resid / resid.ewm(span=10 * span, min_periods=3 * span).std().shift(1)).to_numpy()
    vol = daily_vol(pd.DataFrame({"close": np.exp(close)}))
    hour = idx.hour.to_numpy()
    n = len(idx)
    pnl = np.zeros(n)
    trades = []
    t = 0
    while t < n - 2:
        if not (FIRST_HOUR <= hour[t] <= LAST_ENTRY_HOUR) or not np.isfinite(z[t]) or abs(z[t]) <= entry or abs(z[t]) > entry + STOP_GAP \
                or not np.isfinite(vol[t]) or vol[t] <= 0:
            t += 1
            continue
        d = -np.sign(z[t])
        units = min(0.01 / vol[t], 10.0)
        k = t + 1                                              # filled at the open of the next bar
        if hour[k] >= EXIT_HOUR or hour[k] < FIRST_HOUR:
            t += 1
            continue
        res = -cost[k]
        pnl[k] -= units * cost[k]
        while True:
            nxt = k + 1
            g = d * (opn[nxt] - opn[k])                        # open to open
            res += g
            pnl[k] += units * g
            done = (z[k] * -d <= 0) or abs(z[k]) > entry + STOP_GAP or hour[nxt] >= EXIT_HOUR or hour[nxt] < FIRST_HOUR or nxt >= n - 1
            k = nxt
            if done:
                break
        res -= cost[k]
        pnl[k] -= units * cost[k]
        trades.append(res * units)
        t = k
    return S.by_day(pd.Series(pnl, index=idx)), trades


def variants(m: S.Market) -> dict[str, tuple[pd.Series, list[float]]]:
    out = {}
    for span in SPANS:
        for entry in ENTRIES:
            days, trades = {}, []
            for legs in INSTRUMENTS:
                if all(m.has(s, "H1") for s in legs):
                    d, tr = one(m, legs, span, entry)
                    days["/".join(legs)] = d
                    trades += tr
            out[f"asia|nivel {span}h|z {entry}"] = (pd.DataFrame(days).fillna(0.0).mean(axis=1), trades)
    return out
