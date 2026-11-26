"""Same ML signal, cheaper execution: limit (maker) orders on FDUSD pairs, which have 0% maker fee.

Fill model on 1-minute candles (pessimistic on purpose):
  * buy limit at the last traded price when the signal fires; it only counts as filled if a
    later 1-minute candle trades strictly BELOW the limit within `wait` minutes (so we are
    filled mostly when price keeps falling = adverse selection is included);
  * after `hold` minutes, sell limit at the last price; filled only if price trades strictly
    ABOVE within `wait_out` minutes, otherwise sell at market paying the taker fee + spread.
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import numpy as np
import pandas as pd

from kenui_trader import vision as v
from research import dataset as DS, panel as P, rules as R
from research.sim import COSTS

TAKER = 0.00075 + 0.0005   # market exit on a thinner FDUSD book


def signals(tag, theta=0.005, K=5):
    p = pd.read_parquet(DS.OUT.parent / f"preds_{tag}.parquet")
    eq, tr = R.trade(R.wide(p, "pred_1h"), R.wide(p, "open_next"), 12, theta, COSTS["spot_taker_bnb"], K=K)
    tr["tag"] = tag
    return tr


def one_min(sym_fd):
    try:
        return sym_fd, v.fetch("spot", "klines", sym_fd, date(2025, 7, 1), date(2026, 11, 24), "1m", workers=4)
    except Exception:
        return sym_fd, pd.DataFrame()


def simulate(tr, wait=5, hold=60, wait_out=10):
    fd = {u["fut"]: u["spot"][:-4] + "FDUSD" for u in P.UNIVERSE}
    need = sorted({fd[s] for s in tr["sym"].unique()})
    with ThreadPoolExecutor(4) as ex:
        m1 = dict(ex.map(one_min, need))
    rows = []
    for _, t in tr.iterrows():
        k = m1.get(fd[t.sym])
        T0 = t.t_in + pd.Timedelta(minutes=5)            # signal candle closes here
        row = {"t_in": t.t_in, "sym": t.sym, "tag": t.tag, "taker_usdt": t.ret, "status": "no_pair"}
        if k is not None and len(k):
            past = k.loc[T0 - pd.Timedelta(minutes=5):T0 - pd.Timedelta(minutes=1)]
            fut = k.loc[T0:T0 + pd.Timedelta(minutes=wait - 1)]
            if len(past) < 3 or past["volume"].sum() == 0:
                row["status"] = "stale"
            else:
                limit = past["close"].iloc[-1]
                hit = fut["low"] < limit
                if not hit.any():
                    row["status"] = "not_filled"
                else:
                    t_fill = hit.idxmax()
                    t_x = t_fill + pd.Timedelta(minutes=hold)
                    kx = k.loc[t_x - pd.Timedelta(minutes=3):t_x + pd.Timedelta(minutes=wait_out)]
                    pre = kx.loc[:t_x - pd.Timedelta(minutes=1)]
                    post = kx.loc[t_x:]
                    if not len(pre) or not len(post):
                        row["status"] = "no_exit_data"
                    else:
                        lim_s = pre["close"].iloc[-1]
                        up = post["high"] > lim_s
                        if up.any():
                            row.update(status="maker_maker", ret=lim_s / limit - 1)
                        else:
                            row.update(status="maker_taker", ret=post["close"].iloc[-1] / limit - 1 - TAKER)
        rows.append(row)
    return pd.DataFrame(rows)


def show(d, name):
    f = d[d["status"].isin(["maker_maker", "maker_taker"])]
    by = lambda x: (lambda g: g.mean() / g.std() * np.sqrt(len(g)))(x.groupby(d.loc[x.index, "t_in"].dt.date).mean())
    print(f"\n{name}: {len(d)} signals | status: {d['status'].value_counts().to_dict()}")
    print(f"  taker on USDT pair, all signals : avg {d['taker_usdt'].mean()*1e4:6.1f} bps  t_by_day {by(d['taker_usdt']):.2f}")
    if len(f) > 10:
        print(f"  taker on USDT, same filled ones : avg {f['taker_usdt'].mean()*1e4:6.1f} bps")
        print(f"  maker on FDUSD pair (filled)    : avg {f['ret'].mean()*1e4:6.1f} bps  win {100*(f['ret']>0).mean():.0f}%  t_by_day {by(f['ret']):.2f}  n={len(f)} days={f['t_in'].dt.date.nunique()}")
        print(f"  sum of trade returns: maker {f['ret'].sum()*100:.1f}%  vs taker(all signals) {d['taker_usdt'].sum()*100:.1f}%")


if __name__ == "__main__":
    for tag in ("research", "holdout"):
        d = simulate(signals(tag))
        d.to_csv(DS.OUT.parent / f"maker_{tag}.csv", index=False)
        show(d, tag)
