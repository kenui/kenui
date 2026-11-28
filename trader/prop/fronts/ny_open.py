"""Front 3: breakout of the New York opening range.

Instruments: US500, US30, USTEC and XAUUSD. Broker time is New York + 7 hours, so the cash open
(09:30) falls inside the 16:00 bar. Hourly bars cannot cut exactly 90 minutes: the opening range
is the high and low of the 16:00 and 17:00 bars (09:00 to 11:00 New York) or of the 16:00 bar
alone. From the next bar until 21:00 a stop order sits on each side of the range; the first one
touched is the trade, the other side of the range is the stop-loss, and whatever is open is
closed at the open of the 22:00 bar, before the rollover. If one bar touches both sides the trade
counts as stopped. With `hurst` the front only trades when the 250-day Hurst exponent of the
instrument, known the day before, is above 0.5.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from prop.fronts.common import bar_cost, daily_vol
from prop.research import mt5_study as S
from prop.research.stage2 import hurst

INSTRUMENTS = ["US500", "US30", "USTEC", "XAUUSD"]
OPEN_HOUR, EXIT_HOUR = 16, 22


def one(m: S.Market, sym: str, range_bars: int, use_hurst: bool) -> tuple[pd.Series, list[float]]:
    h = m.bars(sym, "H1")
    cost, vol = bar_cost(m, sym, h), daily_vol(h)
    hi, lo, op, hour = h["high"].to_numpy(), h["low"].to_numpy(), h["open"].to_numpy(), h.index.hour.to_numpy()
    day = h.index.normalize()
    ok = None
    if use_hurst:
        daily = np.log(h["close"].groupby(day).last())
        ok = (hurst(daily) > 0.5).shift(1).fillna(False)       # yesterday's reading
    out, trades = {}, []
    start = np.flatnonzero(hour == OPEN_HOUR)
    for s in start:
        e = s + range_bars
        if e + 1 >= len(h) or day[e] != day[s] or hour[e] != OPEN_HOUR + range_bars or not np.isfinite(vol[s]) or vol[s] <= 0:
            continue
        if ok is not None and not bool(ok.get(day[s], False)):
            continue
        top, bottom = hi[s:e].max(), lo[s:e].min()
        if top <= bottom:
            continue
        units = min(0.01 / vol[s], 10.0)
        res, k, side = 0.0, e, 0
        while k < len(h) and day[k] == day[s] and hour[k] < EXIT_HOUR:
            if side == 0:
                up, down = hi[k] >= top, lo[k] <= bottom
                if up and down:                                # both sides in one bar: counted as entry and stop
                    res = -(top - bottom) / top - 2 * cost[k]
                    side = 9
                    break
                if up or down:
                    side = 1 if up else -1
                    level = top if up else bottom
                    entry = max(level, op[k]) if up else min(level, op[k])     # a gap fills at the open
                    res -= cost[k]
                    stop = bottom if up else top
                    # the same bar can still come back to the stop only on a later bar (unknown order inside the bar)
            else:
                hit = lo[k] <= stop if side == 1 else hi[k] >= stop
                if hit:
                    fill = min(stop, op[k]) if side == 1 else max(stop, op[k])
                    res += side * (fill / entry - 1.0) - cost[k]
                    side = 9
                    break
            k += 1
        if side in (1, -1):                                    # still open: closed at the open of the exit bar
            x = min(k, len(h) - 1)
            res += side * (op[x] / entry - 1.0) - cost[x]
        if side != 0:
            out[day[s]] = out.get(day[s], 0.0) + units * res
            trades.append(units * res)
    return pd.Series(out, dtype=float).sort_index(), trades


def variants(m: S.Market) -> dict[str, tuple[pd.Series, list[float]]]:
    res = {}
    for range_bars in (1, 2):
        for use_hurst in (False, True):
            days, trades = {}, []
            for sym in INSTRUMENTS:
                if m.has(sym, "H1"):
                    d, tr = one(m, sym, range_bars, use_hurst)
                    days[sym] = d
                    trades += tr
            name = f"abertura NY|faixa de {range_bars}h|{'com Hurst' if use_hurst else 'sem filtro'}"
            res[name] = (pd.DataFrame(days).fillna(0.0).mean(axis=1), trades)
    return res
