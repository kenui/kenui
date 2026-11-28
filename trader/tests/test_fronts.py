import numpy as np
import pandas as pd

from prop.fronts import portfolio as P
from prop.research import mt5_study as S


def series(seed: int, drift: float, n: int = 3000) -> pd.Series:
    rng = np.random.default_rng(seed)
    return pd.Series(rng.normal(drift, 0.01, n), index=pd.bdate_range("2008-01-01", periods=n))


def test_hrp_weights_are_positive_sum_to_one_and_favour_the_calmer_front():
    x = pd.DataFrame({"a": series(1, 0.0), "b": series(2, 0.0) * 3, "c": series(3, 0.0)})
    w = P.hrp(x)
    assert abs(w.sum() - 1) < 1e-9 and (w > 0).all()
    assert w["b"] < w["a"] and w["b"] < w["c"]
    assert P.hrp(x[["a"]])["a"] == 1.0


def test_gate_keeps_out_losing_and_correlated_fronts():
    anchor = series(1, 0.0004)
    good, bad = series(2, 0.0006), series(3, -0.0006)
    copy = anchor * 0.9 + series(4, 0.0005) * 0.1
    inside, log = P.gate(anchor, {"boa": good, "ruim": bad, "copia": copy})
    verdict = {r["frente"]: r["decisao"] for r in log}
    assert verdict == {"boa": "entra", "ruim": "fica fora", "copia": "fica fora"}
    assert list(inside) == ["frente 1", "boa"]
    assert S.SPLIT > anchor.index[0]
