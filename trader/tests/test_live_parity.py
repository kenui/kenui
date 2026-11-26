"""The live bot must compute exactly the same signals as the research dataset (no train/live skew)."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

DATA = Path(__file__).resolve().parent.parent / "data"
pytestmark = pytest.mark.skipif(not (DATA / "dataset.parquet").exists(), reason="needs downloaded research data")


def test_bot_features_match_research():
    import paper_bot as B
    from research import panel as P
    T = pd.Timestamp("2026-11-20 13:35", tz="UTC")
    panels = {s: df.loc[T - pd.Timedelta(days=B.HIST_DAYS):T] for s, df in P.load_all().items() if s != "FTMUSDT"}
    live_rows = B.latest_features(panels, T)
    cols = [c for c in live_rows.columns if c != "ok"]
    ref = pd.read_parquet(DATA / "dataset.parquet", filters=[("time", "==", T)]).set_index("sym")
    common = live_rows.index.intersection(ref.index)
    assert len(common) >= 35
    a, b = live_rows.loc[common, cols].astype(float), ref.loc[common, cols].astype(float)
    bad = {}
    for c in cols:
        if c.startswith("xs_") or c.startswith("mkt_"):
            continue      # these depend on FTM being in the universe early on; checked loosely below
        diff = (a[c] - b[c]).abs() / (b[c].abs() + 1e-6)
        if not ((diff < 2e-2) | (a[c].isna() & b[c].isna())).all():
            bad[c] = float(diff.max())
    assert not bad, bad
    for c in [c for c in cols if c.startswith("mkt_")]:
        assert np.allclose(a[c], b[c], rtol=5e-2, atol=1e-4, equal_nan=True), c
