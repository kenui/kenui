"""Signals ("features") built from flow, futures and cross-market data.

Every feature on row t uses only information available at the close of candle t.
Open interest / long-short ratios get one extra candle of delay, because Binance
publishes them a few minutes late.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

D = 288  # 5-minute candles per day
HORIZONS = {"5m": 1, "15m": 3, "1h": 12, "4h": 48, "24h": 288}


def _z(x: pd.Series, win: int = 7 * D) -> pd.Series:
    r = x.rolling(win, min_periods=win // 4)
    return ((x - r.mean()) / r.std().replace(0, np.nan)).clip(-10, 10)


def _imb(buy: pd.Series, tot: pd.Series, n: int) -> pd.Series:
    b, t = buy.rolling(n).sum(), tot.rolling(n).sum()
    return ((2 * b - t) / t.replace(0, np.nan)).fillna(0)


def make(df: pd.DataFrame, btc: pd.DataFrame | None = None) -> pd.DataFrame:
    c = df["close"].ffill()
    lr = np.log(c).diff()
    X = pd.DataFrame(index=df.index)

    # --- price: momentum / reversal / volatility
    for name, n in [("5m", 1), ("15m", 3), ("1h", 12), ("4h", 48), ("24h", 288), ("7d", 2016)]:
        X[f"ret_{name}"] = np.log(c).diff(n)
    vol_1h = lr.rolling(12).std()
    vol_1d = lr.rolling(D).std()
    X["vol_1d"] = vol_1d
    X["vol_ratio"] = vol_1h / vol_1d
    hi, lo = df["high"].rolling(D).max(), df["low"].rolling(D).min()
    X["range_pos_1d"] = (c - lo) / (hi - lo).replace(0, np.nan)
    X["ret_1h_voladj"] = X["ret_1h"] / (vol_1d * np.sqrt(12))
    X["wick"] = ((df["high"] - df[["open", "close"]].max(axis=1)) - (df[["open", "close"]].min(axis=1) - df["low"])) / c

    # --- aggressive flow (who is crossing the spread), spot and futures
    for name, n in [("5m", 1), ("15m", 3), ("1h", 12), ("4h", 48), ("24h", 288)]:
        X[f"flow_s_{name}"] = _imb(df["tbuy_q"], df["qvol"], n)
        X[f"flow_f_{name}"] = _imb(df["f_tbuy_q"], df["f_qvol"], n)
    X["flow_s_z"] = _z(X["flow_s_1h"])
    X["flow_f_z"] = _z(X["flow_f_1h"])
    X["flow_sf_gap_1h"] = X["flow_s_1h"] - X["flow_f_1h"]          # spot buyers vs futures buyers
    # flow/price divergence: lots of buying but price not rising (absorption) and vice versa
    X["absorb_1h"] = _z(X["flow_s_1h"]) - _z(X["ret_1h"])
    X["absorb_4h"] = _z(X["flow_s_4h"]) - _z(X["ret_4h"])
    lv = np.log1p(df["qvol"])
    X["vol_surge"] = _z(lv.rolling(3).mean())
    X["vol_surge_signed"] = X["vol_surge"] * np.sign(X["ret_15m"])
    X["trade_size"] = _z(np.log((df["qvol"] / df["trades"].replace(0, np.nan)).rolling(12).mean()))
    X["fut_spot_volratio"] = _z(np.log((df["f_qvol"].rolling(12).sum() + 1) / (df["qvol"].rolling(12).sum() + 1)))

    # --- basis / premium / funding
    prem = df["prem"].ffill(limit=3)
    X["prem"] = prem
    X["prem_z"] = _z(prem, D)
    X["prem_chg_1h"] = prem - prem.shift(12)
    X["prem_1h_avg"] = prem.rolling(12).mean()
    X["funding"] = df["funding_last"]
    X["funding_z"] = _z(df["funding_last"], 30 * D)
    X["fs_gap"] = (df["f_close"] / df["close"] - 1).ffill(limit=3)   # last futures trade vs last spot trade
    X["fs_lead_5m"] = np.log(df["f_close"].ffill()).diff() - lr       # futures moved more than spot this candle

    # --- open interest and positioning (delayed one extra candle)
    lag = 1
    oi = np.log(df["oi"].replace(0, np.nan)).ffill(limit=3).shift(lag)
    for name, n in [("15m", 3), ("1h", 12), ("4h", 48), ("24h", 288)]:
        X[f"doi_{name}"] = oi.diff(n)
    X["doi_1h_z"] = _z(X["doi_1h"])
    X["doi_15m_z"] = _z(X["doi_15m"])
    # liquidation proxies: positions vanish while price moves hard
    X["liq_long"] = (-X["doi_15m_z"]).clip(lower=0) * (-X["ret_15m"] / (vol_1d * np.sqrt(3))).clip(lower=0)
    X["liq_short"] = (-X["doi_15m_z"]).clip(lower=0) * (X["ret_15m"] / (vol_1d * np.sqrt(3))).clip(lower=0)
    X["liq_long_1h"] = (-X["doi_1h_z"]).clip(lower=0) * (-X["ret_1h_voladj"]).clip(lower=0)
    X["liq_short_1h"] = (-X["doi_1h_z"]).clip(lower=0) * (X["ret_1h_voladj"]).clip(lower=0)
    # new money entering in the direction of the move (fresh leverage)
    X["oi_up_price_up"] = X["doi_1h_z"].clip(lower=0) * X["ret_1h_voladj"].clip(lower=0)
    X["oi_up_price_dn"] = X["doi_1h_z"].clip(lower=0) * (-X["ret_1h_voladj"]).clip(lower=0)
    X["oi_per_vol"] = _z(np.log(df["oi_val"].replace(0, np.nan)).shift(lag) - np.log(df["f_qvol"].rolling(D).sum() + 1))
    for col in ["top_pos_ls", "top_acct_ls", "acct_ls"]:
        s = np.log(df[col].replace(0, np.nan)).ffill(limit=3).shift(lag)
        X[f"{col}_z"] = _z(s)
        X[f"{col}_chg_4h"] = s.diff(48)
    X["smart_vs_crowd"] = X["top_pos_ls_z"] - X["acct_ls_z"]

    # --- market leader: does BTC move first?
    if btc is not None:
        bc = btc["close"].reindex(df.index).ffill()
        blr = np.log(bc).diff()
        X["btc_ret_5m"] = blr
        X["btc_ret_15m"] = np.log(bc).diff(3)
        X["btc_ret_1h"] = np.log(bc).diff(12)
        cov = (lr * blr).rolling(7 * D).mean() - lr.rolling(7 * D).mean() * blr.rolling(7 * D).mean()
        beta = (cov / blr.rolling(7 * D).var()).clip(0, 4)
        X["beta"] = beta
        for name, n in [("15m", 3), ("1h", 12), ("4h", 48), ("24h", 288)]:
            X[f"resid_{name}"] = np.log(c).diff(n) - beta * np.log(bc).diff(n)   # move not explained by BTC
        X["btc_gap_5m"] = beta * blr - lr                                         # BTC moved, coin has not yet

    # --- clock
    h = df.index.hour + df.index.minute / 60
    X["hour_sin"], X["hour_cos"] = np.sin(2 * np.pi * h / 24), np.cos(2 * np.pi * h / 24)
    X["dow"] = df.index.dayofweek
    X["to_funding"] = (8 - (h % 8)) % 8
    return X.astype("float32")


def forward_returns(df: pd.DataFrame, col: str = "open") -> pd.DataFrame:
    """Return from the OPEN of the next candle to the open h candles later (what a trade could capture)."""
    o = df[col].ffill()
    Y = pd.DataFrame(index=df.index)
    for name, h in HORIZONS.items():
        Y[f"fwd_{name}"] = o.shift(-1 - h) / o.shift(-1) - 1
    return Y.astype("float32")
