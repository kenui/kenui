"""Build one big table (time, coin) with all signals + future returns, for ML and rule tests."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from research import features as F
from research import panel as P

OUT = P.PANEL.parent / "dataset.parquet"
XS_COLS = ["ret_15m", "ret_1h", "ret_4h", "ret_24h", "ret_7d", "flow_s_1h", "flow_s_24h", "flow_f_1h",
           "funding", "prem", "doi_1h", "doi_24h", "top_pos_ls_z", "acct_ls_z", "vol_1d", "vol_surge"]
MKT_COLS = ["ret_5m", "ret_15m", "ret_1h", "ret_4h", "ret_24h", "flow_s_1h", "flow_f_1h", "funding", "prem",
            "doi_1h", "doi_24h", "liq_long", "liq_short", "liq_long_1h", "vol_surge", "vol_ratio"]


def build(step: int = 1) -> pd.DataFrame:
    data = P.load_all()
    btc = data["BTCUSDT"]
    Xs, Ys = {}, {}
    for s, df in data.items():
        if len(df) < 60 * F.D:
            continue
        X = F.make(df, btc)
        Y = F.forward_returns(df)
        Y["f_fwd_1h"] = F.forward_returns(df, "f_open")["fwd_1h"]
        ok = (df["traded"].rolling(12).sum() >= 10)
        X["ok"] = ok.astype("float32")
        X["open_next"] = df["open"].shift(-1).astype("float64")
        Xs[s], Ys[s] = X, Y
    # market-wide and cross-sectional context
    idx = btc.index
    mkt = {c: pd.DataFrame({s: Xs[s][c].reindex(idx) for s in Xs}) for c in set(XS_COLS) | set(MKT_COLS)}
    mkt_mean = {c: mkt[c].mean(axis=1) for c in MKT_COLS}
    breadth = (mkt["ret_1h"] > 0).mean(axis=1)
    disp = mkt["ret_1h"].std(axis=1)
    frames = []
    for s in Xs:
        X = Xs[s]
        for c in MKT_COLS:
            X[f"mkt_{c}"] = mkt_mean[c].reindex(X.index).astype("float32")
        X["mkt_breadth"] = breadth.reindex(X.index).astype("float32")
        X["mkt_disp"] = disp.reindex(X.index).astype("float32")
        for c in XS_COLS:
            X[f"xs_{c}"] = (mkt[c].rank(axis=1, pct=True)[s]).reindex(X.index).astype("float32")
        Z = pd.concat([X, Ys[s]], axis=1).iloc[::step]
        Z = Z.loc["2025-01-01":]
        Z = Z[Z["ok"] > 0].drop(columns="ok")
        Z["sym"] = s
        frames.append(Z)
    big = pd.concat(frames)
    big["sym"] = big["sym"].astype("category")
    big.to_parquet(OUT)
    return big


def load() -> pd.DataFrame:
    return pd.read_parquet(OUT)


if __name__ == "__main__":
    b = build()
    print(b.shape, b.index.min(), b.index.max(), round(b.memory_usage().sum() / 1e9, 2), "GB")
