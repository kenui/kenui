"""Checks for the Quant V5 layer: signatures, adaptive conformal bound, state store, bridge,
prop-firm replay and the overfitting statistics."""
import json

import numpy as np
import pandas as pd

from prop.backtest import monte_carlo_prop as mcp
from prop.backtest.selection import to_trades
from prop.execution import mt5_socket_bridge as br
from prop.execution.contextual_bandit import LinUCB
from prop.extensions.atemporal_aci import AdaptiveConformalController, Order3PathSignatureExtractor
from prop.models.conformal_meta_ensemble import ConformalMetaEnsemble
from prop.persistence.state_store import StateStore
from prop.risk.drift_monitor import CusumBrier
from prop.risk.prop_firm_controller import Controller
from prop.validation import cpcv_dsr_and_mc as val


def price_bars(n=200, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2026-01-05", periods=n, freq="1h", tz="UTC")
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.003, n)))
    return pd.DataFrame({"open": close, "high": close, "low": close, "close": close,
                         "volume": rng.uniform(1, 5, n)}, index=idx)


def fake_trades(r, per_day=1):
    n = len(r)
    exit_time = pd.date_range("2026-01-05 12:00", periods=n, freq=f"{24 // per_day}h", tz="UTC")
    df = pd.DataFrame({"entry_time": exit_time - pd.Timedelta(hours=2), "exit_time": exit_time, "asset": "X",
                       "arm": "arm1", "arm_i": 2, "mult": 1.0, "p": 0.6, "score": 1.0, "y": (np.asarray(r) > 0).astype(int)})
    for k in ("plain", "arm0", "arm1", "arm2"):
        df[f"r_{k}"], df[f"mae_{k}"] = r, np.minimum(r, 0.0)
    return to_trades(df)


def test_signature_has_41_features_and_no_lookahead():
    df = price_bars()
    ex = Order3PathSignatureExtractor(window=24)
    full = ex.transform(df)
    assert full.shape == (200, 41)
    assert full.iloc[:24].isna().all().all() and full.iloc[24:].notna().all().all()
    cut = ex.transform(df.iloc[:120])                 # the future is removed: past values must not move
    np.testing.assert_allclose(full.iloc[:120].to_numpy(), cut.to_numpy(), equal_nan=True)
    # shuffle identity of signatures: S1_i * S1_j = S2_ij + S2_ji
    row = full.iloc[100]
    assert abs(row["sig1_t"] * row["sig1_p"] - (row["sig2_tp"] + row["sig2_pt"])) < 1e-9


def test_aci_tightens_after_misses_and_survives_a_restart():
    rng = np.random.default_rng(1)
    p = rng.uniform(0.3, 0.8, 400)
    aci = AdaptiveConformalController(alpha_target=0.10, gamma=0.025, alpha_min=0.01, alpha_max=0.30)
    aci.fit_calibration(p, (rng.random(400) < p - 0.1).astype(int))     # an over-confident model
    start = float(aci.predict_lower_bound(0.7)[0])
    assert start < 0.7
    for _ in range(60):                                                  # every authorised trade loses
        aci.update_on_trade_close(0.7, 0)
    assert aci.alpha < 0.10 and aci.alpha >= 0.01
    assert float(aci.predict_lower_bound(0.7)[0]) <= start
    clone = AdaptiveConformalController.from_dict(json.loads(json.dumps(aci.to_dict())))
    assert clone.alpha == aci.alpha
    assert float(clone.predict_lower_bound(0.55)[0]) == float(aci.predict_lower_bound(0.55)[0])
    for _ in range(300):                                                 # wins bring alpha back up, inside the cap
        aci.update_on_trade_close(0.7, 1)
    assert 0.10 < aci.alpha <= 0.30


def test_state_store_commits_trade_and_learners_together(tmp_path):
    store = StateStore(tmp_path / "s.db")
    assert store.db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    store.open_trade("t1", "XAUUSD", 1, 0.005, 0.62, 2, [1.0, 0.2, 0.5, 0.3, 0.1, 0.0, 1.0])
    try:
        with store.transaction() as db:
            db.execute("UPDATE trade_log SET result_r=1.0 WHERE id='t1'")
            raise RuntimeError("crash in the middle")
    except RuntimeError:
        pass
    assert store.db.execute("SELECT result_r FROM trade_log WHERE id='t1'").fetchone()[0] is None
    aci = AdaptiveConformalController()
    aci.alpha = 0.07
    store.close_trade("t1", 0.9, -0.2, 1, {"aci": aci.to_dict()})
    store.close()
    again = StateStore(tmp_path / "s.db")
    restored, _, _ = again.restore_learners(AdaptiveConformalController)
    assert restored.alpha == 0.07
    assert again.db.execute("SELECT outcome FROM trade_log WHERE id='t1'").fetchone()[0] == 1


def test_bridge_close_updates_aci_bandit_and_cusum(tmp_path):
    store = StateStore(tmp_path / "b.db")
    bridge = br.Mt5SocketBridge(store, "segredo")
    ens = ConformalMetaEnsemble(adaptive=True)
    bandit, cusum = LinUCB(7), CusumBrier()
    bridge.learners = {"ensemble": ens, "bandit": bandit, "cusum": cusum}
    store.open_trade("a", "EURUSD", 1, 0.005, 0.6, 2, [1.0, 0.2, 0.5, 0.3, 0.1, 0.0, 1.0])
    bridge.handle({"type": "closed", "id": "a", "result_r": -1.0, "mae_r": -1.0})
    assert ens.aci.n_updates == 1
    assert store.load("aci")["n_updates"] == 1 and store.load("linucb") and store.load("cusum")
    line = br.signed_line({"type": "order", "symbol": "EURUSD", "risk_pct": 0.5}, "segredo")
    msg = json.loads(line)
    assert msg["sig"] == br.sign(msg, "segredo") and br.sign(msg, "outro") != msg["sig"]


def test_replay_passes_winners_fails_losers_and_respects_the_daily_kill():
    fixed = Controller("t", 0.0, "fixed", 0.01, 0.01, daily_kill=0.03)
    win = mcp.monte_carlo(fake_trades(np.full(60, 1.0)), fixed, paths=200)[0]
    assert win.pass_both == 1.0 and win.fail_total == 0.0 and win.ev_usd > 0
    lose = mcp.monte_carlo(fake_trades(np.full(60, -1.0)), fixed, paths=200)[0]
    assert lose.pass_p1 == 0.0 and lose.fail_total == 1.0 and lose.ev_usd == -50.0
    # 5 losers of 1% in the same day: the kill at 3% must stop the day before the 5% limit
    crowded = mcp.monte_carlo(fake_trades(np.full(120, -1.0), per_day=6), fixed, paths=200)[0]
    assert crowded.fail_daily == 0.0 and crowded.fail_total == 1.0


def test_stationary_bootstrap_keeps_blocks():
    idx, jump = mcp.bootstrap_indices(100, 50, 400, 6, np.random.default_rng(0))
    cont = ~jump[:, 1:]
    assert ((idx[:, 1:] - idx[:, :-1]) % 100 == 1)[cont].all()
    assert 0.10 < jump[:, 1:].mean() < 0.24


def test_pbo_and_dsr_separate_noise_from_skill():
    rng = np.random.default_rng(3)
    noise = rng.normal(0, 0.01, (600, 30))
    many = [val.pbo_cscv(np.random.default_rng(k).normal(0, 0.01, (600, 30)))["pbo"] for k in range(6)]
    assert 0.3 < np.mean(many) < 0.7                                 # best in-sample is a coin flip out of sample
    skilled = noise.copy()
    skilled[:, 0] += 0.004
    assert val.pbo_cscv(skilled)["pbo"] < 0.1
    sr_var = float(np.var([val.sharpe(c) for c in noise.T]))
    best = noise[:, int(np.argmax(noise.mean(axis=0)))]
    assert val.deflated_sharpe(best, 30, sr_var) < 0.9               # the luckiest of 30 is not significant
    assert val.deflated_sharpe(skilled[:, 0], 30, sr_var) > 0.99


# ---- paper bot of the listing short ------------------------------------------------------------
class FakeExchange:
    """A coin NEWUSDT is listed at hour 2; its perpetual follows the given hourly closes."""

    def __init__(self, closes, perp=True):
        self.t0 = pd.Timestamp("2026-03-02 00:00", tz="UTC")
        idx = pd.date_range(self.t0 + pd.Timedelta(hours=2), periods=len(closes), freq="1h")
        c = np.asarray(closes, float)
        o = np.r_[c[0], c[:-1]]
        self.k = pd.DataFrame({"open": o, "high": np.maximum(o, c), "low": np.minimum(o, c), "close": c}, index=idx)
        self.now, self.perp = self.t0, perp

    def spot_symbols(self):
        return {"BTCUSDT"} | ({"NEWUSDT"} if self.now >= self.t0 + pd.Timedelta(hours=2) else set())

    def perp_symbols(self):
        return {"BTCUSDT", "NEWUSDT"} if self.perp else {"BTCUSDT"}

    def hourly(self, perp, start):
        return self.k[(self.k.index >= start.floor("h")) & (self.k.index < self.now)]

    def funding(self, perp, start, end):
        return 0.0


def run_paper(tmp_path, closes, hours, perp=True):
    from prop.live import listing_paper as lp
    from prop.risk.bellman_barrier_controller import X_STEP, D_STEP, BarrierPolicy
    from prop.risk.dual_bellman_solver import HarvestPolicy
    xg, dg = np.arange(-0.10, 0.08 + X_STEP / 2, X_STEP), np.arange(-0.05, 0.05 + D_STEP / 2, D_STEP)
    flat = BarrierPolicy(xg, dg, np.full((len(xg), len(dg)), 0.01), np.zeros((len(xg), len(dg))), 0.08)
    harvest = HarvestPolicy(xg, np.full(len(xg), 0.005), np.zeros(len(xg)), 0.045)
    api = FakeExchange(closes, perp)
    store = StateStore(tmp_path / "p.db")
    bot = lp.ListingPaper(store, api, {0: flat, 1: flat}, harvest)
    for h in range(hours):
        api.now = api.t0 + pd.Timedelta(hours=h)
        if h == 40:                                   # restart in the middle: state must come back from SQLite
            bot = lp.ListingPaper(store, api, {0: flat, 1: flat}, harvest)
        bot.step(api.now)
    return bot, lp


def test_paper_bot_shorts_24h_after_listing_and_closes_after_7_days(tmp_path):
    closes = np.r_[np.full(30, 100.0), np.full(200, 85.0)]         # falls 15% after the entry
    bot, lp = run_paper(tmp_path, closes, 2 + 24 + 168 + 3)
    assert len(bot.closed) == 1 and not bot.open and not bot.pending
    t = bot.closed[0]
    assert t["reason"] == "tempo" and t["entry"] == 100.0
    assert pd.Timestamp(t["entry_time"]) == bot.api.t0 + pd.Timedelta(hours=26)
    expect_r = (0.15 - 2 * lp.COST) / lp.STOP
    assert abs(t["r"] - expect_r) < 1e-9 and abs(bot.account.x - 0.01 * expect_r) < 1e-9
    assert "ROBO DE LISTAGEM" in lp.report(bot.store)


def test_paper_bot_stop_costs_one_r_and_missing_perp_is_skipped(tmp_path):
    closes = np.r_[np.full(30, 100.0), 140.0, np.full(200, 140.0)]  # pumps 40% through the 30% stop
    bot, lp = run_paper(tmp_path, closes, 2 + 24 + 12)
    t = bot.closed[0]
    assert t["reason"] == "stop" and t["exit"] == 130.0
    assert abs(t["r"] - (-0.30 - 2 * lp.COST) / lp.STOP) < 1e-9
    none, _ = run_paper(tmp_path / "x", closes, 2 + 24 + 12, perp=False)
    assert not none.closed and not none.open and none.skipped[0][2] == "sem contrato perpetuo"


def test_challenge_account_walks_through_the_phases():
    from prop.live.challenge_account import ChallengeAccount
    a = ChallengeAccount()
    a.new_day("2026-01-05")
    assert a.book(0.081, "t") == "Fase 1 aprovada" and a.phase == 1 and a.x == 0.0
    a.new_day("2026-01-06")
    assert a.book(0.05, "t").startswith("Fase 2 aprovada") and a.phase == 2
    a.new_day("2026-01-07")
    assert a.book(0.05, "t") == "saque de US$ 400" and abs(a.payouts_usd - 400.0) < 1e-6
    a.new_day("2026-01-08")
    a.book(-0.033, "t")
    assert a.day_locked                                             # daily kill: no more trades today
    for d in range(9, 12):
        a.new_day(f"2026-01-{d:02d}")
        a.book(-0.03, "t")
    assert a.failed == 1 and a.phase == 0 and a.attempts == 2
    assert ChallengeAccount.from_dict(json.loads(json.dumps(a.to_dict()))).to_dict() == a.to_dict()
