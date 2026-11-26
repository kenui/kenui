"""The post-listing short as an alpha source for the V5 controller and Monte Carlo.

The V5 machinery (Bellman sizing, harvest solver, full-journey Monte Carlo, DSR, PBO) does not
care where the trades come from. This module converts the listing-short trades to the same
`Trades` container and builds the grid of rule variants (wait x hold x stop) for the
overfitting statistics.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from prop.backtest import engine
from prop.backtest.selection import Trades, to_trades
from prop.config.settings import SETTINGS, RiskConfig

CSV = Path("prop/output/listing_short_trades.csv")


def add_funding(t: pd.DataFrame) -> pd.DataFrame:
    """Funding actually paid or received by the short while it was open, in R (stop = 30%)."""
    from kenui_trader import vision as v
    from prop.candidates.listing_short import STOP
    from research.listings_short import load
    ev = pd.read_csv("data/listings_events.csv", parse_dates=["listed"])
    ev = ev[ev["symbol"].isin(t["symbol"])]
    futs = set(v.symbols("futures/um"))
    with ThreadPoolExecutor(8) as ex:
        fund = {x[0]: x[2] for x in ex.map(lambda r: load(r, futs), [r for _, r in ev.iterrows()]) if x}
    out = []
    for _, row in t.iterrows():
        fr = fund.get(row["symbol"])
        got = fr.loc[row["entry_time"]:row["exit_time"], "last_funding_rate"].sum() if fr is not None and len(fr) else 0.0
        out.append(float(got) / STOP)
    return t.assign(funding_r=out)


def trade_table() -> pd.DataFrame:
    """Backtest trades of the rule. Column `r` excludes funding; `funding_r` is added to it by `trades`."""
    if not CSV.exists():
        from prop.candidates.listing_short import build
        bars, sigs, inst = build()
        res = engine.run(bars, sigs, RiskConfig.plain(0.01), SETTINGS.rules, inst)
        CSV.parent.mkdir(parents=True, exist_ok=True)
        res.trades.to_csv(CSV, index=False)
    t = pd.read_csv(CSV, parse_dates=["entry_time", "exit_time"])
    if "funding_r" not in t.columns:
        t = add_funding(t)
        t.to_csv(CSV, index=False)
    return t


def net_r(t: pd.DataFrame) -> np.ndarray:
    return (t["r"] + t["funding_r"]).to_numpy(float)


def trades(edge_haircut: float = 0.0, table: pd.DataFrame | None = None) -> Trades:
    """`edge_haircut` (0 to 1) removes that share of the measured average result from every
    trade: a stress test for an edge that decays or was partly luck."""
    t = trade_table() if table is None else table
    r = net_r(t)
    r = r - edge_haircut * r.mean()
    df = pd.DataFrame({"entry_time": t["entry_time"], "exit_time": t["exit_time"], "asset": t["symbol"],
                       "arm": "arm1", "arm_i": 2, "mult": 1.0, "p": 0.6, "score": 1.0, "y": (r > 0).astype(int),
                       "kind": 3})
    for k in ("plain", "arm0", "arm1", "arm2"):
        df[f"r_{k}"], df[f"mae_{k}"] = r, np.minimum(t["mae_r"].to_numpy(float), r)
    return to_trades(df)


def variant_matrix() -> pd.DataFrame:
    """Net return of every rule variant for every listing (rows in listing order)."""
    from kenui_trader import vision as v
    from research.listings_short import load, trade
    ev = pd.read_csv("data/listings_events.csv", parse_dates=["listed"]).sort_values("listed")
    futs = set(v.symbols("futures/um"))
    with ThreadPoolExecutor(8) as ex:
        loaded = {x[0]: x for x in ex.map(lambda r: load(r, futs), [r for _, r in ev.iterrows()]) if x}
    rows = {}
    for _, e in ev.iterrows():
        if e["symbol"] not in loaded:
            continue
        _, k, fr = loaded[e["symbol"]]
        row = {}
        for wait_h in (1, 24, 72):
            for hold_d in (1, 3, 7, 14):
                for stop in (None, 0.15, 0.30):
                    out = trade(k, fr, e["listed"] + pd.Timedelta(hours=wait_h), hold_d * 24, stop)
                    row[f"w{wait_h}_h{hold_d}_s{stop}"] = out[0] if out else np.nan
        rows[e["symbol"]] = row
    return pd.DataFrame.from_dict(rows, orient="index")


