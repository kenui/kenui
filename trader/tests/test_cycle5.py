import numpy as np
import pandas as pd

from prop.research.cycle5 import extreme, flow


def test_extreme_fades_a_crowded_position_and_leaves_when_it_normalises():
    idx = pd.date_range("2020-01-03", periods=60, freq="W-FRI")
    rng = np.random.default_rng(0)
    x = pd.Series(rng.normal(0, 0.01, 60), index=idx)
    x.iloc[40:45] = 0.2                                                  # crowded long
    s = extreme(x, 26)
    assert s.iloc[40] == -1.0 and (s.iloc[:26] == 0).all()
    assert s.iloc[50] == 0.0 or abs(((x - x.rolling(26).mean()) / x.rolling(26).std()).iloc[50]) >= 0.5


def test_flow_follows_the_change():
    x = pd.Series([0.0, 0.1, 0.2, 0.1, 0.0], index=pd.date_range("2020-01-03", periods=5, freq="W-FRI"))
    assert list(flow(x, 1)) == [0.0, 1.0, 1.0, -1.0, -1.0]
