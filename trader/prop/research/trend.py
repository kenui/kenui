"""Slow strategies for MetaTrader-style markets: daily time-series trend with volatility-sized
positions. Costs as charged by CFD prop firms: spread/commission per side and a daily swap.

Each (asset, rule) produces a daily net return series for a position sized so that one day of
normal volatility moves the account by `1 unit`; the portfolio averages them. Everything uses
the previous day's close to decide and the next day's open-to-open path to get paid.
"""
from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path("data/majors_1h.pkl")
# per-side cost and daily swap (fraction of notional), conservative CFD figures
COSTS = {"BTC": (0.0005, 0.0006), "ETH": (0.0006, 0.0006), "PAXG": (0.00020, 0.00015), "EUR": (0.00007, 0.00004)}
ALT_COST = (0.0020, 0.0006)
SPLIT = pd.Timestamp("2023-01-01", tz="UTC")       # rules are chosen before this date, judged after


def load() -> dict[str, pd.DataFrame]:
    return pickle.load(DATA.open("rb"))


def daily(h: pd.DataFrame) -> pd.DataFrame:
    d = h.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    return d


def vol(d: pd.DataFrame, n: int = 30) -> pd.Series:
    return np.log(d["close"]).diff().ewm(span=n, min_periods=n).std()


def sig_donchian(d: pd.DataFrame, n: int) -> pd.Series:
    """+1 after a close above the n-day high, -1 below the n-day low, flat after crossing the n/2 channel back."""
    hi, lo = d["high"].rolling(n).max().shift(1), d["low"].rolling(n).min().shift(1)
    xh, xl = d["high"].rolling(n // 2).max().shift(1), d["low"].rolling(n // 2).min().shift(1)
    pos, out = 0, np.zeros(len(d))
    c = d["close"].to_numpy()
    for i in range(len(d)):
        if np.isnan(hi.iloc[i]):
            continue
        if pos == 0:
            pos = 1 if c[i] > hi.iloc[i] else (-1 if c[i] < lo.iloc[i] else 0)
        elif pos == 1 and c[i] < xl.iloc[i]:
            pos = 0
        elif pos == -1 and c[i] > xh.iloc[i]:
            pos = 0
        out[i] = pos
    return pd.Series(out, index=d.index)


def sig_tsmom(d: pd.DataFrame, n: int) -> pd.Series:
    """Sign of the n-day return."""
    return np.sign(d["close"].pct_change(n)).fillna(0.0)


def sig_ema(d: pd.DataFrame, fast: int, slow: int) -> pd.Series:
    f, s = d["close"].ewm(span=fast).mean(), d["close"].ewm(span=slow).mean()
    return np.sign(f - s).where(s.notna(), 0.0)


RULES = {
    **{f"donchian{n}": (lambda d, n=n: sig_donchian(d, n)) for n in (20, 55, 100)},
    **{f"tsmom{n}": (lambda d, n=n: sig_tsmom(d, n)) for n in (30, 90, 180)},
    **{f"ema{a}_{b}": (lambda d, a=a, b=b: sig_ema(d, a, b)) for a, b in ((10, 40), (20, 100), (50, 200))},
}


def net_returns(d: pd.DataFrame, signal: pd.Series, cost: tuple[float, float], long_only: bool = False,
                target: float = 0.01) -> pd.Series:
    """Daily net return of the account. Decision at the close of day t, traded at the open of
    t+1, position notional = target / volatility (capped at 3x)."""
    s = signal.clip(lower=0.0) if long_only else signal
    w = (s * (target / vol(d)).clip(upper=3.0)).shift(1).fillna(0.0)        # held from open t+1
    oo = d["open"].shift(-1) / d["open"] - 1.0                              # open(t) -> open(t+1)
    gross = w * oo
    turn = (w - w.shift(1).fillna(0.0)).abs()
    return (gross - turn * cost[0] - w.abs() * cost[1]).dropna()


def table(data: dict[str, pd.DataFrame] | None = None, long_only: bool = False) -> pd.DataFrame:
    """Columns: (asset, rule) -> daily net returns at 1% daily volatility per position."""
    data = data or load()
    cols = {}
    for a, h in data.items():
        d = daily(h)
        for name, fn in RULES.items():
            cols[(a, name)] = net_returns(d, fn(d), COSTS.get(a, ALT_COST), long_only)
    return pd.DataFrame(cols)


def sharpe(x: pd.Series) -> float:
    x = x.dropna()
    return float(x.mean() / x.std() * np.sqrt(365)) if len(x) > 30 and x.std() > 0 else float("nan")
