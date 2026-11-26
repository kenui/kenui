"""Scan every signal x holding time for predictive power, BEFORE costs, research period only.

Two views:
  TS (time series): when the signal is extreme for a coin (z > 2 or < -2 vs its own last 7 days),
      what does that coin do next, minus what it normally does?
  XS (cross section): rank the coins by the signal; return of top fifth minus bottom fifth.
t-stats are computed on daily aggregates so overlapping trades do not fake significance.
"""
from __future__ import annotations

import sys
import numpy as np
import pandas as pd

from research import features as F
from research import panel as P

RESEARCH = ("2025-01-01", "2026-06-30")   # everything after is the locked final exam
HOLDOUT = ("2026-07-01", "2026-11-24")
SKIP = {"hour_sin", "hour_cos", "dow", "to_funding", "beta", "vol_1d"}


def build(period=RESEARCH, syms=None):
    data = P.load_all()
    btc = data["BTCUSDT"]
    feats, fwd = {}, {}
    for s, df in data.items():
        if syms and s not in syms:
            continue
        if len(df) < 60 * F.D:
            continue
        X = F.make(df, btc)
        Y = F.forward_returns(df)
        ok = df["traded"].rolling(12).sum() >= 10        # skip halts / illiquid patches
        X, Y = X[ok], Y[ok]
        feats[s], fwd[s] = X.loc[period[0]:period[1]], Y.loc[period[0]:period[1]]
    return feats, fwd


def tstat(x: pd.Series):
    x = x.dropna()
    return (x.mean() / x.std() * np.sqrt(len(x))) if len(x) > 20 and x.std() > 0 else np.nan


def main():
    feats, fwd = build()
    syms = list(feats)
    cols = [c for c in feats[syms[0]].columns if c not in SKIP]
    rows = []
    for hname, h in F.HORIZONS.items():
        y = pd.DataFrame({s: fwd[s][f"fwd_{hname}"] for s in syms})
        ymean = y.rolling(7 * F.D, min_periods=F.D).mean().shift(h + 2)   # coin's usual drift, known at t
        for c in cols:
            x = pd.DataFrame({s: feats[s][c] for s in syms})
            # ---- TS extremes
            z = (x - x.rolling(7 * F.D, min_periods=F.D).mean()) / x.rolling(7 * F.D, min_periods=F.D).std()
            for side, mask in (("hi", z > 2), ("lo", z < -2)):
                ev = (y - ymean).where(mask)
                daily = ev.stack().groupby(level=0).mean().resample("1D").mean()
                rows.append({"view": "TS", "signal": c, "side": side, "horizon": hname,
                             "mean_bps": ev.stack().mean() * 1e4, "t": tstat(daily),
                             "n": int(mask.sum().sum()), "days": int(daily.notna().sum())})
            # ---- XS quintiles, non-overlapping rebalances
            xs, ys = x.iloc[::h], y.iloc[::h]
            r = xs.rank(axis=1, pct=True)
            n = xs.notna().sum(axis=1)
            top = ys.where(r > 0.8).mean(axis=1)
            bot = ys.where(r <= 0.2).mean(axis=1)
            mkt = ys.where(xs.notna()).mean(axis=1)
            good = n >= 15
            ls = (top - bot)[good]
            lo_ex = (top - mkt)[good]
            rows.append({"view": "XS", "signal": c, "side": "top-bot", "horizon": hname,
                         "mean_bps": ls.mean() * 1e4, "t": tstat(ls.resample("1D").sum(min_count=1)),
                         "n": int(good.sum()), "days": int(ls.resample("1D").sum(min_count=1).notna().sum())})
            rows.append({"view": "XS", "signal": c, "side": "top-mkt", "horizon": hname,
                         "mean_bps": lo_ex.mean() * 1e4, "t": tstat(lo_ex.resample("1D").sum(min_count=1)),
                         "n": int(good.sum()), "days": int(lo_ex.resample("1D").sum(min_count=1).notna().sum())})
            rows.append({"view": "XS", "signal": c, "side": "bot-mkt", "horizon": hname,
                         "mean_bps": (bot - mkt)[good].mean() * 1e4,
                         "t": tstat((bot - mkt)[good].resample("1D").sum(min_count=1)),
                         "n": int(good.sum()), "days": 0})
        print("done", hname, flush=True)
    rep = pd.DataFrame(rows)
    rep.to_csv("data/scan_research.csv", index=False)
    pd.set_option("display.width", 200)
    print("tests:", len(rep))
    print(rep.reindex(rep["t"].abs().sort_values(ascending=False).index).head(70).to_string(index=False))


if __name__ == "__main__":
    main()
