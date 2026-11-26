"""Simple, transparent rules suggested by Kenui, tested with the same costs and the same
research / locked-period split (the locked period was already opened once, so treat it as a second look).

A) Liquidation-exhaustion rebound: sharp 1h drop + abnormal volume (+ optional negative funding /
   open-interest wipe-out) -> buy, hold 1h or 4h.
B) Opening range breakout at the New York open (09:30 ET): range = first 30 min; buy the first
   5-min close above the range high before 12:00; stop = close below range low; exit 16:00 ET.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from research import dataset as DS, panel as P

COST_RT = 2 * (0.00075 + 0.0003)
SPLIT = pd.Timestamp("2026-07-01", tz="UTC")


def summ(r: pd.Series, t: pd.Series, name: str) -> dict:
    out = {"rule": name}
    for lab, m in (("research", t < SPLIT), ("locked", t >= SPLIT)):
        x = r[m]
        if len(x) < 5:
            out.update({f"{lab}_n": len(x)})
            continue
        d = x.groupby(t[m].dt.date).mean()
        out.update({f"{lab}_n": len(x), f"{lab}_days": len(d), f"{lab}_avg_net_bps": round(x.mean() * 1e4, 1),
                    f"{lab}_win_%": round((x > 0).mean() * 100), f"{lab}_t": round(d.mean() / d.std() * np.sqrt(len(d)), 2) if len(d) > 2 else np.nan})
    return out


def liquidation():
    cols = ["sym", "ret_1h_voladj", "ret_15m", "vol_1d", "vol_surge", "funding", "liq_long_1h", "doi_1h_z", "fwd_1h", "fwd_4h"]
    d = pd.read_parquet(DS.OUT, columns=cols).reset_index()
    rows = []
    specs = {
        "drop>3s + vol>2": (d.ret_1h_voladj < -3) & (d.vol_surge > 2),
        "drop>3s + vol>2 + funding<0": (d.ret_1h_voladj < -3) & (d.vol_surge > 2) & (d.funding < 0),
        "drop>3s + vol>2 + OI wiped (z<-2)": (d.ret_1h_voladj < -3) & (d.vol_surge > 2) & (d.doi_1h_z < -2),
        "drop>5s + vol>3": (d.ret_1h_voladj < -5) & (d.vol_surge > 3),
        "drop>5s + vol>3 + OI wiped (z<-2)": (d.ret_1h_voladj < -5) & (d.vol_surge > 3) & (d.doi_1h_z < -2),
    }
    for name, mask in specs.items():
        ev = d[mask].copy()
        # one trade per coin per hour (no stacking)
        ev = ev[ev.groupby("sym", observed=True)["time"].diff().fillna(pd.Timedelta(days=1)) > pd.Timedelta(hours=1)]
        for h in ("fwd_1h", "fwd_4h"):
            rows.append(summ(ev[h] - COST_RT, ev["time"], f"A {name} | hold {h[4:]}"))
    return rows


def orb():
    res = []
    for s, df in P.load_all().items():
        if len(df) < 60 * 288:
            continue
        df = df.loc["2025-01-01":, ["open", "high", "low", "close"]].dropna()
        ny = df.index.tz_convert("America/New_York")
        mins = ny.hour * 60 + ny.minute
        day = ny.date
        g = pd.DataFrame({"o": df["open"].values, "h": df["high"].values, "l": df["low"].values, "c": df["close"].values,
                          "m": mins, "d": day, "wd": ny.dayofweek, "t": df.index})
        g = g[(g.wd < 5) & (g.m >= 570) & (g.m <= 960)]
        for dkey, x in g.groupby("d"):
            rng = x[x.m < 600]
            if len(rng) < 6:
                continue
            hi, lo = rng.h.max(), rng.l.min()
            win = x[(x.m >= 600)].reset_index(drop=True)
            brk = win[(win.m < 720) & (win.c > hi)]
            if not len(brk) or brk.index[0] + 1 >= len(win):
                continue
            i = brk.index[0] + 1
            entry = win.o[i]
            after = win.iloc[i:]
            stop = after[after.c < lo]
            last = after[after.m == 960]
            j = stop.index[0] + 1 if len(stop) and stop.index[0] + 1 < len(win) else None
            exit_px = win.o[j] if j is not None else (last.o.iloc[0] if len(last) else after.c.iloc[-1])
            res.append({"t": win.t[i], "sym": s, "ret": exit_px / entry - 1 - COST_RT})
    r = pd.DataFrame(res)
    return [summ(r["ret"], r["t"], "B NY opening-range breakout (all 39 coins)"),
            summ(r[r.sym.isin(["BTCUSDT", "ETHUSDT", "SOLUSDT"])]["ret"], r[r.sym.isin(["BTCUSDT", "ETHUSDT", "SOLUSDT"])]["t"], "B NY opening-range breakout (BTC, ETH, SOL)")]


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    rep = pd.DataFrame(liquidation() + orb())
    rep.to_csv(DS.OUT.parent / "ideas_report.csv", index=False)
    print(rep.to_string(index=False))
