"""MetaTrader 5 trend robot: sizing, circuit breaker and phase logic (no terminal needed)."""
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from prop.live import mt5_trend as M

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)


def bars(drift: float, n: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(1)
    return pd.DataFrame({"close": 100 * np.exp(np.cumsum(drift + rng.normal(0, 0.01, n)))})


def test_weight_follows_the_trend_and_the_volatility():
    assert M.weight(bars(-0.003)) == 0.0
    w = M.weight(bars(0.003))
    assert 1.0 < w < 1.8                        # 1% budget / downside volatility, which is below 1% in a rising series
    assert M.weight(bars(0.003, 100)) == 0.0    # not enough history


def test_target_lots_rounding_and_limits():
    kw = dict(unit=0.006, n_assets=2, price=4000.0, contract=100.0, step=0.01, vmin=0.01, vmax=50.0)
    assert M.target_lots(1.0, 0.003, equity=100_000, **kw) == 0.06       # 25,000 notional / 400,000 per lot
    assert M.target_lots(1.0, 0.003, equity=1_000, **kw) == 0.0          # below the minimum lot: no position
    assert M.target_lots(0.0, 0.003, equity=100_000, **kw) == 0.0
    assert M.target_lots(1.0, 0.0, equity=100_000, **kw) == 0.0


def test_rebalance_band():
    assert not M.needs_trade(0.10, 0.11, 0.01)
    assert M.needs_trade(0.10, 0.14, 0.01)
    assert M.needs_trade(0.10, 0.0, 0.01)
    assert not M.needs_trade(0.0, 0.0, 0.01)


def test_rules_file_has_every_firm():
    for firm in ("padrao", "ftmo", "the5ers", "fundednext"):  # e8_pro has a single phase
        r = M.load_rules(firm)
        assert 0 < r["meta_fase2"] < r["meta_fase1"] <= 0.10 and r["perda_diaria"] < r["perda_total"]


def test_breaker_phases_and_violation(tmp_path):
    rules, st = M.load_rules("padrao"), M.State(tmp_path / "s.db")
    s = M.account_step(st, rules, 10_000, NOW)
    assert (s["phase"], s["locked"], s["flatten"]) == (0, False, False)
    s = M.account_step(st, rules, 9_690, NOW)                 # -3.1% in the day: 60% of the 5% limit is 3%
    assert s["locked"] and s["flatten"]
    s = M.account_step(st, rules, 9_690, NOW)                 # stays locked, flattens only once
    assert s["locked"] and not s["flatten"]
    nxt = NOW.replace(day=26)
    s = M.account_step(st, rules, 9_700, nxt)
    assert not s["locked"] and abs(s["x"] + 0.03) < 1e-9
    s = M.account_step(st, rules, 10_810, nxt.replace(day=27))            # +8.1%: Phase 1 passed
    assert s["phase"] == 1 and s["flatten"] and s["x"] == 0.0
    s = M.account_step(st, rules, 10_810 * 1.051, nxt.replace(day=28))    # +5.1%: funded
    assert s["phase"] == 2
    funded = 10_810 * 1.051
    s = M.account_step(st, rules, funded * 1.046, nxt.replace(day=29))    # payout trigger
    assert st.get("payouts") > 0 and s["x"] == 0.0
    M.account_step(st, rules, funded * 1.046, nxt.replace(day=30))
    s = M.account_step(st, rules, funded * 1.046 * 0.94, nxt.replace(day=30))   # -6% in one day: rule broken
    assert s["phase"] == 0 and s["flatten"] and st.get("failed") == 1
    assert M.State(tmp_path / "s.db").get("failed") == 1                  # survives a restart


def test_policy_default_and_tables():
    assert M.Policy().budget(0, 0.0, 0.0) == M.DEFAULT_BUDGET
    x, d = np.arange(-0.10, 0.081, 0.01), np.arange(-0.03, 0.031, 0.01)
    risk = np.outer(np.linspace(0.001, 0.006, len(x)), np.ones(len(d)))
    p = M.Policy(0.006, {"b0_x": x, "b0_d": d, "b0_risk": risk, "h_x": x, "h_risk": risk[:, 0]})
    assert p.budget(0, -0.5, 0.0) == 0.001 and p.budget(0, 0.5, 0.0) == 0.006 and p.budget(2, 0.5, 0.0) == 0.006


def test_rollover_window():
    assert M.in_rollover(NOW.replace(hour=22)) and not M.in_rollover(NOW)


class _Mt5:
    SYMBOL_TRADE_MODE_FULL = 4

    def __init__(self, missing: str) -> None:
        self.missing = missing

    def symbol_info(self, sym):
        from types import SimpleNamespace
        return SimpleNamespace(trade_contract_size=100.0, volume_step=0.01, volume_min=0.01, volume_max=100.0, spread=10, trade_mode=4)

    def symbol_info_tick(self, sym):
        from types import SimpleNamespace
        return None if sym == self.missing else SimpleNamespace(ask=2000.0, bid=1999.5)


class _Terminal:
    def __init__(self, missing: str) -> None:
        self.mt5 = _Mt5(missing)

    def equity(self) -> float:
        return 100_000.0

    def bars(self, sym: str) -> pd.DataFrame:
        return bars(-0.003).assign(spread=10)

    def held(self, sym: str):
        return 0.0, []


def test_a_symbol_without_data_keeps_the_day_open_for_a_retry(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "in_rollover", lambda now: False)
    rules, pol = M.load_rules("padrao"), M.Policy()
    st = M.State(tmp_path / "a.db")
    M.run_once(_Terminal(missing="XAGUSD"), st, rules, pol, live=True)
    assert st.get("rebalanced") != st.get("day")              # silver was not read: try again on the next pass
    st2 = M.State(tmp_path / "b.db")
    M.run_once(_Terminal(missing=""), st2, rules, pol, live=True)
    assert st2.get("rebalanced") == st2.get("day")
