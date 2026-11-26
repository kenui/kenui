"""Event study: what happens to a coin after it is listed on Binance spot?

Listing date = first hourly candle in Binance's public archive. For each new USDT pair
listed from 2023 on, measure the return from several entry points to several exits,
and compare with BTC over the same hours.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import numpy as np
import pandas as pd

from kenui_trader import vision as v

SKIP = ("UP", "DOWN", "BULL", "BEAR")
STABLE = {"USDC", "FDUSD", "TUSD", "USDP", "DAI", "EUR", "USD1", "RLUSD", "AEUR", "EURI", "XUSD", "BFUSD", "USDE", "PYUSD", "U"}


def first_month(sym):
    keys = v.s3_list(f"data/spot/monthly/klines/{sym}/1d/", dirs=False)
    ms = sorted(k.split("-1d-")[1][:7] for k in keys if k.endswith(".zip"))
    return sym, (ms[0] if ms else None)


def hourly(sym, start: date):
    end = min(start + timedelta(days=75), date(2026, 11, 24))
    return v.fetch("spot", "klines", sym, start, end, "1h", workers=4)


def main():
    syms = [s for s in v.symbols("spot") if s.endswith("USDT") and s[:-4] not in STABLE
            and not any(s[:-4].endswith(k) for k in SKIP)]
    with ThreadPoolExecutor(32) as ex:
        fm = dict(ex.map(first_month, syms))
    new = {s: m for s, m in fm.items() if m and "2023-01" <= m <= "2026-09"}
    print(len(syms), "USDT pairs;", len(new), "listed 2023-01..2026-09")
    btc = v.fetch("spot", "klines", "BTCUSDT", date(2023, 1, 1), date(2026, 11, 24), "1h")["close"]
    rows = []

    def one(item):
        s, m = item
        y, mo = map(int, m.split("-"))
        try:
            return s, hourly(s, date(y, mo, 1))
        except Exception as e:
            return s, None

    with ThreadPoolExecutor(8) as ex:
        for s, df in ex.map(one, new.items()):
            if df is None or len(df) < 24 * 35:
                continue
            c = df["close"]
            t0 = c.index[0]
            if t0.day == 1 and t0.hour == 0:      # archive starts exactly at month start: not a real listing (relist/migration)
                continue
            b = btc.reindex(c.index).ffill()
            row = {"symbol": s, "listed": t0, "first_hour_ret": c.iloc[0] / df["open"].iloc[0] - 1}
            for ename, e in [("1h", 0), ("24h", 23), ("72h", 71)]:
                for xname, x in [("+1d", 24), ("+3d", 72), ("+7d", 168), ("+30d", 720)]:
                    if e + x < len(c):
                        row[f"in{ename}{xname}"] = c.iloc[e + x] / c.iloc[e] - 1
                        row[f"in{ename}{xname}_vsBTC"] = row[f"in{ename}{xname}"] - (b.iloc[e + x] / b.iloc[e] - 1)
            rows.append(row)
    rep = pd.DataFrame(rows).sort_values("listed")
    rep.to_csv("data/listings_events.csv", index=False)
    print(len(rep), "listing events")
    out = []
    for col in [c for c in rep.columns if c.startswith("in")]:
        x = rep[col].dropna()
        out.append({"trade": col, "n": len(x), "mean_%": x.mean() * 100, "median_%": x.median() * 100,
                    "win_%": (x > 0).mean() * 100, "t": x.mean() / x.std() * np.sqrt(len(x))})
    print(pd.DataFrame(out).round(2).to_string(index=False))
    for yr in (2023, 2024, 2025, 2026):
        sub = rep[rep["listed"].dt.year == yr]
        print(yr, len(sub), "events; in24h+7d_vsBTC mean %.1f%% median %.1f%%" % (
            sub["in24h+7d_vsBTC"].mean() * 100, sub["in24h+7d_vsBTC"].median() * 100))


if __name__ == "__main__":
    main()
