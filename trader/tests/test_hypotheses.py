import numpy as np
import pandas as pd

from prop.research import hypotheses as H
from prop.research import stage2 as G


class FakeMarket:
    def __init__(self, n: int) -> None:
        rng = np.random.default_rng(5)
        idx = pd.bdate_range("2012-01-02", periods=n)
        self.data = {}
        for s in G.SYMS:
            c = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, n)))
            self.data[s] = pd.DataFrame({"open": c, "high": c * 1.005, "low": c * 0.995, "close": c}, index=idx)

    def bars(self, sym: str, tf: str) -> pd.DataFrame:
        return self.data[sym]


def test_features_of_a_day_do_not_change_when_the_future_changes():
    full, cut = FakeMarket(900), FakeMarket(900)
    for s in G.SYMS:
        cut.data[s] = cut.data[s].iloc[:700]
    a, b = H.features(full), H.features(cut)
    for s in G.SYMS:
        x, y = a[s].loc[b[s].index[:-1], H.FEATURES + ["on"]], b[s].iloc[:-1][H.FEATURES + ["on"]]
        assert np.allclose(x.astype(float).fillna(0.0), y.astype(float).fillna(0.0))
        assert b[s]["y"].iloc[-H.HORIZON:].isna().all()          # the label needs the next five days


def test_gold_silver_scales_only_reduce_the_position():
    sc = H.gold_silver_scales(H.features(FakeMarket(600)))
    for case in sc.values():
        for s in G.SYMS:
            assert set(np.unique(case[s].dropna())) <= {0.25, 0.5, 1.0}
