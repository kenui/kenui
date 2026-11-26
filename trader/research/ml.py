"""Machine learning that combines all signals, tested the only honest way: walk-forward.

For each month M: train only on data that ended before M (with a gap so no future return
leaks in), then predict every 5-minute candle of M. Predictions are saved; trading rules
are judged only on these never-seen-before predictions.
"""
from __future__ import annotations

import sys

import lightgbm as lgb
import numpy as np
import pandas as pd

from research import dataset as DS

TARGETS = {"fwd_1h": 12, "fwd_4h": 48, "fwd_24h": 288}
DROP = {"sym", "open_next", "f_fwd_1h"} | {f"fwd_{h}" for h in ("5m", "15m", "1h", "4h", "24h")}
PARAMS = dict(objective="huber", alpha=1.0, learning_rate=0.03, num_leaves=31, min_data_in_leaf=3000,
              feature_fraction=0.5, bagging_fraction=0.5, bagging_freq=1, lambda_l2=10.0,
              num_threads=4, verbose=-1, seed=7)
ROUNDS = 400


def run(first_test="2025-07-01", last_test="2026-06-30", tag="research", train_step=3):
    big = DS.load()
    feats = [c for c in big.columns if c not in DROP]
    months = pd.date_range(first_test, last_test, freq="MS", tz="UTC")
    out = []
    imp = pd.Series(0.0, index=feats)
    for m in months:
        m_end = m + pd.offsets.MonthBegin(1)
        test = big.loc[(big.index >= m) & (big.index < m_end)]
        if not len(test):
            continue
        res = test[["sym", "open_next"] + [c for c in big.columns if c.startswith("fwd_")]].copy()
        for tgt, h in TARGETS.items():
            cut = m - pd.Timedelta(minutes=5 * (h + 2)) - pd.Timedelta(days=1)   # purge: no label overlaps the test month
            tr = big.loc[big.index < cut].iloc[::train_step]
            tr = tr[tr[tgt].notna()]
            y = tr[tgt].astype("float64")
            scale = y.std()
            y = (y / scale).clip(-5, 5)                                           # tame crazy candles
            model = lgb.train(PARAMS, lgb.Dataset(tr[feats], y), ROUNDS)
            res["pred_" + tgt[4:]] = model.predict(test[feats]) * scale
            imp += pd.Series(model.feature_importance("gain"), index=feats)
        ic = {t: res[f"pred_{t[4:]}"].corr(res[t], method="spearman") for t in TARGETS}
        print(f"{m:%Y-%m} train<{cut:%Y-%m-%d} n_test={len(test)} IC " + " ".join(f"{k}={v:.4f}" for k, v in ic.items()), flush=True)
        out.append(res)
    preds = pd.concat(out)
    preds.to_parquet(DS.OUT.parent / f"preds_{tag}.parquet")
    (imp / imp.sum()).sort_values(ascending=False).head(40).to_csv(DS.OUT.parent / f"importance_{tag}.csv")
    return preds


def report(tag="research"):
    p = pd.read_parquet(DS.OUT.parent / f"preds_{tag}.parquet")
    for t in ("1h", "4h", "24h"):
        pr, y = p[f"pred_{t}"], p[f"fwd_{t}"]
        q = pd.qcut(pr.rank(method="first"), [0, .01, .05, .2, .5, .8, .95, .99, .999, 1.0])
        g = pd.DataFrame({"pred_bps": pr.groupby(q, observed=True).mean() * 1e4,
                          "real_bps": y.groupby(q, observed=True).mean() * 1e4,
                          "n": y.groupby(q, observed=True).size()})
        print(f"\n== horizon {t}: what really happened, by how optimistic the model was ==")
        print(g.round(1).to_string())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "holdout":
        run("2026-07-01", "2026-11-24", "holdout")
        report("holdout")
    else:
        run()
        report()
