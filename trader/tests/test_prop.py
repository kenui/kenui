"""Checks for the prop-challenge lab: fills, stops, locks, timeframe alignment, Monte Carlo."""
import dataclasses

import numpy as np
import pandas as pd

from prop.backtest import engine, metrics, montecarlo as mc
from prop.config.settings import Instrument, PropRules, RiskConfig
from prop.risk.risk_manager import news_windows
from prop.strategies.indicators import empty_signals
from prop.strategies.timeframe import signals_on

FREE = {"X": Instrument("X", "X", "spot", 0.0, 100.0, 0.0, False)}
RULES = PropRules(account_size=10_000.0, day_timezone="UTC")


def bars(closes, start="2026-01-05 10:00", spread=0.0005):
    idx = pd.date_range(start, periods=len(closes), freq="15min", tz="UTC")
    c = np.asarray(closes, float)
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) + spread, "low": np.minimum(o, c) - spread,
                         "close": c, "volume": 1.0}, index=idx)


def one_signal(df, at, side, stop, tp, max_bars=0):
    sg = empty_signals(df.index)
    sg.iloc[at, sg.columns.get_loc("side")] = side
    sg["stop_dist"], sg["tp_dist"], sg["max_bars"], sg["engine"] = stop, tp, max_bars, "t"
    return sg


def test_fills_next_open_and_sizes_by_risk():
    df = bars([1.10, 1.10, 1.10, 1.102, 1.112, 1.112])
    res = engine.run({"X": df}, {"X": one_signal(df, 1, 1, 0.005, 0.010)}, RiskConfig.plain(0.01), RULES, FREE)
    t = res.trades.iloc[0]
    assert t.entry_time == df.index[2] and t.entry == df["open"].iloc[2]
    assert t.reason == "target" and abs(t.r - 2.0) < 1e-9
    assert abs(t.units * 0.005 - 100.0) < 1e-6  # 1% of 10,000 at risk


def test_stop_wins_when_both_touched_and_short_side():
    df = bars([1.10, 1.10, 1.10, 1.10])
    df.iloc[2, df.columns.get_loc("high")] = 1.12
    df.iloc[2, df.columns.get_loc("low")] = 1.08
    for side in (1, -1):
        res = engine.run({"X": df}, {"X": one_signal(df, 1, side, 0.01, 0.01)}, RiskConfig.plain(), RULES, FREE)
        assert res.trades.iloc[0].reason == "stop" and abs(res.trades.iloc[0].r + 1.0) < 1e-9


def test_costs_and_leverage_cap():
    inst = {"X": Instrument("X", "X", "spot", 0.001, 2.0, 0.0, False)}
    df = bars([100.0, 100.0, 100.0, 100.0, 100.0])
    res = engine.run({"X": df}, {"X": one_signal(df, 0, 1, 0.5, 50.0, max_bars=2)}, RiskConfig.plain(), RULES, inst)
    t = res.trades.iloc[0]
    assert abs(t.units * 100.0 - 20_000.0) < 1e-6          # capped at 2x equity
    assert abs(t.pnl + 20_000.0 * 0.002) < 0.05            # flat price, pays both sides


def test_daily_hard_stop_locks_the_day_and_verdict_sees_breach():
    closes = [100.0] * 3 + [96.0] + [96.0] * 4
    df = bars(closes)
    sg = one_signal(df, 1, 1, 100.0, 100.0)  # huge stop so only the lock can close it
    sg["side"] = 0
    sg.iloc[[1, 5], sg.columns.get_loc("side")] = 1
    inst = {"X": Instrument("X", "X", "spot", 0.0, 1.0, 0.0, False)}
    locked = dataclasses.replace(RiskConfig.plain(1.0), max_risk_per_trade=1.0, daily_hard_stop=0.03)
    res = engine.run({"X": df}, {"X": sg}, locked, RULES, inst)
    assert list(res.trades.reason) == ["lock"] and res.locks[0][1] == "daily_stop"
    free = dataclasses.replace(RiskConfig.plain(1.0), max_risk_per_trade=1.0)
    res2 = engine.run({"X": df.assign(low=df["low"] - 3)}, {"X": sg}, free, RULES, inst)
    assert metrics.challenge_verdict(res2, RULES).startswith("REPROVOU diario")


def test_slow_timeframe_signal_fills_when_the_slow_bar_closes():
    df = bars(np.linspace(1.0, 1.1, 64), start="2026-01-05 00:00")

    def eng(slow):
        sg = empty_signals(slow.index)
        sg.loc[sg.index[2], "side"] = 1  # slow bar 02:00-03:00
        sg["stop_dist"], sg["tp_dist"], sg["max_bars"], sg["engine"] = 1.0, 1.0, 3, "t"
        return sg

    sg = signals_on(df, eng, "1h")
    when = sg.index[sg["side"] != 0]
    assert list(when) == [pd.Timestamp("2026-01-05 02:45", tz="UTC")] and sg.loc[when[0], "max_bars"] == 12
    res = engine.run({"X": df}, {"X": sg}, RiskConfig.plain(), RULES, FREE)
    assert res.trades.iloc[0].entry_time == pd.Timestamp("2026-01-05 03:00", tz="UTC")


def test_news_window_blocks_us_data_time():
    idx = pd.date_range("2026-03-04 12:00", periods=12, freq="15min", tz="UTC")  # 08:30 NY = 13:30 UTC
    blocked = news_windows(idx)
    assert blocked[idx == pd.Timestamp("2026-03-04 13:30", tz="UTC")][0]
    assert not blocked[idx == pd.Timestamp("2026-03-04 12:15", tz="UTC")][0]


def test_monte_carlo_no_edge_is_a_coin_toss_and_edge_helps():
    risk = dataclasses.replace(RiskConfig.prop(), max_drawdown_lock=None)
    flat = mc.bootstrap(mc.coin_flip_days(cost_r=0.0), risk, "flat", paths=600)
    good = mc.bootstrap(mc.coin_flip_days(cost_r=-0.2), risk, "good", paths=300)
    assert 0.40 < flat.pass_phase1 < 0.62
    assert good.pass_phase1 > 0.95 and good.value_per_attempt_usd > flat.value_per_attempt_usd
