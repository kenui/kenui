"""What it takes to pass: approval rate, time and money as a function of strategy quality.

Each row is a daily-return strategy (synthetic with a given Sharpe ratio, or a real candidate
judged on 2023-2026 with rules chosen on 2019-2022) pushed through the same full-journey
Monte Carlo as the V5 report: Phase 1 (+8%), Phase 2 (+5%), 12 months funded, 10,000 accounts,
risk chosen by the Bellman controller from a menu of daily volatility budgets.

    python -m prop.research.approval_map
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from prop.backtest import monte_carlo_prop as mcp
from prop.backtest.selection import Trades
from prop.config.quant import Q
from prop.research import families as F
from prop.research import trend as T
from prop.risk import bellman_barrier_controller as bbc
from prop.risk import dual_bellman_solver as dbs
from prop.risk.prop_firm_controller import Controller

VOL_MENU = np.array([0.001, 0.002, 0.003, 0.004, 0.006])      # daily volatility budget of the account
FUNDED_MENU = np.array([0.002, 0.003, 0.004])
IS_RULES = ("tsmom30", "ema10_40", "donchian20")              # best three on 2019-2022, long only


def as_days(r: np.ndarray, unit: float) -> Trades:
    """One 'trade' per day, in units of one normal day (`unit` = daily standard deviation)."""
    z = (np.asarray(r, float) / unit)[:, None].repeat(4, axis=1)
    mae = np.minimum(z * 1.5, -0.3)                             # intraday worst: assumed, not measured
    n = len(z)
    return Trades(z, np.minimum(mae, z), np.full(n, 2), np.ones(n), np.full(n, 0.5), np.ones(n), np.ones(n, bool),
                  np.ones(n), (z[:, 0] > 0).astype(int), np.arange(n), pd.DataFrame())


def controller(name: str, design: np.ndarray) -> Controller:
    """Policy solved on `design` (never the data it is judged on)."""
    vals, probs = bbc.outcome_distribution(design, bin_r=0.25)
    kw = dict(trades_per_day=1.0, discount=0.9995, actions=VOL_MENU)
    barrier = {0: bbc.solve_evaluation(vals, probs, Q.phase1_target, **kw),
               1: bbc.solve_evaluation(vals, probs, Q.phase2_target, **kw)}
    return Controller(name, 0.0, "bellman", daily_kill=Q.hard_daily_kill, cap_to_kill=True, funded="harvest",
                      payout="trigger", barrier=barrier, harvest=dbs.solve_funded(vals, probs, actions=FUNDED_MENU))


def journey(name: str, days: Trades, design: np.ndarray, paths: int) -> dict:
    st = mcp.monte_carlo(days, controller(name, design), paths)[0].row()
    return {"estrategia": name, "aprovacao_F1+F2_%": st["passa_F1+F2_%"], "aprovado_em_12m_%": st["aprovado_em_12m_%"],
            "dias_corridos_mediana": st["dias_corridos"], "reprova_%": round(st["viola_diario_%"] + st["viola_total_%"], 1),
            "sobrevive_12m_%": st["sobrevive_12m_%"], "saques_12m_usd": st["saques_12m_usd"], "EV_usd": st["EV_usd"]}


def candidates() -> dict[str, tuple[pd.Series, pd.Series]]:
    """name -> (in-sample daily returns, out-of-sample daily returns)."""
    data = T.load()
    lo = T.table(data, long_only=True)
    ls = T.table(data, long_only=False)
    pick = lambda t, assets=None: t.loc[:, [(a, r) for a, r in t.columns if r in IS_RULES and (assets is None or a in assets)]].mean(axis=1)  # noqa: E731
    out = {"tendencia comprada, cripto + ouro + euro": pick(lo),
           "tendencia comprada, so BTC ETH e ouro": pick(lo, ("BTC", "ETH", "PAXG")),
           "tendencia comprada e vendida": pick(ls),
           "reversao de movimento extremo no euro (dado Binance)": F.extreme_reversal(data, "EUR", 3, 4)}
    return {k: (v[v.index < T.SPLIT].dropna(), v[v.index >= T.SPLIT].dropna()) for k, v in out.items()}


def main(paths: int = Q.mc_paths) -> pd.DataFrame:
    warnings.filterwarnings("ignore")
    pd.set_option("display.width", 250)
    rng = np.random.default_rng(Q.seed)
    rows = []
    for s in (0.0, 0.5, 1.0, 1.5, 2.0, 3.0):
        mu = s / np.sqrt(365)
        design = rng.standard_t(5, 4000) / np.sqrt(5 / 3) + mu * 0.5         # designed for half the Sharpe
        days = as_days(rng.standard_t(5, 3000) / np.sqrt(5 / 3) + mu, 1.0)
        rows.append({"sharpe_anual": s, **journey(f"sintetica, Sharpe {s:.1f}", days, design, paths)})
    for name, (ins, oos) in candidates().items():
        unit = float(ins.std())
        rows.append({"sharpe_anual": round(T.sharpe(oos), 2), **journey(name, as_days(oos.to_numpy(), unit), ins.to_numpy() / unit, paths),
                     "sharpe_2019_22": round(T.sharpe(ins), 2)})
    out = pd.DataFrame(rows)
    print(out.to_string(index=False))
    Q.out_dir.mkdir(parents=True, exist_ok=True)
    out.to_csv(Q.out_dir / "mapa_aprovacao.csv", index=False)
    return out


if __name__ == "__main__":
    main()
