"""Concept-drift detector: one-sided CUSUM on the Brier score of the closed trades.

Brier = (predicted probability - outcome)^2. A calibrated model on a near coin-flip problem
scores about 0.25. The CUSUM accumulates how much the rolling Brier of the last `window` trades
exceeds `reference + slack`; above `threshold` the model is treated as broken and SAFE_MODE
cuts position size by 60% until the next retraining.
"""
from __future__ import annotations

from collections import deque


class CusumBrier:
    def __init__(self, reference: float = 0.25, slack: float = 0.01, threshold: float = 0.15,
                 window: int = 20, safe_scale: float = 0.4) -> None:
        self.reference, self.slack, self.threshold = reference, slack, threshold
        self.safe_scale = safe_scale
        self.recent: deque[float] = deque(maxlen=window)
        self.s = 0.0
        self.safe_mode = False

    def update(self, p_pred: float, outcome: int) -> bool:
        """Feed one closed trade; returns True while SAFE_MODE is on."""
        self.recent.append((p_pred - outcome) ** 2)
        if len(self.recent) == self.recent.maxlen:
            rolling = sum(self.recent) / len(self.recent)
            self.s = max(0.0, self.s + rolling - self.reference - self.slack)
            if self.s > self.threshold:
                self.safe_mode = True
        return self.safe_mode

    def scale(self) -> float:
        return self.safe_scale if self.safe_mode else 1.0

    def reset(self) -> None:
        """Called when the models are retrained."""
        self.s, self.safe_mode = 0.0, False
        self.recent.clear()

    def state(self) -> dict:
        return {"s": self.s, "safe_mode": self.safe_mode, "recent": list(self.recent)}

    def load(self, state: dict) -> None:
        self.s, self.safe_mode = float(state["s"]), bool(state["safe_mode"])
        self.recent.clear()
        self.recent.extend(state["recent"])
