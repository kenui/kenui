"""Dress rehearsal of the paper bot on recorded data (no network).

1. Speed/memory of one live cycle and exact match of the bot's forecast with the research pipeline.
2. The bot's paper account, fed bar by bar, must reproduce the backtest's trades.
"""
from __future__ import annotations

import resource
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

import paper_bot as B
from research import dataset as DS, panel as P, rules as R


def main():
    model = B.Model()
    # ---- 1) one cycle from raw panels
    T = pd.Timestamp("2026-11-21 04:15", tz="UTC")
    panels = {s: df.loc[T - pd.Timedelta(days=B.HIST_DAYS):T] for s, df in P.load_all().items() if s != "FTMUSDT"}
    t0 = time.time()
    feats = B.latest_features(panels, T)
    pred_bot = model.predict(feats)
    dt = time.time() - t0
    ref = pd.read_parquet(DS.OUT, filters=[("time", "==", T)]).set_index("sym")
    pred_ref = pd.Series(model.booster.predict(ref[model.feats].to_numpy(dtype="float32")) * model.scale, index=ref.index)
    both = pd.concat([pred_bot, pred_ref], axis=1, keys=["bot", "research"]).dropna()
    print(f"cycle compute time {dt:.1f}s; peak memory {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1e6:.2f} GB")
    print(f"forecast match on {len(both)} coins: max abs diff {1e4*(both.bot-both.research).abs().max():.2f} bps, corr {both.bot.corr(both.research):.4f}")
    del panels

    # ---- 2) account logic vs backtest on two months of bars
    d = pd.read_parquet(DS.OUT, filters=[("time", ">=", pd.Timestamp("2026-10-01", tz="UTC"))])
    d = d[d["sym"] != "FTMUSDT"]
    d["pred_1h"] = model.booster.predict(d[model.feats].to_numpy(dtype="float32")) * model.scale
    pr = R.wide(d, "pred_1h")
    px = R.wide(d, "open_next").reindex(pr.index)
    eq, tr = R.trade(pr, px, B.HOLD_BARS, B.THETA, B.FEE, K=B.K)
    B.OUT = Path(tempfile.mkdtemp())
    acct = B.Account()
    spot_of = {s: s for s in pr.columns}
    n = 0
    for T, row in pr.iterrows():
        book = pd.DataFrame({"bidPrice": px.loc[T], "askPrice": px.loc[T]}).dropna()
        n += len(acct.step(T, row.dropna(), book, spot_of))
    bt_ret = eq.iloc[-1] - 1
    bot_ret = acct.equity / B.START_CAPITAL - 1
    closed_bt = len(tr)
    print(f"backtest: {closed_bt} trades, {bt_ret*100:.2f}% | bot account: {n} closed (+{len(acct.pos)} open), {bot_ret*100:.2f}%")
    print("(in-sample numbers: this only checks that the bot's bookkeeping equals the backtest's)")
    assert abs(n + len(acct.pos) - closed_bt) <= B.K and abs(bt_ret - bot_ret) < 0.01


if __name__ == "__main__":
    main()
