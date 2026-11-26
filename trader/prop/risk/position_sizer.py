"""V2 position sizer: fractional-Kelly style scaling of risk by the meta-model probability.

Risk grows linearly from `risk_lo` at the decision threshold to `risk_hi` at high confidence.
A full Kelly bet needs the true edge; with an estimated probability a small fixed fraction of
it is the usual protection against estimation error, so the range is capped at 1% of the account.
"""
from __future__ import annotations

import numpy as np


def risk_from_probability(p: np.ndarray, threshold: float, risk_lo: float = 0.0025, risk_hi: float = 0.01,
                          full_confidence: float = 0.20) -> np.ndarray:
    """Risk fraction per trade. `full_confidence` is how far above the threshold p must be
    for the maximum risk."""
    scale = np.clip((np.asarray(p, float) - threshold) / full_confidence, 0.0, 1.0)
    return risk_lo + scale * (risk_hi - risk_lo)
