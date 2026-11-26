"""Monte Carlo of the prop challenge: phase 1, phase 2, then the funded account.

Works on the trade list of a backtest (results in R = multiples of the money risked), grouped
by trading day. Two tests:
  * `bootstrap`: thousands of synthetic futures built from blocks of real days;
  * `rolling`: start the challenge on every real day of the history, in the real order.
The risk-manager rules (daily lock, halving after two stops, win-streak boost, -6% lock) are
replayed trade by trade; the worst open loss of each trade (MAE) is used for the limits.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from prop.config.settings import SETTINGS, PropRules, RiskConfig

PASS, FAIL_DAILY, FAIL_TOTAL, HALTED, UNDECIDED = "pass", "fail_daily", "fail_total", "halted", "undecided"


def trades_by_day(trades: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp,
                  rules: PropRules = SETTINGS.rules) -> list[np.ndarray]:
    """One array of (r, mae_r) rows per weekday between start and end, in exit order."""
    tz = rules.day_timezone
    days = pd.date_range(start.tz_convert(tz).normalize(), end.tz_convert(tz).normalize(), freq="B")
    t = trades.sort_values("exit_time")
    key = t["exit_time"].dt.tz_convert(tz).dt.normalize()
    # weekend exits (crypto) are booked on the following Monday
    key = key.where(key.dt.weekday < 5, key + pd.offsets.BDay(1))
    groups = {k: g[["r", "mae_r"]].to_numpy() for k, g in t.groupby(key)}
    empty = np.empty((0, 2))
    return [groups.get(d, empty) for d in days]


def coin_flip_days(n_days: int = 3000, trades_per_day: float = 1.0, cost_r: float = 0.05,
                   seed: int = 7) -> list[np.ndarray]:
    """Benchmark with no skill: 50/50 trades of +1R / -1R, minus costs.

    Every day is included twice, once mirrored, so the pool has exactly zero edge before costs.
    """
    rng = np.random.default_rng(seed)
    out = []
    for n in rng.poisson(trades_per_day, n_days // 2):
        flips = rng.choice([1.0, -1.0], n)
        for sign in (1.0, -1.0):
            r = sign * flips - cost_r
            out.append(np.column_stack([r, np.minimum(r, -0.3)]))
    return [out[i] for i in rng.permutation(len(out))]  # mirrored days must not sit side by side


def play(days: list[np.ndarray], risk: RiskConfig, rules: PropRules, target: float | None,
         max_days: int, payout_every: int = 0) -> tuple[str, int, float]:
    """Replay one account. Returns (outcome, trading days used, profit paid out as fraction of account).

    With `target` it is an evaluation phase; with `target=None` it is the funded account and
    profits are withdrawn every `payout_every` trading days (balance goes back to the start).
    """
    bal, paid, win_streak = 1.0, 0.0, 0
    for d, day in enumerate(days[:max_days], start=1):
        day_start, locked, losses = bal, False, 0
        for r, mae in day:
            if locked:
                break
            f = risk.risk_per_trade
            if risk.halve_after_losses and losses >= risk.halve_after_losses:
                f *= 0.5
            elif win_streak >= 2:
                f *= risk.win_streak_boost
            money = bal * min(f, risk.max_risk_per_trade)
            low = bal + money * min(mae, r)
            pnl = money * r
            if risk.daily_hard_stop and low <= day_start - risk.daily_hard_stop:
                pnl, low, locked = (day_start - risk.daily_hard_stop) - bal, day_start - risk.daily_hard_stop, True
            if low <= day_start - rules.max_daily_loss:
                return FAIL_DAILY, d, paid
            if low <= 1 - rules.max_total_loss:
                return FAIL_TOTAL, d, paid
            bal += pnl
            if r < 0:
                losses, win_streak = losses + 1, 0
            else:
                losses, win_streak = 0, win_streak + 1
            if risk.max_drawdown_lock and bal <= 1 - risk.max_drawdown_lock:
                return HALTED, d, paid
            if target is not None and bal >= 1 + target:
                return PASS, max(d, rules.min_trading_days), paid
        if target is None and payout_every and d % payout_every == 0 and bal > 1:
            paid += (bal - 1) * rules.profit_split
            bal = 1.0
    return UNDECIDED, min(len(days), max_days), paid


@dataclass
class ChallengeStats:
    label: str
    paths: int
    pass_phase1: float
    fail_phase1: float
    halted_phase1: float
    undecided_phase1: float
    median_days_phase1: float
    funded: float              # passed both phases
    got_payout: float          # funded and received at least one payout
    mean_payout_usd: float     # average over ALL attempts, 6 months after funding
    value_per_attempt_usd: float  # payouts + refunded fee - fee

    def row(self) -> dict:
        pct = lambda x: round(100 * x, 1)  # noqa: E731
        return {"cenario": self.label, "passa_fase1_%": pct(self.pass_phase1),
                "reprova_%": pct(self.fail_phase1), "trava_-6%_%": pct(self.halted_phase1),
                "indefinido_%": pct(self.undecided_phase1), "dias_fase1": self.median_days_phase1,
                "conta_financiada_%": pct(self.funded), "recebe_saque_%": pct(self.got_payout),
                "saque_medio_usd": round(self.mean_payout_usd, 1),
                "valor_por_tentativa_usd": round(self.value_per_attempt_usd, 1)}


def bootstrap(days: list[np.ndarray], risk: RiskConfig, label: str, rules: PropRules = SETTINGS.rules,
              paths: int = 4000, block: int = 5, phase_days: int = 250, funded_days: int = 126,
              seed: int = 1) -> ChallengeStats:
    """Block bootstrap of real days: phase 1 -> phase 2 -> funded account for ~6 months."""
    rng = np.random.default_rng(seed)
    n = len(days)
    total = 2 * phase_days + funded_days
    payout_every = max(1, round(rules.payout_every_days * 5 / 7))
    out1: list[str] = []
    d1: list[int] = []
    funded = paid_any = 0
    payouts = value = 0.0
    for _ in range(paths):
        starts = rng.integers(0, n, total // block + 1)
        idx = ((starts[:, None] + np.arange(block)[None, :]) % n).ravel()[:total]
        seq = [days[i] for i in idx]
        o, used, _ = play(seq, risk, rules, rules.target_phase1, phase_days)
        out1.append(o)
        got = 0.0
        if o == PASS:
            d1.append(used)
            o2, used2, _ = play(seq[used:], risk, rules, rules.target_phase2, phase_days)
            if o2 == PASS:
                funded += 1
                _, _, paid = play(seq[used + used2:], risk, rules, None, funded_days, payout_every)
                got = paid * rules.account_size
                if got > 0:
                    paid_any += 1
                    got += rules.fee_usd  # fee is refunded with the first payout
        payouts += got
        value += got - rules.fee_usd
    s = pd.Series(out1)
    return ChallengeStats(label, paths, (s == PASS).mean(), s.isin([FAIL_DAILY, FAIL_TOTAL]).mean(),
                          (s == HALTED).mean(), (s == UNDECIDED).mean(),
                          float(np.median(d1)) if d1 else float("nan"), funded / paths, paid_any / paths,
                          payouts / paths, value / paths)


def rolling(days: list[np.ndarray], risk: RiskConfig, rules: PropRules = SETTINGS.rules,
            max_days: int = 250) -> dict:
    """Phase 1 started on every real day, real order, no resampling."""
    res = [play(days[s:], risk, rules, rules.target_phase1, max_days)[0]
           for s in range(max(1, len(days) - 20))]
    s = pd.Series(res)
    return {"inicios": len(s), "passa_%": round(100 * (s == PASS).mean(), 1),
            "reprova_%": round(100 * s.isin([FAIL_DAILY, FAIL_TOTAL]).mean(), 1),
            "trava_-6%_%": round(100 * (s == HALTED).mean(), 1),
            "indefinido_%": round(100 * (s == UNDECIDED).mean(), 1)}


def rolling_equity(equity: pd.Series, worst: pd.Series, day_start: pd.Series,
                   rules: PropRules = SETTINGS.rules, max_days: int = 365) -> dict:
    """Two-phase challenge started on every real day of an account-level backtest.

    Uses the bar-level equity (open positions included), so several positions losing together
    are counted against the daily and total limits. Results are scaled to the start equity.
    """
    tz = rules.day_timezone
    day = equity.index.tz_convert(tz).normalize()
    hi = equity.groupby(day).max().to_numpy()
    lo = worst.groupby(day).min().to_numpy()
    ds = day_start.groupby(day).first().to_numpy()
    close = equity.groupby(day).last().to_numpy()
    n = len(close)

    def phase(s: int, target: float) -> tuple[str, int]:
        base = close[s - 1] if s > 0 else ds[0]
        e = min(n, s + max_days)
        up = np.flatnonzero(hi[s:e] >= base * (1 + target))
        bad = np.flatnonzero((lo[s:e] <= base * (1 - rules.max_total_loss)) |
                             (lo[s:e] - ds[s:e] <= -base * rules.max_daily_loss))
        first_up = up[0] if len(up) else 10 ** 9
        first_bad = bad[0] if len(bad) else 10 ** 9
        if first_up == first_bad == 10 ** 9:
            return UNDECIDED, e - s
        return (PASS, first_up + 1) if first_up < first_bad else ("fail", first_bad + 1)

    p1, p2, d1, d2 = [], [], [], []
    for s in range(max(1, n - 30)):
        o, used = phase(s, rules.target_phase1)
        p1.append(o)
        if o == PASS:
            d1.append(used)
            o2, used2 = phase(s + used, rules.target_phase2)
            p2.append(o2)
            if o2 == PASS:
                d2.append(used + used2)
    a, b = pd.Series(p1), pd.Series(p2, dtype=object)
    return {"inicios": len(a), "passa_fase1_%": round(100 * (a == PASS).mean(), 1),
            "reprova_fase1_%": round(100 * (a == "fail").mean(), 1),
            "indefinido_fase1_%": round(100 * (a == UNDECIDED).mean(), 1),
            "dias_fase1": float(np.median(d1)) if d1 else float("nan"),
            "passa_as_duas_%": round(100 * (b == PASS).sum() / len(a), 1),
            "dias_ate_financiada": float(np.median(d2)) if d2 else float("nan")}
