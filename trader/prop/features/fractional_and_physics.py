"""V5 features: fixed-width fractional differentiation, rolling Hurst exponent and the
Ornstein-Uhlenbeck half-life."""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from statsmodels.tools.sm_exceptions import InterpolationWarning  # noqa: F401
from statsmodels.tsa.stattools import adfuller

from prop.extensions.atemporal_aci import Order3PathSignatureExtractor

D_GRID = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6)


def ffd_weights(d: float, threshold: float = 1e-4, max_len: int = 500) -> np.ndarray:
    w = [1.0]
    for k in range(1, max_len):
        nxt = -w[-1] * (d - k + 1) / k
        if abs(nxt) < threshold:
            break
        w.append(nxt)
    return np.array(w[::-1])


def fracdiff_ffd(series: pd.Series, d: float, threshold: float = 1e-4) -> pd.Series:
    """Lopez de Prado's fixed-width-window fractional differentiation (causal filter)."""
    w = ffd_weights(d, threshold)
    x = series.to_numpy(float)
    out = np.full(len(x), np.nan)
    if len(x) >= len(w):
        out[len(w) - 1:] = np.convolve(x, w[::-1], mode="valid")
    return pd.Series(out, index=series.index)


def ffd_table(log_price: pd.Series) -> pd.DataFrame:
    """One column per candidate d; the order is chosen later, inside each training window."""
    return pd.DataFrame({d: fracdiff_ffd(log_price, d) for d in D_GRID})


def choose_d(table: pd.DataFrame, train_index: pd.DatetimeIndex, p_value: float = 0.05) -> float:
    """Smallest d whose series passes the ADF stationarity test on the training window only."""
    for d in D_GRID:
        x = table.loc[table.index.isin(train_index), d].dropna()
        if len(x) > 200:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                if adfuller(x.to_numpy(), maxlag=8, autolag=None)[1] < p_value:
                    return d
    return D_GRID[-1]


def hurst(log_price: pd.Series, window: int = 256, lags: tuple[int, ...] = (2, 4, 8, 16, 32)) -> pd.Series:
    """Rolling Hurst exponent from the scaling of the std of lagged differences:
    std(x[t+k] - x[t]) ~ k^H.  H > 0.5 persistent (trend), H < 0.5 anti-persistent (reverting)."""
    logk = np.log(np.array(lags, float))
    logs = np.column_stack([np.log(log_price.diff(k).rolling(window).std().to_numpy()) for k in lags])
    kc = logk - logk.mean()
    h = (logs - logs.mean(axis=1, keepdims=True)) @ kc / (kc @ kc)
    return pd.Series(h, index=log_price.index)


def ou_half_life(log_price: pd.Series, window: int = 100) -> pd.Series:
    """Half-life (in bars) of the deviation from the rolling mean, from the AR(1) regression
    dy[t] = a + b*y[t-1]. Infinite when the series is not mean-reverting (b >= 0)."""
    y = log_price - log_price.rolling(window).mean()
    lag, dy = y.shift(), y.diff()
    b = dy.rolling(window).cov(lag) / lag.rolling(window).var()
    tau = -np.log(2) / np.log1p(b.clip(lower=-0.999, upper=-1e-6))
    return tau.where(b < 0, np.inf)


def physics_features(df: pd.DataFrame) -> pd.DataFrame:
    lp = np.log(df["close"])
    tau = ou_half_life(lp)
    return pd.DataFrame({"hurst": hurst(lp), "ou_tau": tau,
                         "ou_tau_feat": np.log1p(tau.clip(upper=500).fillna(500))})


SIGNATURE = Order3PathSignatureExtractor(window=24)


def signature_features(df: pd.DataFrame) -> pd.DataFrame:
    """41 path-signature features for the meta-ensemble only (the HMM keeps seeing returns and
    volatility alone). The first 24 rows stay NaN; the models impute them with the median of
    their own training window, so nothing from the future is used."""
    return SIGNATURE.transform(df)
