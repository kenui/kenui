"""Download every dataset for the universe and merge into one 5-minute table per coin.

Alignment rule (no look-ahead): row t = candle that OPENS at t and closes at t+5m.
Everything in the row is known by t+5m. Trades decided on row t execute on row t+1.
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from kenui_trader import vision as v

START, END = date(2024, 12, 1), date(2026, 11, 24)
HERE = Path(__file__).resolve().parent
PANEL = HERE.parent / "data" / "panel"
UNIVERSE = json.loads((HERE / "universe.json").read_text())


def merge(u: dict, s, f, p, fr, m, funding_time_col: bool = False):
    """Join raw spot/futures/premium/funding/metrics frames into the 5-minute panel format.
    Used by both the historical panel and the live bot, so both see identical columns."""
    if s.empty or f.empty:
        return None
    idx = pd.date_range(s.index[0], s.index[-1], freq="5min")
    df = pd.DataFrame(index=idx)
    df.index.name = "time"
    for c in ["open", "high", "low", "close"]:
        df[c] = s[c].reindex(idx)
    df["traded"] = s["volume"].reindex(idx).fillna(0) > 0
    df["qvol"] = s["quote_volume"].reindex(idx).fillna(0)
    df["trades"] = s["trades"].reindex(idx).fillna(0)
    df["tbuy_q"] = s["taker_buy_quote"].reindex(idx).fillna(0)
    k = u["mult"]
    for c in ["open", "high", "low", "close"]:
        df["f_" + c] = f[c].reindex(idx) / k
    df["f_qvol"] = f["quote_volume"].reindex(idx).fillna(0)
    df["f_tbuy_q"] = f["taker_buy_quote"].reindex(idx).fillna(0)
    df["f_trades"] = f["trades"].reindex(idx).fillna(0)
    if len(p):
        df["prem"] = p["close"].reindex(idx)
    else:
        df["prem"] = np.nan
    if len(fr):
        # funding stamped at T is paid at T; known from T on
        fr2 = fr.copy()
        fr2.index = fr2.index.floor("5min")
        fr2 = fr2[~fr2.index.duplicated()]
        df["funding_paid"] = fr2["last_funding_rate"].reindex(idx)          # non-NaN only on payment bars (bar opening at T)
        df["funding_last"] = df["funding_paid"].ffill()
        df["funding_ih"] = fr2["funding_interval_hours"].reindex(idx).ffill()
    else:
        df["funding_paid"] = df["funding_last"] = df["funding_ih"] = np.nan
    if len(m):
        # snapshot taken at T is known at the close of the candle that opened at T-5m
        m2 = m.copy()
        m2.index = m2.index - pd.Timedelta(minutes=5)
        ren = {"sum_open_interest": "oi", "sum_open_interest_value": "oi_val",
               "count_toptrader_long_short_ratio": "top_acct_ls", "sum_toptrader_long_short_ratio": "top_pos_ls",
               "count_long_short_ratio": "acct_ls", "sum_taker_long_short_vol_ratio": "f_taker_ls"}
        for a, b in ren.items():
            df[b] = m2[a].reindex(idx) if a in m2 else np.nan
        df["oi"] = df["oi"] / k
    df = df.astype({c: "float32" for c in df.columns if c not in ("traded", "open", "high", "low", "close",
                                                                 "f_open", "f_high", "f_low", "f_close")})
    return df


def build(u: dict) -> str:
    out = PANEL / f"{u['fut']}.parquet"
    if out.exists():
        return f"{u['fut']} cached"
    s = v.fetch("spot", "klines", u["spot"], START, END, "5m")
    f = v.fetch("futures/um", "klines", u["fut"], START, END, "5m")
    p = v.fetch("futures/um", "premiumIndexKlines", u["fut"], START, END, "5m")
    fr = v.fetch("futures/um", "fundingRate", u["fut"], START, END)
    m = v.fetch("futures/um", "metrics", u["fut"], START, END)
    df = merge(u, s, f, p, fr, m)
    if df is None:
        return f"{u['fut']} EMPTY"
    PANEL.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out)
    return f"{u['fut']} {len(df)} rows {df.index[0]:%Y-%m-%d}->{df.index[-1]:%Y-%m-%d} oi_nan={df['oi'].isna().mean():.3f} prem_nan={df['prem'].isna().mean():.3f}"


def load(sym: str) -> pd.DataFrame:
    return pd.read_parquet(PANEL / f"{sym}.parquet")


def load_all() -> dict[str, pd.DataFrame]:
    return {u["fut"]: load(u["fut"]) for u in UNIVERSE if (PANEL / f"{u['fut']}.parquet").exists()}


if __name__ == "__main__":
    with ProcessPoolExecutor(6) as ex:
        for msg in ex.map(build, UNIVERSE):
            print(msg, flush=True)
