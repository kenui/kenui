"""Baseline strategies. They are the yardstick: any new idea in step 2
must beat these after costs, on data it was not tuned on.

Each function returns (entries, exits, risk_overrides).
"""
from __future__ import annotations

import pandas as pd


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, float("nan")))


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    pc = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def ema_cross(df, fast=12, slow=48, sl=0.02, tp=0.04):
    f, s = ema(df["close"], fast), ema(df["close"], slow)
    entries = (f > s) & (f.shift() <= s.shift())
    exits = (f < s) & (f.shift() >= s.shift())
    return entries, exits, {"stop_loss": sl, "take_profit": tp}


def donchian_breakout(df, n=48, vol_mult=1.5, sl=0.02, tp=0.05):
    """Buy a close above the n-bar high, only with above-average volume."""
    hi = df["high"].rolling(n).max().shift()
    vol_ok = df["volume"] > df["volume"].rolling(n).mean() * vol_mult
    entries = (df["close"] > hi) & vol_ok
    return entries, None, {"stop_loss": sl, "take_profit": tp}


def rsi_reversion(df, n=14, low=25, trend=200, sl=0.02, tp=0.02, max_bars=24):
    """Buy oversold dips while the longer trend is up."""
    r = rsi(df["close"], n)
    up = df["close"] > ema(df["close"], trend)
    entries = (r < low) & up
    exits = r > 55
    return entries, exits, {"stop_loss": sl, "take_profit": tp, "max_bars": max_bars}


def volatility_squeeze(df, n=48, squeeze_q=0.2, sl=0.015, tp=0.045):
    """Bollinger width at a low quantile, then a breakout above the upper band."""
    m = df["close"].rolling(n).mean()
    sd = df["close"].rolling(n).std()
    width = (4 * sd / m)
    squeezed = width < width.rolling(n * 10).quantile(squeeze_q)
    entries = squeezed.shift().fillna(False).astype(bool) & (df["close"] > m + 2 * sd)
    return entries, None, {"stop_loss": sl, "take_profit": tp}


def grid(**axes) -> list[dict]:
    """grid(a=[1,2], b=[3]) -> [{'a':1,'b':3}, {'a':2,'b':3}]"""
    out = [{}]
    for k, vals in axes.items():
        out = [{**o, k: v} for o in out for v in vals]
    return out


BASELINES = {
    "ema_cross": (ema_cross, grid(fast=[8, 12, 21], slow=[48, 96], sl=[0.015, 0.03], tp=[0.03, 0.06])),
    "donchian_breakout": (donchian_breakout, grid(n=[24, 48, 96], vol_mult=[1.0, 2.0], sl=[0.015, 0.03], tp=[0.03, 0.06])),
    "rsi_reversion": (rsi_reversion, grid(low=[20, 30], trend=[100, 300], sl=[0.015, 0.03], tp=[0.015, 0.03])),
    "volatility_squeeze": (volatility_squeeze, grid(n=[24, 48], squeeze_q=[0.1, 0.25], sl=[0.01, 0.02], tp=[0.03, 0.06])),
}
