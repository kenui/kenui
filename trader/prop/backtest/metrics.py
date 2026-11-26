"""Metrics and the prop-firm verdict for one backtest."""
from __future__ import annotations

import numpy as np
import pandas as pd

from prop.backtest.engine import BacktestResult
from prop.config.settings import INSTRUMENTS, SETTINGS, Instrument, PropRules


def challenge_verdict(res: BacktestResult, rules: PropRules = SETTINGS.rules) -> str:
    """What would have happened to a challenge started on the first bar of this run."""
    init = res.initial
    eq, worst, ds = res.equity.to_numpy(), res.worst.to_numpy(), res.day_start.to_numpy()
    hit = np.flatnonzero(eq >= init * (1 + rules.target_phase1))
    daily = np.flatnonzero(worst <= ds - init * rules.max_daily_loss)
    total = np.flatnonzero(worst <= init * (1 - rules.max_total_loss))
    first = {k: (v[0] if len(v) else len(eq)) for k, v in (("pass", hit), ("daily", daily), ("total", total))}
    what = min(first, key=first.get)
    if first[what] == len(eq):
        locked = [w for _, w in res.locks if w == "max_drawdown"]
        return "travou em -6%" if locked else "sem meta"
    days = (res.equity.index[first[what]] - res.equity.index[0]).days
    return {"pass": f"PASSOU ({days}d)", "daily": f"REPROVOU diario ({days}d)",
            "total": f"REPROVOU total ({days}d)"}[what]


def max_losing_streak(pnl: np.ndarray) -> int:
    best = cur = 0
    for x in pnl:
        cur = cur + 1 if x < 0 else 0
        best = max(best, cur)
    return best


def summarize(res: BacktestResult, rules: PropRules = SETTINGS.rules,
              instruments: dict[str, Instrument] = INSTRUMENTS) -> dict:
    t, eq = res.trades, res.equity
    n = len(t)
    dd = (res.worst / eq.cummax().clip(lower=res.initial) - 1).min() if len(eq) else 0.0
    out = {"trades": n, "retorno_%": round((eq.iloc[-1] / res.initial - 1) * 100, 2) if len(eq) else 0.0,
           "dd_max_%": round(float(dd) * 100, 2)}
    if n == 0:
        return {**out, "profit_factor": float("nan"), "acerto_%": float("nan"), "expect_R": float("nan"),
                "t_stat": float("nan"), "expect_vs_custo": float("nan"), "perdas_seguidas": 0,
                "pior_dia_%": 0.0, "mesa": challenge_verdict(res, rules)}
    pnl = t["pnl"].to_numpy()
    gw, gl = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    r = t["r"].to_numpy()
    cost = t["symbol"].map(lambda s: 2 * instruments[s].cost_per_side).to_numpy()
    daily = eq.groupby(eq.index.tz_convert(rules.day_timezone).normalize()).last().diff() / res.initial
    out.update({
        "profit_factor": round(gw / gl, 2) if gl > 0 else float("inf"),
        "acerto_%": round((pnl > 0).mean() * 100, 1),
        "expect_R": round(r.mean(), 3),
        "t_stat": round(r.mean() / r.std(ddof=1) * np.sqrt(n), 2) if n > 2 and r.std() > 0 else 0.0,
        # average net result per trade measured in round-trip costs (want >= 3)
        "expect_vs_custo": round(float((t["ret_notional"].to_numpy() / cost).mean()), 2),
        "perdas_seguidas": max_losing_streak(pnl),
        "pior_dia_%": round(float(daily.min()) * 100, 2) if len(daily) > 1 else 0.0,
        "mesa": challenge_verdict(res, rules),
    })
    return out


def table(rows: list[dict]) -> str:
    df = pd.DataFrame(rows)
    return df.to_string(index=False)
