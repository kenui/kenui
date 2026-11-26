"""Can the post-listing drop be traded? Short the perpetual N hours after the spot listing.

Includes: taker fees both sides, slippage, funding actually paid/received, and a stop-loss
(a short has unlimited loss, so a stop is mandatory). Reported by half-year to see decay.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta, date

import numpy as np
import pandas as pd

from kenui_trader import vision as v

COST = 0.00045 + 0.0010     # per side: taker with BNB + generous slippage (new coins have wide spreads)


def load(ev, futs):
    s = ev["symbol"]
    f = s if s in futs else ("1000" + s if "1000" + s in futs else None)
    if f is None:
        return None
    d0 = ev["listed"].date()
    try:
        k = v.fetch("futures/um", "klines", f, d0, min(d0 + timedelta(days=45), date(2026, 11, 24)), "1h", workers=4)
        fr = v.fetch("futures/um", "fundingRate", f, d0.replace(day=1), min(d0 + timedelta(days=45), date(2026, 11, 24)), workers=2)
    except Exception:
        return None
    return s, k, fr


def trade(k, fr, t_in, hold_h, stop):
    k = k.loc[t_in:]
    if len(k) < hold_h + 1:
        return None
    entry = k["open"].iloc[0]
    win = k.iloc[:hold_h]
    hit = win["high"] >= entry * (1 + stop) if stop else pd.Series(False, index=win.index)
    if hit.any():
        t_out = hit.idxmax()
        px = max(entry * (1 + stop), win.loc[t_out, "open"])
    else:
        t_out = win.index[-1]
        px = win["close"].iloc[-1]
    fund = fr.loc[t_in:t_out, "last_funding_rate"].sum() if len(fr) else 0.0   # short receives positive funding
    return -(px / entry - 1) - 2 * COST + fund, fund, bool(hit.any())


def main():
    ev = pd.read_csv("data/listings_events.csv", parse_dates=["listed"])
    futs = set(v.symbols("futures/um"))
    with ThreadPoolExecutor(8) as ex:
        loaded = [x for x in ex.map(lambda r: load(r, futs), [r for _, r in ev.iterrows()]) if x]
    L = dict(zip(ev["symbol"], ev["listed"]))
    print(len(ev), "listings;", len(loaded), "with a perpetual")
    rows = []
    for wait_h in (1, 24, 72):
        for hold_d in (1, 3, 7, 14):
            for stop in (None, 0.15, 0.30):
                res = []
                for s, k, fr in loaded:
                    t_in = L[s] + pd.Timedelta(hours=wait_h)
                    if len(k) == 0 or k.index[0] > t_in:      # perp not trading yet at entry time
                        continue
                    r = trade(k, fr, t_in, hold_d * 24, stop)
                    if r:
                        res.append({"symbol": s, "t": t_in, "ret": r[0], "fund": r[1], "stopped": r[2]})
                d = pd.DataFrame(res)
                if len(d) < 30:
                    continue
                half = d.groupby(d["t"].dt.year.astype(str) + "H" + ((d["t"].dt.month > 6) + 1).astype(str))["ret"].mean()
                rows.append({"wait_h": wait_h, "hold_d": hold_d, "stop": stop, "n": len(d),
                             "mean_%": d["ret"].mean() * 100, "median_%": d["ret"].median() * 100,
                             "win_%": (d["ret"] > 0).mean() * 100, "worst_%": d["ret"].min() * 100,
                             "fund_mean_%": d["fund"].mean() * 100, "stopped_%": d["stopped"].mean() * 100,
                             "t": d["ret"].mean() / d["ret"].std() * np.sqrt(len(d)),
                             **{h: round(x * 100, 1) for h, x in half.items()}})
                if (wait_h, hold_d, stop) == (24, 7, 0.30):
                    d.to_csv("data/listings_short_24h_7d.csv", index=False)
    pd.set_option("display.width", 250)
    print(pd.DataFrame(rows).round(2).to_string(index=False))


if __name__ == "__main__":
    main()
