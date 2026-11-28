import numpy as np
import pandas as pd

from prop.research.cycle3 import month_to_date, trades


def test_month_to_date_restarts_at_each_month():
    idx = pd.bdate_range("2020-01-27", "2020-02-05")
    c = pd.Series(np.exp(np.arange(len(idx)) * 0.01), index=idx)
    mtd = month_to_date(c)
    assert np.isnan(mtd.iloc[0])                                        # no previous month in the data
    feb = mtd[mtd.index.month == 2]
    assert np.allclose(feb.to_numpy(), 0.01 * np.arange(1, len(feb) + 1))


def test_trades_joins_the_exit_day_to_its_month():
    x = pd.Series(0.0, index=pd.bdate_range("2020-01-01", "2020-03-10"))
    x[pd.Timestamp("2020-01-31")] = 0.01
    x[pd.Timestamp("2020-02-03")] = 0.02
    x[pd.Timestamp("2020-02-28")] = -0.01
    t = trades(x)
    assert len(t) == 2 and np.isclose(t.iloc[0], 0.03)
