"""Cycle 2: the calendar window and the exporter's filter."""
import pandas as pd

from prop.data.mt5_export import wanted
from prop.research import cycle2 as C


def test_window_marks_the_last_and_first_trading_days_of_each_month():
    idx = pd.bdate_range("2024-01-01", "2024-03-29")
    w = C.in_window(idx, 1, 3)
    jan = w["2024-01"]
    assert list(jan[jan].index.day) == [1, 2, 3, 31]
    assert w["2024-02-29"] and w["2024-03-05"] and not w["2024-03-06"] and not w["2024-02-15"]
    assert C.in_window(idx, 3, 3)["2024-02-27"] and not C.in_window(idx, 1, 1)["2024-02-02"]


def test_exporter_leaves_single_stocks_out_unless_asked():
    assert wanted("Forex\\EURUSD", False) and wanted("Crypto\\BTCUSD", False)
    assert not wanted("Stocks\\US\\AAPL", False) and wanted("Stocks\\US\\AAPL", True)
