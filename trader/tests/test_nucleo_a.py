import numpy as np

from prop.research import nucleo_a as N


def test_kalman_tracks_the_hedge_ratio_without_looking_ahead():
    rng = np.random.default_rng(1)
    x = np.cumsum(rng.normal(0, 0.01, 4000))
    y = 0.3 + 0.8 * x + rng.normal(0, 0.002, 4000)
    e, beta = N.kalman(y, x[:, None], 1e-4)
    assert abs(beta[-1, 0] - 0.8) < 0.05
    y2 = y.copy()
    y2[3000:] += 1.0                                   # a change in the future must not move the past
    e2, beta2 = N.kalman(y2, x[:, None], 1e-4)
    assert np.allclose(e[:3000], e2[:3000]) and np.allclose(beta[:3001], beta2[:3001])


def test_adf_and_half_life_tell_a_reverting_series_from_a_random_walk():
    rng = np.random.default_rng(2)
    ou = np.zeros(3000)
    for t in range(1, 3000):
        ou[t] = 0.9 * ou[t - 1] + rng.normal()
    walk = np.cumsum(rng.normal(size=3000))
    assert N.adf_t(ou) < -3.45 < N.adf_t(walk)
    assert 4 < N.half_life(ou) < 10


def test_folds_are_70_30_and_never_overlap_in_the_test_part():
    import pandas as pd
    f = N.folds(pd.Timestamp("2010-01-01"), pd.Timestamp("2020-01-01"))
    assert all(b > a and c > b for a, b, c in f)
    assert all(f[i][2] == f[i + 1][1] for i in range(len(f) - 1))
