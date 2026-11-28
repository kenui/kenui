import numpy as np
import pandas as pd

from prop.research.cycle4 import split_adjusted


def test_split_is_removed_and_normal_days_are_kept():
    idx = pd.bdate_range("2020-01-01", periods=6)
    close = np.array([10.0, 10.1, 10.2, 81.6, 82.0, 81.0])            # 1-for-8 reverse split before the fourth day
    d = pd.DataFrame({"open": close, "high": close, "low": close, "close": close}, index=idx)
    out = split_adjusted(d)
    assert np.allclose(out["close"].iloc[:3], close[:3] * 8.0)
    assert np.allclose(out["close"].iloc[3:], close[3:])
    assert abs(out["close"].pct_change().iloc[3]) < 0.01
