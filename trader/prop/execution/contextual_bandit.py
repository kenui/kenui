"""V5 exit-policy selector: LinUCB contextual bandit with three arms.

  arm 0  scalp lock-in        target 0.9R, no partial
  arm 1  institutional hybrid 50% off at +0.8R, break-even, target 1.6R
  arm 2  trend runner         40% off at +1.0R, 1.5 ATR trailing stop
Each arm keeps a ridge regression of reward on context (A, b). The arm with the highest upper
confidence bound is played, and only that arm is updated with the realised, MAE-adjusted reward.
"""
from __future__ import annotations

import numpy as np

ARMS = ("arm0", "arm1", "arm2")


class LinUCB:
    def __init__(self, n_features: int, n_arms: int = len(ARMS), alpha: float = 0.5, ridge: float = 1.0) -> None:
        self.alpha = alpha
        self.A = np.stack([np.eye(n_features) * ridge for _ in range(n_arms)])
        self.b = np.zeros((n_arms, n_features))
        self.pulls = np.zeros(n_arms, int)

    def select(self, x: np.ndarray) -> int:
        scores = np.empty(len(self.A))
        for a in range(len(self.A)):
            inv = np.linalg.inv(self.A[a])
            theta = inv @ self.b[a]
            scores[a] = theta @ x + self.alpha * np.sqrt(x @ inv @ x)
        return int(np.argmax(scores + 1e-9 * np.array([0.0, 1.0, 0.0])))  # ties go to the hybrid arm

    def update(self, arm: int, x: np.ndarray, reward: float) -> None:
        self.A[arm] += np.outer(x, x)
        self.b[arm] += reward * x
        self.pulls[arm] += 1

    @staticmethod
    def reward(r: float, mae: float, heat_penalty: float = 0.25) -> float:
        """Net R minus a charge for the heat taken (MAE is negative)."""
        return r + heat_penalty * mae

    def state(self) -> dict:
        return {"A": self.A.tolist(), "b": self.b.tolist(), "pulls": self.pulls.tolist(), "alpha": self.alpha}

    def load(self, state: dict) -> None:
        self.A, self.b = np.array(state["A"]), np.array(state["b"])
        self.pulls, self.alpha = np.array(state["pulls"]), float(state["alpha"])
