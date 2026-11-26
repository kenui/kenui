"""Hierarchical Risk Parity (Lopez de Prado) and the Absorption Ratio (Kritzman et al.)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.spatial.distance import squareform

from prop.config.quant import Q


def _cluster_var(cov: np.ndarray, items: list[int]) -> float:
    sub = cov[np.ix_(items, items)]
    ivp = 1.0 / np.diag(sub)
    ivp /= ivp.sum()
    return float(ivp @ sub @ ivp)


def hrp_weights(returns: pd.DataFrame) -> pd.Series:
    """Risk-budget weights: tree clustering on correlation distance, quasi-diagonalisation,
    then recursive bisection giving each half a share inversely proportional to its variance."""
    cov, corr = returns.cov().to_numpy(), returns.corr().fillna(0).to_numpy()
    n = len(cov)
    if n == 1:
        return pd.Series(1.0, index=returns.columns)
    dist = np.sqrt(np.clip((1 - corr) / 2, 0, 1))
    np.fill_diagonal(dist, 0.0)
    order = list(leaves_list(linkage(squareform(dist, checks=False), method="single")))
    w = np.ones(n)
    clusters = [order]
    while clusters:
        nxt = []
        for cl in clusters:
            if len(cl) < 2:
                continue
            left, right = cl[:len(cl) // 2], cl[len(cl) // 2:]
            vl, vr = _cluster_var(cov, left), _cluster_var(cov, right)
            alpha = 1 - vl / (vl + vr)
            w[left] *= alpha
            w[right] *= 1 - alpha
            nxt += [left, right]
        clusters = nxt
    return pd.Series(w / w.sum(), index=returns.columns)


def risk_multipliers(returns: pd.DataFrame, lo: float = 0.5, hi: float = 1.5) -> pd.Series:
    """HRP weights are in capital; risk is already equalised by the ATR stop, so only the
    correlation structure matters: weights of the volatility-standardised returns."""
    z = returns / returns.std().replace(0, np.nan)
    w = hrp_weights(z.fillna(0.0))
    return (w * len(w)).clip(lo, hi)


def absorption_ratio(returns: pd.DataFrame, window: int = 200) -> pd.Series:
    """Share of variance explained by the first eigenvector of the rolling correlation matrix."""
    x = returns.to_numpy(float)
    out = np.full(len(x), np.nan)
    for t in range(window, len(x) + 1, 6):  # refreshed every 6 bars, held in between
        c = np.corrcoef(x[t - window:t], rowvar=False)
        if np.isfinite(c).all():
            ev = np.linalg.eigvalsh(c)
            out[t - 1] = ev[-1] / ev.sum()
    return pd.Series(out, index=returns.index).ffill()


def systemic_scale(ar: pd.Series, limit: float = Q.absorption_limit, max_cut: float = 0.5) -> pd.Series:
    """1.0 below the limit, falling linearly to 1 - max_cut when the ratio reaches 1."""
    return (1 - max_cut * ((ar - limit) / (1 - limit)).clip(0, 1)).fillna(1.0)
