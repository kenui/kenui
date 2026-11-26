"""Fast portfolio simulator for signals on many coins at once.

pos:   DataFrame (time x coin) of target weights decided at the CLOSE of each candle
       (long-only spot: 0..1 ; futures can be negative).
Fill:  at the OPEN of the next candle. Costs charged on every change of position.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# cost per side (fee + half spread/slippage), as a fraction
COSTS = {
    "spot_taker": 0.0010 + 0.0003,        # 0.10% fee, no BNB
    "spot_taker_bnb": 0.00075 + 0.0003,   # paying fees in BNB (-25%)
    "spot_maker_bnb": 0.00075,            # limit order: no spread paid (fill risk handled separately)
    "fut_taker_bnb": 0.00045 + 0.0003,    # USD-M futures taker with BNB (-10%)
    "fut_maker_bnb": 0.00018,
    "zero": 0.0,
}


@dataclass
class SimResult:
    daily: pd.Series      # daily net return of the portfolio
    gross: pd.Series
    turnover: float       # average traded notional per day, in units of capital (one side)
    stats: dict


def simulate(pos: pd.DataFrame, opens: pd.DataFrame, cost: float, funding: pd.DataFrame | None = None) -> SimResult:
    o = opens.reindex(pos.index).ffill()
    # position decided at close t -> held from open t+1 to open t+2
    r_next = (o.shift(-2) / o.shift(-1) - 1).fillna(0.0)
    p = pos.fillna(0.0)
    gross = (p * r_next).sum(axis=1)
    if funding is not None:   # futures: longs pay funding when positive
        gross = gross - (p.shift(1).fillna(0) * funding.reindex(pos.index).fillna(0)).sum(axis=1)
    traded = p.diff().abs().fillna(p.abs()).sum(axis=1)
    net = gross - traded * cost
    d_net, d_gross = net.resample("1D").sum(), gross.resample("1D").sum()
    return SimResult(d_net, d_gross, float(traded.resample("1D").sum().mean()), stats(d_net, d_gross, traded))


def stats(d_net: pd.Series, d_gross: pd.Series, traded: pd.Series | None = None) -> dict:
    n = len(d_net)
    eq = (1 + d_net).cumprod()
    sd = d_net.std()
    out = {
        "days": n,
        "net_total_%": round((eq.iloc[-1] - 1) * 100, 2),
        "gross_total_%": round(((1 + d_gross).prod() - 1) * 100, 2),
        "net_per_day_bps": round(d_net.mean() * 1e4, 2),
        "sharpe": round(d_net.mean() / sd * np.sqrt(365), 2) if sd > 0 else 0.0,
        "t_stat": round(d_net.mean() / sd * np.sqrt(n), 2) if sd > 0 else 0.0,
        "max_dd_%": round((eq / eq.cummax() - 1).min() * 100, 2),
        "pos_months_%": round((d_net.resample("MS").sum() > 0).mean() * 100, 0),
    }
    if traded is not None:
        out["turnover_per_day"] = round(float(traded.resample("1D").sum().mean()), 2)
    return out
