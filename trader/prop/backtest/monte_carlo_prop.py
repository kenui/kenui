"""Prop-firm replay and Monte Carlo (V3+).

`replay` walks many accounts in parallel through a sequence of trades and applies the firm's
rules plus the version's controller: Phase 1 (+8%), Phase 2 (+5%), then 12 months funded with
payouts. Daily and total limits are checked against the worst open result of each trade (MAE).
`monte_carlo` feeds it 10,000 sequences from a stationary block bootstrap (blocks of random
length, 6 trades on average) of the out-of-sample trades, which keeps real losing streaks.
`history` replays the real order once, restarting a fresh challenge after every pass or fail.

Simplifications: trades are booked one at a time in exit order (overlapping positions are
handled on the signal side by the open-risk cap); the tick guard is assumed to liquidate 5%
beyond the daily kill level, so a daily breach needs a larger gap than the data can show.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import numpy as np

from prop.backtest.selection import Trades
from prop.config.quant import Q
from prop.risk.position_sizer import risk_from_probability
from prop.risk.prop_firm_controller import Controller

ALIVE, FAIL_DAILY, FAIL_TOTAL, HALTED, FINISHED = 0, 1, 2, 3, 4


def bootstrap_indices(n: int, paths: int, steps: int, mean_block: int, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Stationary bootstrap (Politis-Romano): each step continues the block or jumps anywhere."""
    jump = rng.random((paths, steps)) < 1.0 / mean_block
    jump[:, 0] = True
    fresh = rng.integers(0, n, (paths, steps), dtype=np.int32)
    idx = np.empty((paths, steps), np.int32)
    idx[:, 0] = fresh[:, 0]
    for j in range(1, steps):
        idx[:, j] = np.where(jump[:, j], fresh[:, j], (idx[:, j - 1] + 1) % n)
    return idx, jump


def replay(tr: Trades, idx: np.ndarray, jump: np.ndarray | None, cfg: Controller, cycle: bool = False,
           record_paths: int = 0) -> dict:
    """Run every row of `idx` (one account per row). `cycle=True` restarts Phase 1 after each
    pass or fail instead of moving on (used for the historical order)."""
    P, T = idx.shape
    t1, t2 = Q.phase1_target, Q.phase2_target
    x = np.zeros(P); day = np.zeros(P); status = np.zeros(P, np.int8); phase = np.zeros(P, np.int8)
    losses = np.zeros(P, np.int16); locked = np.zeros(P, bool); recov = np.zeros(P, bool)
    tdays = np.zeros(P); cal = np.zeros(P); since_pay = np.zeros(P); funded_cal = np.zeros(P)
    paid = np.zeros(P); n_pay = np.zeros(P, np.int32)
    p1_tdays = np.full(P, np.nan); p1_cal = np.full(P, np.nan); app_tdays = np.full(P, np.nan); app_cal = np.full(P, np.nan)
    fail_phase = np.full(P, -1, np.int8)
    passes = np.zeros(P, np.int32); fails = np.zeros(P, np.int32)
    pnl_hist = np.zeros(T) if P == 1 else None
    xpath = np.full((min(record_paths, P), T + 1), np.nan)
    xpath[:, 0] = 0.0
    rows = np.arange(P)

    for j in range(T):
        t = idx[:, j]
        alive = status == ALIVE
        nd = tr.new_day[t] if jump is None else (tr.new_day[t] | jump[:, j])
        if j == 0:
            nd = np.ones(P, bool)
        day[nd] = 0.0; losses[nd] = 0; locked[nd] = False
        tdays += nd & alive
        g = np.where(alive, tr.gap[t], 0.0)
        cal += g
        funded = phase == 2
        since_pay += np.where(funded, g, 0.0); funded_cal += np.where(funded, g, 0.0)
        target = np.where(phase == 0, t1, t2)
        evalp = ~funded

        final = cfg.zones & evalp & (x >= target * 5.5 / 8.0)
        lock = cfg.lockin & evalp & (x >= cfg.lockin_progress * target)
        if cfg.zones:
            recov = (recov | (x < -0.03)) & ~(x > -0.015)
        thr = cfg.threshold + cfg.threshold_boost * (final | lock)
        take = alive & ~locked & (tr.score[t] >= thr)

        if cfg.sizing == "fixed":
            f = np.full(P, cfg.risk_hi)
        elif cfg.sizing == "prob":
            f = risk_from_probability(tr.p[t], cfg.threshold, cfg.risk_lo, cfg.risk_hi)
        else:
            f = np.where(phase == 0, cfg.barrier[0].lookup(x, day), cfg.barrier[1].lookup(x, day))
        if cfg.lockin:
            f = np.where(lock, np.minimum(f, cfg.lockin_risk), f)
        if cfg.zones:
            f = np.where(recov & evalp, cfg.recovery_risk, f)
        if cfg.funded == "fixed":
            f = np.where(funded, cfg.funded_risk, f)
        elif cfg.funded == "harvest":
            f = np.where(funded, cfg.harvest.lookup(x), f)
        if cfg.halve_after_losses:
            f = np.where(losses >= cfg.halve_after_losses, f * 0.5, f)
        f = f * tr.mult[t]
        if cfg.cap_to_kill:
            room = cfg.daily_kill + day
            take &= room > 0.0005
            f = np.minimum(f, np.maximum(room, 0.0))
        f = np.where(take, f, 0.0)

        arm = np.where(final, 1, tr.arm[t])           # final stretch: short 0.9R target
        r, mae = tr.R[t, arm], tr.MAE[t, arm]
        pnl, low = f * r, f * np.minimum(mae, r)
        killed = take & (day + low <= -cfg.daily_kill)
        pnl = np.where(killed, -cfg.daily_kill * 1.05 - day, pnl)
        low = np.where(killed, pnl, low)
        breach_d = take & (day + low <= -Q.daily_dd_limit)
        breach_t = take & (x + low <= -Q.max_dd_limit)
        x += pnl; day += pnl
        losses = np.where(take & (pnl < 0), losses + 1, np.where(take & (pnl > 0), 0, losses))
        locked |= killed | (day <= -cfg.daily_kill)
        if cfg.consistency:
            locked |= funded & (day >= cfg.consistency * np.maximum(x, 0.03))
        if pnl_hist is not None:
            pnl_hist[j] = pnl[0]

        failed = alive & (breach_d | breach_t)
        halted = alive & ~failed & evalp & (x <= -(cfg.max_dd_lock or np.inf))
        passed = alive & ~failed & ~halted & evalp & (x >= target)
        if cycle:
            done = failed | halted | passed
            passes += passed; fails += failed | halted
            x[done] = 0.0; day[done] = 0.0; recov[done] = False; locked[done] = False
        else:
            status[failed & breach_d] = FAIL_DAILY
            status[failed & ~breach_d] = FAIL_TOTAL
            status[halted] = HALTED
            fail_phase[failed | halted] = phase[failed | halted]
            p1 = passed & (phase == 0)
            p2 = passed & (phase == 1)
            p1_tdays[p1], p1_cal[p1] = tdays[p1], cal[p1]
            app_tdays[p2], app_cal[p2] = tdays[p2], cal[p2]
            phase[p1], phase[p2] = 1, 2
            x[passed] = 0.0; day[passed] = 0.0; recov[passed] = False
            since_pay[p2] = 0.0; funded_cal[p2] = 0.0
            # funded account: payouts and the 12-month horizon
            live = (status == ALIVE) & (phase == 2) & ~p2
            due = live & (x > 0) & ((since_pay >= 14.0) if cfg.payout == "periodic" else (x >= Q.payout_trigger))
            end = live & (funded_cal >= 365.0)
            pay = due | (end & (x > 0))
            paid[pay] += Q.profit_split * x[pay]; n_pay[pay] += 1
            x[pay] = 0.0; since_pay[pay] = 0.0
            status[end] = FINISHED
        if len(xpath):
            k = len(xpath)
            xpath[:, j + 1] = np.where((phase[:k] == 0) & (status[:k] == ALIVE), x[:k], np.nan)
            just = (passed | failed | halted)[:k] if not cycle else np.zeros(k, bool)
            xpath[just, j + 1] = np.where(passed[:k][just], t1, (x[:k] + 0)[just])
    _ = rows
    return dict(status=status, phase=phase, paid=paid, n_pay=n_pay, p1_tdays=p1_tdays, p1_cal=p1_cal,
                app_tdays=app_tdays, app_cal=app_cal, fail_phase=fail_phase, passes=passes, fails=fails,
                pnl_hist=pnl_hist, xpath=xpath, x=x)


@dataclass
class McStats:
    name: str
    trades: int
    per_year: float
    pass_p1: float
    pass_both: float
    fail_daily: float        # during the evaluation
    fail_total: float
    halted: float
    undecided: float
    days_to_funded: float    # median trading days, both phases
    cal_days_to_funded: float
    funded_1y: float         # approved in both phases within 12 calendar months
    survive_12m: float       # of the funded accounts
    got_payout: float        # of all attempts
    mean_payout_usd: float   # over all attempts, 12 months
    ev_usd: float

    def row(self) -> dict:
        pct = lambda v: round(100 * v, 1)  # noqa: E731
        return {"versao": self.name, "trades_OOS": self.trades, "trades_ano": round(self.per_year),
                "passa_F1_%": pct(self.pass_p1), "passa_F1+F2_%": pct(self.pass_both),
                "viola_diario_%": pct(self.fail_daily), "viola_total_%": pct(self.fail_total),
                "trava_6%_%": pct(self.halted), "indefinido_%": pct(self.undecided),
                "dias_op_ate_aprovar": round(self.days_to_funded, 0) if np.isfinite(self.days_to_funded) else np.nan,
                "dias_corridos": round(self.cal_days_to_funded, 0) if np.isfinite(self.cal_days_to_funded) else np.nan,
                "aprovado_em_12m_%": pct(self.funded_1y),
                "sobrevive_12m_%": pct(self.survive_12m), "recebe_saque_%": pct(self.got_payout),
                "saques_12m_usd": round(self.mean_payout_usd, 1), "EV_usd": round(self.ev_usd, 1)}


def monte_carlo(tr: Trades, cfg: Controller, paths: int = Q.mc_paths, seed: int = Q.seed,
                record_paths: int = 0) -> tuple[McStats, dict]:
    """Full journey: Phase 1 -> Phase 2 -> 12 months funded."""
    if len(tr) < 30:
        nan = float("nan")
        return McStats(cfg.name, len(tr), tr.per_year() if len(tr) else 0.0, 0, 0, 0, 0, 0, 1.0, nan, nan, 0, 0, 0, 0.0,
                       -Q.challenge_fee), {}
    rng = np.random.default_rng(seed)
    steps = int(min(max(tr.per_year() * 4.0, 400), 6000))   # about 4 years of trades per account
    idx, jump = bootstrap_indices(len(tr), paths, steps, Q.mc_block, rng)
    out = replay(tr, idx, jump, cfg, record_paths=record_paths)
    st, ph = out["status"], out["phase"]
    funded = np.isfinite(out["app_tdays"])
    in_eval_fail = out["fail_phase"] < 2
    usd = out["paid"] * Q.account_size
    got = out["n_pay"] > 0
    ev = usd + np.where(got, Q.challenge_fee, 0.0) - Q.challenge_fee    # fee refunded with the first payout
    stats = McStats(
        cfg.name, len(tr), tr.per_year(),
        pass_p1=float(np.isfinite(out["p1_tdays"]).mean()), pass_both=float(funded.mean()),
        fail_daily=float(((st == FAIL_DAILY) & in_eval_fail & (out["fail_phase"] >= 0)).mean()),
        fail_total=float(((st == FAIL_TOTAL) & in_eval_fail & (out["fail_phase"] >= 0)).mean()),
        halted=float((st == HALTED).mean()),
        undecided=float(((st == ALIVE) & (ph < 2)).mean()),
        days_to_funded=float(np.nanmedian(out["app_tdays"])) if funded.any() else float("nan"),
        cal_days_to_funded=float(np.nanmedian(out["app_cal"])) if funded.any() else float("nan"),
        funded_1y=float((out["app_cal"] <= 365.0).mean()),
        survive_12m=float(((st == FINISHED) | ((st == ALIVE) & (ph == 2)))[funded].mean()) if funded.any() else 0.0,
        got_payout=float(got.mean()), mean_payout_usd=float(usd.mean()), ev_usd=float(ev.mean()))
    return stats, out


def history(tr: Trades, cfg: Controller) -> dict:
    """Real order, one account at a time: metrics of the out-of-sample run."""
    n = len(tr)
    if n == 0:
        return {"versao": cfg.name, "trades": 0}
    out = replay(tr, np.arange(n, dtype=np.int32)[None, :], None, cfg, cycle=True)
    pnl = out["pnl_hist"]
    taken = pnl != 0
    curve = np.cumsum(pnl)
    dd = (curve - np.maximum.accumulate(np.maximum(curve, 0))).min()
    days = np.cumsum(tr.new_day) - 1
    daily = np.bincount(days, weights=pnl)
    span_years = max(tr.gap.sum() / 365.0, 1e-9)
    all_days = np.zeros(max(int(span_years * 252), len(daily)))
    all_days[:len(daily)] = daily
    sharpe = all_days.mean() / all_days.std() * np.sqrt(252) if all_days.std() > 0 else 0.0
    gw, gl = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    return {"versao": cfg.name, "trades": int(taken.sum()), "retorno_%": round(100 * curve[-1], 2),
            "profit_factor": round(gw / gl, 2) if gl > 0 else float("nan"), "sharpe": round(float(sharpe), 2),
            "dd_max_%": round(100 * float(dd), 2), "acerto_%": round(100 * float((pnl[taken] > 0).mean()), 1) if taken.any() else 0.0,
            "aprovacoes_F1": int(out["passes"][0]), "reprovacoes": int(out["fails"][0]),
            "curve": curve, "time": tr.time, "daily": all_days}


def rolling_starts(tr: Trades, cfg: Controller, min_trades_left: int = 0) -> dict:
    """Real order, one challenge started at every trade of the history (no resampling).
    Accounts that run out of history before a decision count as undecided."""
    n = len(tr)
    pad = dataclasses.replace(
        tr, R=np.vstack([tr.R, np.zeros((1, tr.R.shape[1]))]), MAE=np.vstack([tr.MAE, np.zeros((1, tr.MAE.shape[1]))]),
        arm=np.r_[tr.arm, 0], mult=np.r_[tr.mult, 0.0], p=np.r_[tr.p, 0.5], score=np.r_[tr.score, -np.inf],
        new_day=np.r_[tr.new_day, False], gap=np.r_[tr.gap, 0.0], y=np.r_[tr.y, 0])
    starts = np.arange(n - min_trades_left)
    idx = np.minimum(starts[:, None] + np.arange(n)[None, :], n).astype(np.int32)
    out = replay(pad, idx, None, cfg)
    funded = np.isfinite(out["app_cal"])
    failed = np.isin(out["status"], (FAIL_DAILY, FAIL_TOTAL, HALTED)) & (out["fail_phase"] < 2)
    pct = lambda v: round(100 * float(np.mean(v)), 1)  # noqa: E731
    return {"inicios": len(starts), "passa_F1_%": pct(np.isfinite(out["p1_cal"])), "passa_F1+F2_%": pct(funded),
            "reprova_%": pct(failed), "indefinido_%": pct(~funded & ~failed),
            "dias_corridos_F1": float(np.nanmedian(out["p1_cal"])) if np.isfinite(out["p1_cal"]).any() else float("nan"),
            "dias_corridos_F1+F2": float(np.nanmedian(out["app_cal"])) if funded.any() else float("nan"),
            "aprovado_em_12m_%": pct(out["app_cal"] <= 365.0)}
