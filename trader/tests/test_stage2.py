import numpy as np
import pandas as pd

from prop.research import stage2 as G


def test_hurst_separates_trending_from_reverting_series():
    rng = np.random.default_rng(3)
    e = rng.normal(size=4000)
    walk = pd.Series(np.cumsum(e))
    trend = pd.Series(np.cumsum(pd.Series(e).rolling(10).mean().fillna(0.0)))
    revert = pd.Series(e)
    h = lambda s: float(G.hurst(s).iloc[-1])  # noqa: E731
    assert 0.35 < h(walk) < 0.65
    assert h(trend) > h(walk) > h(revert)
    assert h(revert) < 0.2


def test_days_keep_the_measured_worst_point_and_calendar_gaps():
    idx = pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06"])
    p = pd.DataFrame({"net": [0.01, -0.02, 0.005], "worst": [-0.004, -0.03, 0.0]}, index=idx)
    t = G.to_trades(p, 0.01, measured=True)
    assert np.allclose(t.R[:, 0], [1.0, -2.0, 0.5])
    assert np.allclose(t.MAE[:, 0], [-0.4, -3.0, 0.0])
    assert list(t.gap) == [1.0, 1.0, 3.0]
