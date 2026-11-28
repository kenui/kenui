"""Front 3 demo robot: the rule and the cost arithmetic, without MetaTrader."""
from datetime import datetime, time, timedelta
from types import SimpleNamespace

import pandas as pd

from prop.live import ny_open_demo as N

DAY = datetime(2026, 11, 30, tzinfo=N.NY)


def _bars(extra=()):
    rng = [(DAY.replace(hour=9) + timedelta(minutes=i), 101.0 + (i == 20), 99.0 - (i == 40)) for i in range(60)]
    return [(DAY.replace(hour=8, minute=59), 150.0, 50.0)] + rng + list(extra)


def test_range_uses_only_nine_to_ten_and_flags_a_missed_break():
    now = DAY.replace(hour=10, minute=0, second=5)
    assert N.opening_range(_bars(), DAY.date(), now) == (102.0, 98.0, False)
    forming = (DAY.replace(hour=10), 103.0, 100.0)             # the bar still forming does not count as missed
    assert N.opening_range(_bars([forming]), DAY.date(), now)[2] is False
    assert N.opening_range(_bars([forming]), DAY.date(), now + timedelta(minutes=5))[2] is True
    assert N.opening_range(_bars()[:20], DAY.date(), now) is None


def test_decisions_follow_the_frozen_rule():
    d = {**N.new_day("2026-11-30"), "estado": "armado", "topo": 102.0, "fundo": 98.0}
    assert N.decide(d, time(10, 1), 100.0) is None
    assert N.decide(d, time(10, 1), 102.0) == "compra"
    assert N.decide(d, time(10, 1), 98.0) == "venda"
    assert N.decide(d, time(15, 0), 103.0) == "fim"
    long = {**d, "estado": "aberto", "lado": 1}
    assert N.decide(long, time(11, 0), 98.0) == "sair:stop"
    assert N.decide(long, time(11, 0), 101.0) is None
    assert N.decide(long, time(15, 0), 101.0) == "sair:hora"
    assert N.decide({**long, "lado": -1}, time(11, 0), 102.0) == "sair:stop"
    assert N.decide({**d, "estado": "fim"}, time(11, 0), 200.0) is None


def test_cost_is_the_fill_against_the_backtest_price():
    assert round(N.side_cost(True, 100.0, 100.02), 6) == 2.0
    assert round(N.side_cost(False, 100.0, 99.99), 6) == 1.0
    d = {"data": "2026-11-30", "simbolo": "US500", "simulado": 1, "lado": 1, "topo": 100.0, "fundo": 99.0, "hora_entrada": "10:05:00",
         "ref_entrada": 100.0, "preco_entrada": 100.02, "spread_entrada": 0.02}
    r = N.close_row(d, "hora", 101.0, 101.0, 0.02, "15:00:00")
    assert (r["custo_entrada_pb"], r["custo_saida_pb"], r["bruto_pb"]) == (2.0, 0.0, 100.0)
    assert abs(r["liquido_pb"] - 98.0) < 0.05
    s = N.close_row({**d, "lado": -1, "ref_entrada": 99.0, "preco_entrada": 98.99}, "stop", 100.0, 100.03, 0.03, "11:00:00")
    assert s["custo_entrada_pb"] > 0 and s["custo_saida_pb"] > 0 and s["liquido_pb"] < s["bruto_pb"] < 0


class _Mt5:
    ACCOUNT_TRADE_MODE_DEMO, ACCOUNT_MARGIN_MODE_RETAIL_HEDGING, SYMBOL_TRADE_MODE_FULL, TIMEFRAME_M1 = 0, 2, 4, 1

    def initialize(self):
        return True

    def account_info(self):
        return SimpleNamespace(trade_mode=1, margin_mode=2, server="Real")      # NOT a demo account

    def symbol_select(self, s, on):
        return True

    def symbol_info(self, s):
        return SimpleNamespace(trade_mode=4, volume_min=0.1, digits=2, filling_mode=1)

    def positions_get(self, symbol=None):
        return []

    def order_send(self, req):
        raise AssertionError("no order may reach an account that is not demo")


def test_a_real_account_is_only_simulated_and_the_trade_is_journaled(tmp_path, monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "MetaTrader5", _Mt5())
    r = N.Robot(tmp_path, live=True)
    assert not r.live and not r.real("US500")
    r.days["US500"] = {**N.new_day("2026-11-30"), "estado": "armado", "topo": 102.0, "fundo": 98.0}
    tick = lambda bid: SimpleNamespace(bid=bid, ask=bid + 0.5, time=0, time_msc=0)  # noqa: E731
    r.handle("US500", tick(102.2), DAY.replace(hour=10, minute=30))
    assert r.days["US500"]["estado"] == "aberto" and r.days["US500"]["preco_entrada"] == 102.7
    r.handle("US500", tick(104.0), DAY.replace(hour=15, minute=0))
    t = pd.read_csv(tmp_path / "trades.csv")
    assert len(t) == 1 and t["motivo_saida"][0] == "hora" and t["simulado"][0] == 1
    assert abs(t["custo_entrada_pb"][0] - 1e4 * 0.7 / 102.0) < 0.01 and t["custo_saida_pb"][0] == 0.0
    assert "US500" in N.report(tmp_path)
    assert N.Robot(tmp_path, live=False).days["US500"]["estado"] == "fim"       # the state survives a restart


def test_replay_of_one_session_on_ticks():
    import numpy as np
    hours = np.concatenate([np.linspace(9.0, 9.99, 200), np.linspace(10.0, 14.99, 500), np.linspace(15.0, 15.1, 10)])
    bid = np.full(len(hours), 100.0)
    bid[50], bid[120] = 101.0, 99.0                              # the range: 99 to 101
    bid[300:] = 101.5                                           # breaks the top after 10:00 and stays there
    bid[-10:] = 103.0
    r = N.replay_day("2026-11-27", "US500", hours, bid, bid + 0.2)
    assert (r["lado"], r["motivo_saida"], r["ref_entrada"], r["preco_entrada"]) == (1, "hora", 101.0, 101.7)
    assert r["preco_saida"] == 103.0 and r["custo_saida_pb"] == 0.0 and r["custo_entrada_pb"] > 0
    bid[400:] = 98.5                                            # comes back through the bottom: stopped
    s = N.replay_day("2026-11-27", "US500", hours, bid, bid + 0.2)
    assert s["motivo_saida"] == "stop" and s["ref_saida"] == 99.0 and s["liquido_pb"] < 0
    assert N.replay_day("2026-11-27", "US500", hours, np.full(len(hours), 100.0), np.full(len(hours), 100.2)) is None
