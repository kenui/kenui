"""Turn model predictions into trades and count the money, after costs.

Rule (long-only spot, what a small Binance account can do):
  * up to K positions, each 1/K of the account
  * buy a coin when the model expects more than `theta` over the next `h` candles
  * sell after `h` candles, unless the model still expects more than `theta` (then keep, no new fee)
  * buy/sell at the open of the next candle; pay `cost` on each side
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research import dataset as DS
from research.sim import COSTS

HB = {"1h": 12, "4h": 48, "24h": 288}


def wide(p: pd.DataFrame, col: str) -> pd.DataFrame:
    return p.pivot_table(index=p.index, columns="sym", values=col, observed=True)


def trade(pred: pd.DataFrame, px: pd.DataFrame, h: int, theta: float, cost: float, K: int = 5,
          short: bool = False) -> tuple[pd.Series, pd.DataFrame]:
    P, X = pred.to_numpy(), px.reindex(pred.index).to_numpy()
    T, N = P.shape
    held_since = np.full(N, -1)
    entry_px = np.zeros(N)
    alloc = np.zeros(N)
    equity, free = 1.0, K
    eq_curve = np.empty(T)
    trades = []
    sgn = -1.0 if short else 1.0
    for t in range(T):
        p = P[t] * sgn
        # exits
        for j in np.nonzero(held_since >= 0)[0]:
            if t - held_since[j] >= h and not (p[j] > theta) and np.isfinite(X[t, j]):
                r = sgn * (X[t, j] / entry_px[j] - 1) - 2 * cost
                equity += alloc[j] * r
                trades.append((pred.index[held_since[j]], pred.index[t], pred.columns[j], r))
                held_since[j] = -1
                free += 1
        # entries
        if free > 0:
            cand = np.nonzero((p > theta) & (held_since < 0) & np.isfinite(X[t]))[0]
            if len(cand):
                for j in cand[np.argsort(-p[cand])][:free]:
                    held_since[j], entry_px[j], alloc[j] = t, X[t, j], equity / K
                    free -= 1
        eq_curve[t] = equity
    eq = pd.Series(eq_curve, index=pred.index)
    return eq, pd.DataFrame(trades, columns=["t_in", "t_out", "sym", "ret"])


def summarize(eq: pd.Series, tr: pd.DataFrame) -> dict:
    d = eq.resample("1D").last().pct_change().dropna()
    n = len(tr)
    return {"net_%": round((eq.iloc[-1] / eq.iloc[0] - 1) * 100, 1),
            "sharpe": round(d.mean() / d.std() * np.sqrt(365), 2) if d.std() > 0 else 0,
            "t": round(d.mean() / d.std() * np.sqrt(len(d)), 2) if d.std() > 0 else 0,
            "maxdd_%": round((eq / eq.cummax() - 1).min() * 100, 1),
            "trades": n, "avg_trade_bps": round(tr["ret"].mean() * 1e4, 1) if n else 0,
            "win_%": round((tr["ret"] > 0).mean() * 100, 1) if n else 0,
            "pos_months": f"{int((eq.resample('MS').last().pct_change().dropna() > 0).sum())}/{len(eq.resample('MS').last()) - 1}"}


def grid(tag="research", cost_name="spot_taker_bnb", periods=None, short=False, hs=("1h", "4h", "24h"),
         thetas=(0.001, 0.002, 0.003, 0.005, 0.008, 0.012)):
    p = pd.read_parquet(DS.OUT.parent / f"preds_{tag}.parquet")
    px = wide(p, "open_next")
    cost = COSTS[cost_name]
    rows = []
    for hn in hs:
        pr = wide(p, f"pred_{hn}")
        for th in thetas:
            for name, (a, b) in (periods or {"all": (None, None)}).items():
                eq, tr = trade(pr.loc[a:b], px.loc[a:b], HB[hn], th, cost, short=short)
                rows.append({"h": hn, "theta_bps": th * 1e4, "period": name, **summarize(eq, tr)})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    import sys
    pd.set_option("display.width", 200)
    periods = {"A 2025H2": ("2025-07-01", "2025-12-31"), "B 2026H1": ("2026-01-01", "2026-06-30")}
    cn = sys.argv[1] if len(sys.argv) > 1 else "spot_taker_bnb"
    print("cost per side:", cn)
    print(grid(cost_name=cn, periods=periods).to_string(index=False))
