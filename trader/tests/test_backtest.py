"""Engine correctness checks on hand-made candles (not market results)."""
import numpy as np
import pandas as pd
import pytest

from kenui_trader.backtest import Costs, Risk, run, walk_forward
from kenui_trader.strategies import BASELINES

NO_COST = Costs(fee=0, slippage=0, min_notional=0)
NO_RISK = Risk(stop_loss=None, take_profit=None, daily_loss_limit=None)


def candles(closes, opens=None, highs=None, lows=None, freq="5min"):
    closes = np.asarray(closes, float)
    opens = closes if opens is None else np.asarray(opens, float)
    idx = pd.date_range("2026-01-01", periods=len(closes), freq=freq, tz="UTC")
    return pd.DataFrame({
        "open": opens, "close": closes,
        "high": np.maximum(opens, closes) if highs is None else highs,
        "low": np.minimum(opens, closes) if lows is None else lows,
        "volume": 1.0,
    }, index=idx)


def sig(df, at):
    s = pd.Series(False, index=df.index)
    s.iloc[at] = True
    return s


def test_fill_next_open_no_lookahead():
    df = candles([100, 100, 110, 120], opens=[100, 105, 110, 120])
    res = run(df, sig(df, [0]), sig(df, [2]), capital=100, costs=NO_COST, risk=NO_RISK)
    t = res.trades.iloc[0]
    assert t.entry_px == 105  # bar 1 open, not bar 0 close
    assert t.exit_px == 120   # bar 3 open
    assert res.equity.iloc[-1] == pytest.approx(100 * 120 / 105)


def test_costs_charged_both_sides():
    df = candles([100, 100, 100, 100])
    c = Costs(fee=0.001, slippage=0.0005, min_notional=0)
    res = run(df, sig(df, [0]), sig(df, [1]), capital=100, costs=c, risk=NO_RISK)
    expected = 100 * (1 - 0.001) / (100 * 1.0005) * 100 * 0.9995 * (1 - 0.001)
    assert res.equity.iloc[-1] == pytest.approx(expected)
    assert res.equity.iloc[-1] < 100


def test_stop_wins_when_both_hit_same_bar():
    df = candles([100, 100, 100], highs=[100, 100, 110], lows=[100, 100, 90])
    r = Risk(stop_loss=0.05, take_profit=0.05, daily_loss_limit=None)
    res = run(df, sig(df, [0]), None, capital=100, costs=NO_COST, risk=r)
    assert res.trades.iloc[0].reason == "stop"
    assert res.equity.iloc[-1] == pytest.approx(95)


def test_gap_through_stop_fills_at_open():
    df = candles([100, 100, 80], opens=[100, 100, 80], lows=[100, 100, 79])
    r = Risk(stop_loss=0.05, take_profit=None, daily_loss_limit=None)
    res = run(df, sig(df, [0]), None, capital=100, costs=NO_COST, risk=r)
    assert res.trades.iloc[0].exit_px == 80


def test_min_notional_skips_tiny_orders():
    df = candles([100, 100, 100])
    res = run(df, sig(df, [0]), None, capital=4, costs=Costs(min_notional=5), risk=NO_RISK)
    assert res.trades.empty


def test_baselines_and_walk_forward_run():
    rng = np.random.default_rng(0)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.004, 6000)))
    df = candles(close, opens=np.r_[close[0], close[:-1]])
    df["high"] = df[["open", "close"]].max(axis=1) * 1.002
    df["low"] = df[["open", "close"]].min(axis=1) * 0.998
    df["volume"] = rng.lognormal(0, 0.5, len(df))
    for name, (fn, g) in BASELINES.items():
        wf = walk_forward(df, fn, g[:4], n_splits=2)
        assert {"total_return_%", "sharpe"} <= set(wf.columns) or wf.empty, name
