"""V2 meta-labeler: XGBoost predicts P(the primary signal reaches its target)."""
from __future__ import annotations

import numpy as np
from xgboost import XGBClassifier


def xgb(seed: int = 0) -> XGBClassifier:
    """Shallow, heavily regularised trees: the signal-to-noise ratio here is tiny."""
    return XGBClassifier(n_estimators=150, max_depth=3, learning_rate=0.05, subsample=0.8,
                         colsample_bytree=0.8, min_child_weight=10, reg_lambda=5.0,
                         n_jobs=4, random_state=seed, verbosity=0)


class MetaLabeler:
    def __init__(self, seed: int = 0) -> None:
        self.model = xgb(seed)
        self.const: float | None = None

    def fit(self, x: np.ndarray, y: np.ndarray, sample_weight: np.ndarray | None = None) -> "MetaLabeler":
        if len(np.unique(y)) < 2:
            self.const = float(np.mean(y))
            return self
        self.const = None
        self.model.fit(x, y, sample_weight=sample_weight)
        return self

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        if self.const is not None:
            return np.full(len(x), self.const)
        return self.model.predict_proba(x)[:, 1]
