import numpy as np
import pandas as pd

from defi.clmm import Costs, amounts, liquidity_for_value, simulate, unit_edge

FREE = Costs(0, 0, 0)


def _frame(prices, f1=0.0):
    idx = pd.date_range("2026-01-01", periods=len(prices), freq="10min", tz="UTC")
    df = pd.DataFrame({"sqrt": np.sqrt(np.array(prices, dtype=float)), "f0": 0.0, "f1": f1}, index=idx)
    df["price"] = df.sqrt ** 2
    return df


def test_position_value_matches_capital():
    s, sa, sb = np.sqrt(2000.0), np.sqrt(1900.0), np.sqrt(2100.0)
    L = liquidity_for_value(60, s, sa, sb)
    x, y = amounts(L, s, sa, sb)
    assert abs(x * 2000 + y - 60) < 1e-9


def test_round_trip_inside_range_is_free_without_fees():
    eq = simulate(_frame([2000, 2050, 2000, 1950, 2000]), 0.05, costs=FREE)
    assert abs(eq.value.iloc[-1] - 60) < 1e-9
    assert eq.n_open.iloc[-1] == 1


def test_leaving_the_range_locks_in_a_loss():
    eq = simulate(_frame([2000, 2050, 2000, 1950, 2000]), 0.01, costs=FREE)
    assert eq.value.iloc[-1] < 59
    assert eq.n_open.iloc[-1] > 1


def test_fees_only_while_in_range():
    df = _frame([2000, 2000, 2000, 3000, 3000], f1=0.001)
    eq = simulate(df, 0.05, costs=FREE, active=[True, True, True, True, True], exit_buffer=10)
    # two flat in-range intervals pay; the jump out pays only for the part of the path inside
    L = liquidity_for_value(60, df.sqrt.iloc[0], df.sqrt.iloc[0] * np.sqrt(0.95), df.sqrt.iloc[0] * np.sqrt(1.05))
    assert 2 * L * 0.001 < eq.fees.iloc[-1] < 3 * L * 0.001


def test_unit_loss_is_quarter_variance():
    df = _frame([2000, 2020])
    u = unit_edge(df)
    r = np.log(2020 / 2000)
    assert abs(u.loss_n.iloc[0] - r * r / 8) / (r * r / 8) < 0.01
