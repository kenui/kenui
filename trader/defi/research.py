"""Does providing concentrated liquidity pay, out of sample, with a small account?

Usage: python -m defi.research <pool-name> [--holdout]
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from .chain import DATA_DIR, block_ts
from .clmm import Costs, prepare, simulate, unit_edge
from .download import POOLS

H = 24            # forecast horizon in bars (4 hours); set by load() from the data's bar size
BAR_PER_DAY = 144
HOLDOUT_START = pd.Timestamp("2026-08-25", tz="UTC")   # touched once, at the very end
MIN_TRAIN_DAYS = 90


def load(name: str) -> pd.DataFrame:
    addr, d0, d1, *_ = POOLS[name]
    raw = pd.read_pickle(DATA_DIR / f"{name}.pkl")
    df = prepare(raw, d0, d1, block_ts)
    global H, BAR_PER_DAY
    bar_s = int(pd.Series(df.ts).diff().median())
    H, BAR_PER_DAY = 4 * 3600 // bar_s, 86400 // bar_s
    if "x1" in raw.columns:  # Aerodrome: AERO rewards paid to staked liquidity
        df = add_aero_rewards(df, raw, d0, d1)
    return df[~df.index.duplicated()]


def add_aero_rewards(df, raw, d0, d1):
    """Staked Aerodrome LPs give up the swap fees and receive AERO instead.
    rewardGrowthGlobalX128 = AERO (18 decimals) per unit of staked liquidity."""
    import requests
    raw = raw[(raw.sqrtPriceX96 > 0) & (raw.liquidity > 0)]
    rg = raw.x1.tolist()
    lscale = 10 ** ((d0 + d1) / 2)
    d = [0.0] + [((b - a) % 2 ** 256) / 2 ** 128 for a, b in zip(rg[:-1], rg[1:])]
    df["aero_per_L"] = np.array(d) * lscale / 1e18
    df["staked_share"] = np.array([int(a) / max(int(b), 1) for a, b in zip(raw.x0, raw.liquidity)])
    df["fee_tier"] = np.array([int(v) for v in raw.x2]) / 1e6
    # hourly AERO price from Binance public data
    rows, t = [], int(df.ts.iloc[0]) * 1000
    while t < int(df.ts.iloc[-1]) * 1000:
        k = requests.get("https://data-api.binance.vision/api/v3/klines",
                         params={"symbol": "AEROUSDT", "interval": "1h", "startTime": t, "limit": 1000},
                         timeout=30).json()
        if not k:
            break
        rows += [(r[0] // 1000, float(r[4])) for r in k]
        t = k[-1][0] + 3600_000
    px = pd.Series(dict(rows)).sort_index()
    df["aero_px"] = px.reindex(df.ts.values, method="ffill").values
    df["f1_fee_only"] = df.f1
    df["f0_fee_only"] = df.f0
    # treat rewards as extra token1 income so the same simulator can be reused
    df["f1"] = df.aero_per_L * df.aero_px
    df["f0"] = 0.0
    return df.dropna(subset=["aero_px"])


def features(df: pd.DataFrame, u: pd.DataFrame) -> pd.DataFrame:
    """Everything here uses data up to and including the current bar only."""
    r2 = u.ret ** 2
    X = pd.DataFrame(index=u.index)
    b = BAR_PER_DAY
    for label, n in [("1h", b // 24), ("4h", b // 6), ("24h", b), ("7d", 7 * b)]:
        X[f"lrv_{label}"] = np.log(r2.rolling(n).mean() + 1e-12)
        X[f"lfee_{label}"] = np.log(u.fee_n.rolling(n).mean() + 1e-14)
    hour = u.index.hour + u.index.minute / 60
    X["h_sin"] = np.sin(2 * np.pi * hour / 24)
    X["h_cos"] = np.cos(2 * np.pi * hour / 24)
    X["weekend"] = (u.index.dayofweek >= 5).astype(float)
    # targets: next 4 hours (strictly after the current bar)
    fwd = lambda s: s[::-1].rolling(H).sum()[::-1].shift(-1)
    X["y_loss"] = fwd(u.loss_n)
    X["y_fee"] = fwd(u.fee_n)
    return X


FEATS = ["lrv_1h", "lrv_4h", "lrv_24h", "lrv_7d", "lfee_1h", "lfee_4h", "lfee_24h", "lfee_7d",
         "h_sin", "h_cos", "weekend"]


def _ridge(Xtr, ytr, Xte, lam=1.0):
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
    A = (Xtr - mu) / sd
    B = (Xte - mu) / sd
    w = np.linalg.solve(A.T @ A + lam * np.eye(A.shape[1]), A.T @ (ytr - ytr.mean()))
    return B @ w + ytr.mean()


def walk_forward(X: pd.DataFrame) -> pd.DataFrame:
    """Monthly expanding-window refit. Predictions for month m use only data before it
    (minus the 4h label overlap)."""
    ok = X.dropna(subset=FEATS)
    months = sorted(set(ok.index.tz_localize(None).to_period("M")))
    out = []
    for m in months:
        start = m.start_time.tz_localize("UTC")
        tr = ok[(ok.index < start - pd.Timedelta(hours=5))].dropna(subset=["y_loss", "y_fee"])
        te = ok[(ok.index >= start) & (ok.index < (m + 1).start_time.tz_localize("UTC"))]
        if len(tr) < MIN_TRAIN_DAYS * BAR_PER_DAY or te.empty:
            continue
        p = pd.DataFrame(index=te.index)
        # predict logs, then convert to expected levels with the in-sample smearing factor
        for tgt in ("y_loss", "y_fee"):
            ytr = np.log(tr[tgt].values + 1e-12)
            fit_tr = _ridge(tr[FEATS].values, ytr, tr[FEATS].values)
            smear = tr[tgt].mean() / np.exp(fit_tr).mean()
            p["p_" + tgt[2:]] = np.exp(_ridge(tr[FEATS].values, ytr, te[FEATS].values)) * smear
        # threshold for "good hours" learned on the training window only
        tr_ratio = np.exp(_ridge(tr[FEATS].values, np.log(tr.y_fee.values + 1e-12), tr[FEATS].values)) / \
            np.exp(_ridge(tr[FEATS].values, np.log(tr.y_loss.values + 1e-12), tr[FEATS].values))
        for q in (0.3, 0.5, 0.7):
            p[f"thr_{int(q * 100)}"] = np.quantile(tr_ratio, q) * 1.0
        p["ratio_raw"] = p.p_fee / p.p_loss  # includes smearing; thresholds use the same scale below
        p["ratio"] = p.ratio_raw / (tr.y_fee.mean() / np.exp(_ridge(tr[FEATS].values, np.log(tr.y_fee.values + 1e-12), tr[FEATS].values)).mean()) * \
            (tr.y_loss.mean() / np.exp(_ridge(tr[FEATS].values, np.log(tr.y_loss.values + 1e-12), tr[FEATS].values)).mean())
        out.append(p)
    return pd.concat(out)


def summarize(eq: pd.DataFrame, df: pd.DataFrame, capital=60.0) -> dict:
    p0, p1 = df.price.iloc[0], df.price.iloc[-1]
    hold = capital / 2 + capital / 2 * p1 / p0
    days = (df.index[-1] - df.index[0]).total_seconds() / 86400
    v = eq.value
    dd = (v / v.cummax() - 1).min()
    return {
        "final_usd": round(v.iloc[-1], 2),
        "ret_%": round((v.iloc[-1] / capital - 1) * 100, 1),
        "vs_hold5050_%": round((v.iloc[-1] / hold - 1) * 100, 1),
        "fees_usd": round(eq.fees.iloc[-1], 2),
        "costs_usd": round(eq.costs.iloc[-1], 2),
        "reopens": int(eq.n_open.iloc[-1]),
        "in_range_%": round(eq.in_range.mean() * 100),
        "max_dd_%": round(dd * 100, 1),
        "days": round(days),
    }


def run(name: str, holdout: bool = False) -> None:
    df = load(name)
    u = unit_edge(df)
    X = features(df, u)
    pred = walk_forward(X)
    fee = POOLS[name][3] or 0.0005
    costs = Costs(swap_fee=fee)

    if holdout:
        span = pred.index[pred.index >= HOLDOUT_START]
    else:
        span = pred.index[pred.index < HOLDOUT_START]
    label = "HOLDOUT" if holdout else "RESEARCH (walk-forward, out of sample)"
    d = df.loc[span]
    uu = u.loc[span]
    pp = pred.loc[span]
    Xs = X.loc[span]
    days = (span[-1] - span[0]).total_seconds() / 86400
    print(f"\n=== {name} | {label} | {span[0]:%Y-%m-%d} .. {span[-1]:%Y-%m-%d} ({days:.0f} days) ===")
    print(f"price {d.price.iloc[0]:.2f} -> {d.price.iloc[-1]:.2f} ({(d.price.iloc[-1] / d.price.iloc[0] - 1) * 100:+.1f}%)")

    # 1) width-free test: fee income vs rebalancing loss of in-range liquidity
    f, l = uu.fee_n.sum(), uu.loss_n.sum()
    print(f"\n[1] unit liquidity: fees {f * 100:.2f}% vs loss {l * 100:.2f}% of full-range capital "
          f"-> fee/loss = {f / l:.2f}  (annualised {f / days * 36500:.1f}% vs {l / days * 36500:.1f}%)")
    mm = uu.resample("MS").sum()
    print("    monthly fee/loss:", " ".join(f"{a:%m/%y}:{b:.2f}" for a, b in (mm.fee_n / mm.loss_n).items()))

    # 2) is the next 4h predictable?
    v = Xs.dropna(subset=["y_loss", "y_fee"]).join(pp)
    c_loss = np.corrcoef(np.log(v.p_loss), np.log(v.y_loss + 1e-12))[0, 1]
    c_fee = np.corrcoef(np.log(v.p_fee), np.log(v.y_fee + 1e-12))[0, 1]
    print(f"\n[2] forecast quality (log, next 4h): volatility/loss corr {c_loss:.2f}, fees corr {c_fee:.2f}")
    v["q"] = pd.qcut(v.ratio, 5, labels=False)
    g = v.groupby("q").agg(fee=("y_fee", "mean"), loss=("y_loss", "mean"), n=("y_fee", "size"))
    g["fee/loss"] = g.fee / g.loss
    g["net_bp_per_4h"] = (g.fee - g.loss) * 1e4
    print("    realised result by predicted fee/loss quintile (0 = worst hours, 4 = best hours):")
    print(g[["fee/loss", "net_bp_per_4h", "n"]].round(3).to_string().replace("\n", "\n    "))

    # 3) $60 back-tests with costs
    rows = {}
    for w in (0.01, 0.02, 0.05, 0.10, 0.20, 0.50):
        rows[f"fixed ±{w * 100:.0f}%"] = summarize(simulate(d, w, costs=costs), d)
    sig = np.sqrt(pp.p_loss.values * 8)  # predicted 4h volatility (std of log return)
    for k in (2, 4, 8):
        rows[f"vol-scaled ±{k}σ(4h), recentre 4h"] = summarize(
            simulate(d, np.clip(k * sig, 0.005, 0.6), costs=costs, recenter_every=H), d)
        rows[f"vol-scaled ±{k}σ(4h), on exit"] = summarize(
            simulate(d, np.clip(k * sig, 0.005, 0.6), costs=costs), d)
    for q in (30, 50, 70):
        act = (pp.ratio.values > pp[f"thr_{q}"].values)
        # avoid flapping: decide once every 4 hours
        act = pd.Series(act, index=span).groupby(np.arange(len(span)) // H).transform("first").values
        for w in (0.05, 0.10):
            rows[f"gated top{100 - q}% hours, ±{w * 100:.0f}%, idle=USDC"] = summarize(
                simulate(d, w, costs=costs, active=act, idle_asset="usdc"), d)
            rows[f"gated top{100 - q}% hours, ±{w * 100:.0f}%, idle=coins"] = summarize(
                simulate(d, w, costs=costs, active=act, idle_asset="hold"), d)
    p0, p1 = d.price.iloc[0], d.price.iloc[-1]
    res = pd.DataFrame(rows).T
    print("\n[3] US$ 60 back-test, all costs included")
    print(f"    benchmarks: USDC 60.00 | hold 50/50 {30 + 30 * p1 / p0:.2f} | 100% coin {60 * p1 / p0:.2f}")
    print(res.to_string())
    res.insert(0, "pool", name)
    res.insert(1, "period", "holdout" if holdout else "research")
    out = DATA_DIR / f"result_{name}_{'holdout' if holdout else 'research'}.csv"
    res.to_csv(out)


if __name__ == "__main__":
    run(sys.argv[1], holdout="--holdout" in sys.argv)
