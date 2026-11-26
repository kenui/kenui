"""Bybit listing bot: sizing, entry, 7-day exit, server stop and breaker, with a fake exchange."""
from datetime import datetime, timedelta, timezone

import numpy as np

from prop.live import listing_bybit as L
from prop.live.listing_paper import policies
from prop.live.mt5_trend import State, load_rules

T0 = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
INST = {"symbol": "NEWUSDT", "step": 1.0, "min": 1.0, "max": 1e9, "tick": 0.001}


class FakeBybit:
    def __init__(self):
        self.eq, self.pos, self.orders, self.px = 10_000.0, {}, [], 2.0

    def has_key(self): return True
    def equity(self): return self.eq
    def positions(self): return dict(self.pos)
    def instrument(self, symbol): return dict(INST) if symbol == "NEWUSDT" else None
    def price(self, symbol): return self.px
    def set_leverage(self, symbol, lev=3): pass

    def short(self, symbol, qty, stop):
        self.pos[symbol] = -qty
        self.orders.append(("short", symbol, qty, stop))
        return "id1"

    def cover(self, symbol, qty):
        self.pos.pop(symbol, None)
        self.orders.append(("cover", symbol, qty))
        return "id2"


def bot(tmp_path, api, spot):
    barrier, harvest = policies()
    return L.ListingBybit(State(tmp_path / "s.db"), api, load_rules("cryptofundtrader"), barrier, harvest, True, spot_symbols=lambda: set(spot))


def test_order_qty_and_stop_rounding():
    assert L.order_qty(10_000, 0.01, 2.0, INST) == 166.0            # 1% risk / 30% stop = US$ 333 notional
    assert L.order_qty(10_000, 0.01, 2.0, {**INST, "min": 500.0}) == 0.0
    assert L.round_up(2.6000001, 0.001) == 2.601
    assert L.eligible("NEWUSDT") and not L.eligible("USDCUSDT") and not L.eligible("BTCUPUSDT")


def test_entry_after_24h_then_exit_after_7_days(tmp_path):
    api, spot = FakeBybit(), {"BTCUSDT"}
    b = bot(tmp_path, api, spot)
    b.step(T0)                                                       # first run only learns the symbols
    spot |= {"NEWUSDT", "NOPERPUSDT"}
    b.step(T0 + timedelta(hours=1))
    assert set(b.st.get("pending")) == {"NEWUSDT", "NOPERPUSDT"} and not api.orders
    b.step(T0 + timedelta(hours=20))
    assert not api.orders                                            # not 24 hours yet
    out = b.step(T0 + timedelta(hours=25, minutes=5))
    kind, sym, qty, stop = api.orders[0]
    assert (kind, sym) == ("short", "NEWUSDT") and abs(stop - 2.6) < 1e-9
    risk = b.st.get("open")[0]["risk"]
    assert 0.002 <= risk <= 0.02 and qty == np.floor(10_000 * risk / 0.30 / 2.0)
    assert any("NOPERPUSDT ignorada" in m for m in out) and b.st.get("pending") == {}
    b.step(T0 + timedelta(days=5))
    assert len(api.orders) == 1
    b.step(T0 + timedelta(hours=25, minutes=10) + timedelta(days=7))
    assert api.orders[-1][0] == "cover" and b.st.get("open") == []


def test_server_stop_is_noticed_and_late_entries_are_skipped(tmp_path):
    api, spot = FakeBybit(), {"BTCUSDT"}
    b = bot(tmp_path, api, spot)
    b.step(T0)
    spot.add("NEWUSDT")
    b.step(T0 + timedelta(hours=1))
    b.step(T0 + timedelta(hours=25, minutes=5))
    api.pos.clear()                                                  # Bybit's stop closed the position
    out = b.step(T0 + timedelta(hours=30))
    assert any("saiu no stop" in m for m in out) and b.st.get("open") == [] and len(api.orders) == 1
    b.st.set(pending={"NEWUSDT": (T0 - timedelta(days=3)).isoformat()})
    out = b.step(T0 + timedelta(hours=31))
    assert any("desligado" in m for m in out) and len(api.orders) == 1


def test_breaker_closes_everything(tmp_path):
    api, spot = FakeBybit(), {"BTCUSDT"}
    b = bot(tmp_path, api, spot)
    b.step(T0)
    spot.add("NEWUSDT")
    b.step(T0 + timedelta(hours=1))
    b.step(T0 + timedelta(hours=25, minutes=5))
    api.eq = 9_690.0                                                 # -3.1% in the day: breaker at 60% of 5%
    b.step(T0 + timedelta(hours=26))
    assert api.orders[-1][0] == "cover" and b.st.get("locked") is True


def test_signature_matches_bybit_v5_format(monkeypatch):
    seen = {}
    monkeypatch.setattr(L, "_http", lambda req: seen.update(h=dict(req.header_items()), url=req.full_url) or {"retCode": 0, "result": {"list": [{"totalEquity": "5"}]}})
    monkeypatch.setattr(L.time, "time", lambda: 1700000000.0)
    assert L.Bybit(L.DEMO, "k", "s").equity() == 5.0
    import hashlib, hmac
    want = hmac.new(b"s", b"1700000000000k5000accountType=UNIFIED", hashlib.sha256).hexdigest()
    assert seen["h"]["X-bapi-sign"] == want and seen["url"].startswith("https://api-demo.bybit.com/")
