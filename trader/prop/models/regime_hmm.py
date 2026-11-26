"""Regime detector: Gaussian Hidden Markov Model with 3 hidden states.

Fitted only on the training window. Probabilities are FILTERED (forward algorithm): the
probability at bar t uses observations up to t only. `predict_proba` of hmmlearn smooths with
future bars, which would leak inside the test window, so it is not used.
States are ordered by volatility: 0 = compression/range, 1 = clean trend, 2 = volatility shock.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM
from scipy.special import logsumexp

STATES = ("p_compress", "p_trend", "p_shock")


def observations(df: pd.DataFrame) -> pd.DataFrame:
    """Return and realised volatility, the two series the HMM sees."""
    r = np.log(df["close"]).diff()
    vol = np.log(r.rolling(12).std().replace(0, np.nan))
    return pd.DataFrame({"ret": r, "abs_ret_12": r.rolling(12).sum().abs(), "log_vol": vol}).dropna()


class RegimeHMM:
    def __init__(self, n_states: int = 3, seed: int = 0) -> None:
        self.n_states, self.seed = n_states, seed
        self.model: GaussianHMM | None = None
        self.mu: np.ndarray | None = None
        self.sd: np.ndarray | None = None
        self.order: np.ndarray | None = None

    def fit(self, obs: pd.DataFrame, lengths: list[int] | None = None) -> "RegimeHMM":
        """`lengths` splits `obs` into separate sequences when the training bars are not contiguous."""
        x = obs.to_numpy(float)
        self.mu, self.sd = x.mean(axis=0), x.std(axis=0) + 1e-12
        z = (x - self.mu) / self.sd
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.model = GaussianHMM(self.n_states, covariance_type="diag", n_iter=60, tol=1e-3,
                                     random_state=self.seed).fit(z, lengths)
        self.order = np.argsort(self.model.means_[:, obs.columns.get_loc("log_vol")])
        return self

    def filtered(self, obs: pd.DataFrame) -> pd.DataFrame:
        """P(state at t | observations up to t), columns ordered compress/trend/shock."""
        assert self.model is not None
        z = (obs.to_numpy(float) - self.mu) / self.sd
        log_b = self.model._compute_log_likelihood(z)
        log_a = np.log(self.model.transmat_ + 1e-300)
        alpha = np.log(self.model.startprob_ + 1e-300) + log_b[0]
        out = np.empty_like(log_b)
        out[0] = alpha - logsumexp(alpha)
        for t in range(1, len(z)):
            alpha = logsumexp(out[t - 1][:, None] + log_a, axis=0) + log_b[t]
            out[t] = alpha - logsumexp(alpha)
        return pd.DataFrame(np.exp(out)[:, self.order], index=obs.index, columns=list(STATES))
