"""V4/V5 meta-model: three different model families plus an inductive conformal layer.

Ensemble: XGBoost, elastic-net logistic regression and extra trees, trained with sample weights
on the first 75% of the training window ("proper training set"). The last 25% is the
calibration set. The probability interval [p_lower, p_upper] comes from the inductive
Venn-Abers predictor (Vovk), the conformal-family method built for probabilities: the test
score is added to the calibration set once as a loss and once as a win, and two isotonic fits
give the two ends. A plain split-conformal interval on a 0/1 outcome is too wide to be useful.
The interval is then widened by the disagreement between the three models at level alpha, so
p_lower is low where the models disagree or where the calibration set has few similar cases.
"""
from __future__ import annotations

import numpy as np
from scipy.stats import norm
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from prop.config.quant import Q
from prop.extensions.atemporal_aci import AdaptiveConformalController
from prop.models.meta_labeler import xgb


def cross_calibrate(raw: np.ndarray, y: np.ndarray) -> tuple[IsotonicRegression, np.ndarray]:
    """Isotonic calibrator for the raw ensemble score, plus calibrated probabilities of the same
    cases produced out of fold (even rows calibrated by the odd rows and vice versa), so that the
    conformity scores built from them are honest. The raw score is not a probability: the sample
    weights that punish high-heat losers push it well below the true hit rate."""
    raw, y = np.asarray(raw, float), np.asarray(y, float)
    cross = np.full(len(raw), y.mean() if len(y) else 0.5)
    for part in (0, 1):
        fit, hold = np.arange(len(raw)) % 2 != part, np.arange(len(raw)) % 2 == part
        if fit.sum() >= 10 and hold.any():
            cross[hold] = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip").fit(raw[fit], y[fit]).predict(raw[hold])
    iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip").fit(raw, y)
    return iso, cross


class ConformalMetaEnsemble:
    def __init__(self, alpha: float = Q.conformal_alpha, calibration_frac: float = Q.calibration_frac,
                 seed: int = 0, adaptive: bool = False, aci: AdaptiveConformalController | None = None) -> None:
        """`adaptive=True` replaces the static Venn-Abers interval by the ACI lower bound,
        whose level keeps moving with the realised trades (see `notify_trade_outcome`)."""
        self.alpha, self.calibration_frac, self.seed = alpha, calibration_frac, seed
        self.adaptive = adaptive
        self.aci = aci or AdaptiveConformalController(alpha_target=alpha)
        self.members: list = []
        self.cal_scores = np.empty(0)
        self.cal_y = np.empty(0)
        self.const: float | None = None
        self.iso: IsotonicRegression | None = None
        self.cal_p = np.empty(0)

    def _new_members(self) -> list:
        return [xgb(self.seed),
                make_pipeline(StandardScaler(), LogisticRegression(penalty="elasticnet", solver="saga",
                                                                   l1_ratio=0.5, C=0.1, max_iter=400)),
                ExtraTreesClassifier(n_estimators=200, max_depth=6, min_samples_leaf=15, n_jobs=4,
                                     random_state=self.seed)]

    def fit(self, x: np.ndarray, y: np.ndarray, sample_weight: np.ndarray, purge: int = 0) -> "ConformalMetaEnsemble":
        """Rows must be in time order. `purge` rows between the two parts are dropped."""
        n_cal = int(len(x) * self.calibration_frac)
        n_fit = len(x) - n_cal - purge
        if n_fit < 100 or n_cal < 40 or len(np.unique(y[:n_fit])) < 2:
            self.const = float(np.mean(y)) if len(y) else 0.5
            return self
        self.const = None
        self.members = self._new_members()
        self.members[0].fit(x[:n_fit], y[:n_fit], sample_weight=sample_weight[:n_fit])
        self.members[1].fit(x[:n_fit], y[:n_fit], logisticregression__sample_weight=sample_weight[:n_fit])
        self.members[2].fit(x[:n_fit], y[:n_fit], sample_weight=sample_weight[:n_fit])
        self.cal_scores = self._raw(x[-n_cal:]).mean(axis=1)
        self.cal_y = y[-n_cal:].astype(float)
        if self.adaptive:
            self.iso, self.cal_p = cross_calibrate(self.cal_scores, self.cal_y)
            self.aci.fit_calibration(self.cal_p, self.cal_y)
        return self

    def notify_trade_outcome(self, p_hat_entry: float, y_realized: int) -> float:
        """Call when a position closes (walk-forward and live). Returns the adapted alpha."""
        return self.aci.update_on_trade_close(p_hat_entry, y_realized)

    def _raw(self, x: np.ndarray) -> np.ndarray:
        return np.column_stack([m.predict_proba(x)[:, 1] for m in self.members])

    def predict(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """(p, p_lower, p_upper). p is the Venn-Abers merged probability."""
        if self.const is not None or len(x) == 0:
            p = np.full(len(x), self.const if self.const is not None else 0.5)
            return p, np.zeros(len(x)), np.ones(len(x))
        raw = self._raw(x)
        score = raw.mean(axis=1)
        if self.adaptive:
            p = self.iso.predict(score)
            p_lower, q = self.aci.predict_lower_bound(p)
            return p, p_lower, np.clip(p + q, 0, 1)
        p0, p1 = np.empty(len(x)), np.empty(len(x))
        for i, s in enumerate(score):
            xs = np.append(self.cal_scores, s)
            for label, out in ((0.0, p0), (1.0, p1)):
                iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
                iso.fit(xs, np.append(self.cal_y, label))
                out[i] = iso.predict([s])[0]
        p = p1 / (1 - p0 + p1 + 1e-12)
        spread = norm.ppf(1 - self.alpha / 2) * raw.std(axis=1, ddof=1) / np.sqrt(raw.shape[1])
        return p, np.clip(np.minimum(p0, p1) - spread, 0, 1), np.clip(np.maximum(p0, p1) + spread, 0, 1)
