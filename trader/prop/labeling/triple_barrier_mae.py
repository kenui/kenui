"""Labels and sample weights derived from the simulated paths.

  y_v2: target reached before the stop (classic triple barrier).
  y_v3: same, and the open loss never went beyond 0.85 of the stop distance (low-heat winners).
  y_v4: positive net result of the partial/break-even exit AND MAE inside the 0.85 limit.
Losers that travelled through the MAE limit weigh 3x: they are the trades that kill a prop
account, so a false positive there costs more than a missed winner.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from prop.config.quant import Q


def add_labels(events: pd.DataFrame) -> pd.DataFrame:
    ev = events.copy()
    ev["y_v2"] = (ev["reason_plain"] == "target").astype(int)
    ev["y_v3"] = ((ev["reason_plain"] == "target") & (ev["mae_plain"] >= -Q.mae_limit)).astype(int)
    ev["y_v4"] = ((ev["r_arm1"] > 0) & (ev["mae_arm1"] >= -Q.mae_limit)).astype(int)
    hot_loser = (ev["y_v4"] == 0) & (ev["mae_arm1"] < -Q.mae_limit)
    ev["w_v4"] = np.where(hot_loser, Q.high_mae_weight, 1.0)
    return ev
