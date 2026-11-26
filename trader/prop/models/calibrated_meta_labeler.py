"""V3 meta-labeler: the same XGBoost wrapped in isotonic calibration (3 folds inside the
training window), so that a predicted 0.60 really wins about 60% of the time."""
from __future__ import annotations

import numpy as np
from sklearn.calibration import CalibratedClassifierCV

from prop.models.meta_labeler import xgb


class CalibratedMetaLabeler:
    def __init__(self, seed: int = 0) -> None:
        self.model = CalibratedClassifierCV(xgb(seed), method="isotonic", cv=3)
        self.const: float | None = None

    def fit(self, x: np.ndarray, y: np.ndarray, sample_weight: np.ndarray | None = None) -> "CalibratedMetaLabeler":
        if min(np.bincount(y, minlength=2)) < 6:
            self.const = float(np.mean(y))
            return self
        self.const = None
        self.model.fit(x, y, sample_weight=sample_weight)
        return self

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        if self.const is not None:
            return np.full(len(x), self.const)
        return self.model.predict_proba(x)[:, 1]
