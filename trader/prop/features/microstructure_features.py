"""Microstructure features and vetoes (V4): Amihud illiquidity, VPIN proxy, spread-spike proxy."""
from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_pct_rank(s: pd.Series, n: int) -> pd.Series:
    """Percentile (0-1) of the current value inside its last n values."""
    return s.rolling(n).rank(pct=True)


def amihud(df: pd.DataFrame, n: int = 100) -> pd.DataFrame:
    """|return| per unit of volume and its rolling percentile: high = thin book."""
    illiq = np.log(df["close"]).diff().abs() / df["volume"].replace(0, np.nan)
    return pd.DataFrame({"amihud": np.log1p(illiq / illiq.rolling(n).median()),
                         "amihud_pct": rolling_pct_rank(illiq, n)})


def vpin_proxy(df: pd.DataFrame, n: int = 50) -> pd.DataFrame:
    """Order-flow toxicity proxy. Buy share of each bar's volume = (close-low)/(high-low);
    VPIN = sum|buy - sell| / sum(volume) over n bars."""
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    buy_frac = ((df["close"] - df["low"]) / rng).fillna(0.5)
    imbalance = (2 * buy_frac - 1).abs() * df["volume"]
    vpin = imbalance.rolling(n).sum() / df["volume"].rolling(n).sum()
    return pd.DataFrame({"vpin": vpin, "vpin_pct": rolling_pct_rank(vpin, 500),
                         "flow_signed": ((2 * buy_frac - 1) * df["volume"]).rolling(n).sum()
                         / df["volume"].rolling(n).sum()})


def spread_spike(df: pd.DataFrame, n: int = 48) -> pd.Series:
    """Simulated spread stress: bar range over its moving average (spreads widen with range)."""
    rng = df["high"] - df["low"]
    return rng / rng.rolling(n).mean()


def micro_features(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.concat([amihud(df), vpin_proxy(df)], axis=1)
    out["spread_spike"] = spread_spike(df)
    return out.replace([np.inf, -np.inf], np.nan)
