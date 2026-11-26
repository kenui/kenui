"""Triple-barrier path simulation on the fast (15m) bars.

For every primary signal three barriers are projected from the signal bar's ATR: stop,
target and a time limit. Four exit policies are simulated on the same path so that labels,
the bandit and the Monte Carlo all read real outcomes:
  plain  target = pt_mult R, no partial                       (V2/V3)
  arm0   "scalp lock-in": target 0.9R, no partial
  arm1   "institutional hybrid": close 50% at +0.8R, stop of the rest to break-even, target 1.6R
  arm2   "trend runner": close 40% at +1.0R, trail the rest 1.5 ATR behind the best price
Results are in R (multiples of the initial stop distance), net of spread, commission, slippage
and swap. Inside one bar the stop is always checked first.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from prop.config.quant import Q
from prop.config.settings import Instrument


@dataclass(frozen=True)
class ExitPolicy:
    name: str
    target_r: float           # final target in R (inf = none)
    partial_frac: float = 0.0  # fraction closed at partial_r
    partial_r: float = 0.0
    breakeven: bool = False   # after the partial, stop of the remainder goes to entry
    trail_atr: float = 0.0    # after the partial, trail this many ATR behind the best price


def policies(pt_mult: float = Q.pt_mult) -> dict[str, ExitPolicy]:
    return {"plain": ExitPolicy("plain", pt_mult),
            "arm0": ExitPolicy("arm0", 0.9),
            "arm1": ExitPolicy("arm1", 1.6, 0.5, 0.8, breakeven=True),
            "arm2": ExitPolicy("arm2", np.inf, 0.4, 1.0, trail_atr=1.5)}


def simulate_path(o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray, start: int, side: int,
                  sl_dist: float, atr: float, pol: ExitPolicy, max_bars: int) -> tuple[float, float, int, str]:
    """(gross R, MAE in R, bars held, exit reason) for one trade entered at o[start]."""
    entry = o[start]
    stop = entry - side * sl_dist
    target = entry + side * pol.target_r * sl_dist if np.isfinite(pol.target_r) else np.inf * side
    part_px = entry + side * pol.partial_r * sl_dist
    rem, realised, mae, best = 1.0, 0.0, 0.0, entry
    took_partial = pol.partial_frac <= 0
    end = min(start + max_bars, len(o))
    for k in range(start, end):
        hi, lo = h[k], l[k]
        adverse, favour = (lo, hi) if side > 0 else (hi, lo)
        mae = min(mae, realised + rem * side * (adverse - entry) / sl_dist)
        if side * (adverse - stop) <= 0:                      # stop (gap fills at the open)
            px = o[k] if side * (o[k] - stop) <= 0 else stop
            return realised + rem * side * (px - entry) / sl_dist, mae, k - start + 1, "stop"
        if not took_partial and side * (favour - part_px) >= 0:
            realised += pol.partial_frac * pol.partial_r
            rem -= pol.partial_frac
            took_partial = True
            if pol.breakeven:
                stop = entry
            best = part_px
        if took_partial and pol.trail_atr > 0:
            if side * (favour - best) > 0:
                best = favour
            trail = best - side * pol.trail_atr * atr
            if side * (trail - stop) > 0:
                stop = trail
        if side * (favour - target) >= 0:
            return realised + rem * pol.target_r, mae, k - start + 1, "target"
    k = end - 1
    return realised + rem * side * (c[k] - entry) / sl_dist, mae, k - start + 1, "time"


def label_events(fast: pd.DataFrame, signals: pd.DataFrame, inst: Instrument,
                 signal_step: pd.Timedelta = pd.Timedelta(Q.timeframe)) -> pd.DataFrame:
    """One row per primary signal with the outcome of every exit policy.

    The signal bar stamped t closes at t + step; the trade is entered at the first fast bar
    at or after that time.
    """
    sig = signals[(signals["side"] != 0) & signals["atr"].notna()]
    o, h, l, c = (fast[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    ft = fast.index
    fast_step = ft[1] - ft[0]
    max_fast = int(Q.max_holding_bars * (signal_step / fast_step))
    night = ((ft - pd.Timedelta(hours=22)).floor("D").asi8 // 86_400_000_000_000
             if ft.unit == "ns" else (ft - pd.Timedelta(hours=22)).floor("D").as_unit("s").asi8 // 86_400)
    starts = ft.searchsorted(sig.index + signal_step)
    pols = policies()
    rows = []
    for (t, s), start in zip(sig.iterrows(), starts):
        if start >= len(ft) - 2 or ft[start] - (t + signal_step) > pd.Timedelta(hours=2):
            continue  # no bar to enter on (weekend gap)
        side, a = int(s["side"]), float(s["atr"])
        sl = Q.sl_mult * a
        entry = o[start]
        cost_r = 2 * inst.cost_per_side * entry / sl
        row = {"time": t, "entry_time": ft[start], "side": side, "kind": int(s["kind"]), "atr": a,
               "sl_dist": sl, "entry": entry, "cost_r": cost_r}
        last_exit = start
        for name, pol in pols.items():
            gross, mae, bars, reason = simulate_path(o, h, l, c, start, side, sl, a, pol, max_fast)
            ex = min(start + bars - 1, len(ft) - 1)
            swap_r = inst.swap_per_night * (night[ex] - night[start]) * entry / sl
            row[f"r_{name}"] = gross - cost_r - swap_r
            row[f"mae_{name}"] = mae - cost_r / 2
            row[f"reason_{name}"] = reason
            row[f"exit_{name}"] = ft[ex] + fast_step
            last_exit = max(last_exit, ex)
        row["label_end"] = ft[last_exit] + fast_step
        rows.append(row)
    return pd.DataFrame(rows).set_index("time") if rows else pd.DataFrame()
