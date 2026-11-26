"""Frontier extension: order-3 path signatures and Adaptive Conformal Inference (ACI).

`Order3PathSignatureExtractor` describes the SHAPE of the last `window` bars, independent of
how the path is sampled in time: the truncated signature of the 3-D path
(time, log price, cumulative volume), built segment by segment with Chen's identity.
3 + 9 + 27 signature terms plus 2 Levy areas = 41 features.

`AdaptiveConformalController` turns a predicted probability into a one-sided lower bound and
keeps adapting its miscoverage level alpha with the realised outcomes (Gibbs and Candes):
alpha <- alpha + gamma * (alpha_target - err). When the bound keeps being violated, alpha falls,
the bound gets more conservative and fewer trades are authorised.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

AXES = ("t", "p", "v")


class Order3PathSignatureExtractor:
    def __init__(self, window: int = 24) -> None:
        self.window = window
        self.columns = ([f"sig1_{a}" for a in AXES] + [f"sig2_{a}{b}" for a in AXES for b in AXES]
                        + [f"sig3_{a}{b}{c}" for a in AXES for b in AXES for c in AXES]
                        + ["levy_tp", "levy_pv"])

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """41 features per bar. The value at bar t uses bars t-window+1..t only; the first
        `window` rows are NaN (left as NaN, never back-filled)."""
        w = self.window
        dp = np.log(df["close"]).diff().to_numpy(float)
        vol = df["volume"].to_numpy(float)
        out = np.full((len(df), len(self.columns)), np.nan)
        if len(df) <= w:
            return pd.DataFrame(out, index=df.index, columns=self.columns)
        dpw = sliding_window_view(dp[1:], w)          # increments of the w segments ending at each bar
        vw = sliding_window_view(vol[1:], w)
        n = len(dpw)
        scale = dpw.std(axis=1, keepdims=True) * np.sqrt(w) + 1e-12   # price path in units of its own volatility
        inc = np.stack([np.full((n, w), 1.0 / w), dpw / scale,
                        vw / (vw.sum(axis=1, keepdims=True) + 1e-12)], axis=2)   # (n, w, 3)
        s1 = np.zeros((n, 3)); s2 = np.zeros((n, 3, 3)); s3 = np.zeros((n, 3, 3, 3))
        for k in range(w):                           # Chen's identity: S(path * segment)
            d = inc[:, k, :]
            d2 = np.einsum("ni,nj->nij", d, d) / 2.0
            d3 = np.einsum("ni,nj,nk->nijk", d, d, d) / 6.0
            s3 = s3 + np.einsum("nij,nk->nijk", s2, d) + np.einsum("ni,njk->nijk", s1, d2) + d3
            s2 = s2 + np.einsum("ni,nj->nij", s1, d) + d2
            s1 = s1 + d
        levy_tp = 0.5 * (s2[:, 0, 1] - s2[:, 1, 0])
        levy_pv = 0.5 * (s2[:, 1, 2] - s2[:, 2, 1])
        feats = np.column_stack([s1, s2.reshape(n, 9), s3.reshape(n, 27), levy_tp, levy_pv])
        feats[~np.isfinite(feats).all(axis=1)] = np.nan
        out[w:] = feats
        return pd.DataFrame(out, index=df.index, columns=self.columns)


class AdaptiveConformalController:
    """One-sided adaptive conformal bound for a win probability.

    Nonconformity score of a calibration case = predicted probability minus the realised win
    rate of its nearest neighbours in predicted probability (how over-confident the model was
    around there). The lower bound is p_hat minus the (1 - alpha) quantile of those scores.
    A 0/1 outcome cannot be "covered" trade by trade, so the online error is defined on a
    window: err = 1 when the hit rate of the last `window` closed trades fell below the average
    lower bound they were authorised with.
    """

    def __init__(self, alpha_target: float = 0.10, gamma: float = 0.025, alpha_min: float = 0.01,
                 alpha_max: float = 0.30, window: int = 20) -> None:
        self.alpha_target, self.gamma = alpha_target, gamma
        self.alpha_min, self.alpha_max, self.window = alpha_min, alpha_max, window
        self.alpha = alpha_target
        self.scores = np.zeros(1)
        self.recent: list[tuple[float, int]] = []
        self.n_updates = 0

    def fit_calibration(self, p_cal: np.ndarray, y_cal: np.ndarray) -> "AdaptiveConformalController":
        """New calibration scores (after a retrain). The adapted alpha is kept."""
        p_cal, y_cal = np.asarray(p_cal, float), np.asarray(y_cal, float)
        if len(p_cal) < 20:
            self.scores = np.array([0.5])
            return self
        order = np.argsort(p_cal)
        k = max(20, len(p_cal) // 10)
        ys = pd.Series(y_cal[order]).rolling(k, center=True, min_periods=k // 2).mean().to_numpy()
        self.scores = np.sort(p_cal[order] - ys)
        return self

    def quantile(self) -> float:
        n = len(self.scores)
        rank = min(n - 1, max(0, int(np.ceil((1 - self.alpha) * (n + 1))) - 1))
        return float(max(self.scores[rank], 0.0))

    def predict_lower_bound(self, p_hat: float | np.ndarray) -> tuple[np.ndarray, float]:
        q = self.quantile()
        return np.clip(np.asarray(p_hat, float) - q, 0.0, 1.0), q

    def update_on_trade_close(self, p_hat_entry: float, y_realized: int) -> float:
        p_lower = float(self.predict_lower_bound(p_hat_entry)[0])
        self.recent = (self.recent + [(p_lower, int(y_realized))])[-self.window:]
        self.n_updates += 1
        if len(self.recent) >= max(5, self.window // 2):
            bound = float(np.mean([b for b, _ in self.recent]))
            hit = float(np.mean([y for _, y in self.recent]))
            err = 1.0 if hit < bound else 0.0
            self.alpha = float(np.clip(self.alpha + self.gamma * (self.alpha_target - err),
                                       self.alpha_min, self.alpha_max))
        return self.alpha

    def to_dict(self) -> dict:
        return {"alpha": self.alpha, "alpha_target": self.alpha_target, "gamma": self.gamma,
                "alpha_min": self.alpha_min, "alpha_max": self.alpha_max, "window": self.window,
                "scores": self.scores.tolist(), "recent": [list(x) for x in self.recent],
                "n_updates": self.n_updates}

    @classmethod
    def from_dict(cls, d: dict) -> "AdaptiveConformalController":
        obj = cls(d["alpha_target"], d["gamma"], d["alpha_min"], d["alpha_max"], d["window"])
        obj.alpha, obj.scores = float(d["alpha"]), np.array(d["scores"], float)
        obj.recent = [(float(a), int(b)) for a, b in d["recent"]]
        obj.n_updates = int(d.get("n_updates", 0))
        return obj
