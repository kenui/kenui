"""Stage 2 of the V8 plan: prop-firm guards on the gold and silver trend engine, measured out of sample.

    python -m prop.research.stage2 C:\\Users\\kenui\\Projetos\\mt5data

Engine (same rule as prop/live/mt5_trend.py): long XAUUSD / XAGUSD while the 50-day average is
above the 200-day one, notional = 1% / daily volatility (max 3x), equal weight. Everything that
is chosen (regime filter, risk policy) is chosen on the data before 2019 and judged on 2019-2026.

What this file adds to the earlier study:
  * the real path inside each day, from the hourly lows, instead of an assumed worst point;
  * orders after the rollover window: filled at the open of the 01:00 server bar (17:00 New York
    is 00:00 on the broker's clock), with that bar's spread;
  * the broker's real swap per night, three nights on Wednesday;
  * a regime filter (rolling Hurst exponent and volatility percentile), picked before 2019;
  * the equity cut at 60% of the daily loss limit, and each firm's own targets.
"""
from __future__ import annotations

import dataclasses
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from prop.backtest import monte_carlo_prop as mcp
from prop.backtest.selection import Trades
from prop.config.quant import Q
from prop.research import mt5_study as S
from prop.risk import bellman_barrier_controller as bbc
from prop.risk import dual_bellman_solver as dbs
from prop.risk.prop_firm_controller import Controller

SYMS = ("XAUUSD", "XAGUSD")
FAST, SLOW, VOL_SPAN = 50, 200, 30
VOL_MENU = np.array([0.001, 0.002, 0.003, 0.004, 0.006])
FUNDED_MENU = np.array([0.002, 0.003, 0.004])
RULES = Path(__file__).resolve().parent.parent / "config" / "prop_rules.json"
FILTERS = {"sem filtro": (None, None), "Hurst > 0,50": (0.50, None), "Hurst > 0,55": (0.55, None),
           "volatilidade abaixo do percentil 90": (None, 0.90), "Hurst > 0,50 e volatilidade < p90": (0.50, 0.90)}


def hurst(logp: pd.Series, window: int = 250, lags: tuple[int, ...] = (1, 2, 4, 8, 16)) -> pd.Series:
    """Rolling Hurst exponent: slope of log(std of the k-day change) on log(k). 0.5 = random walk."""
    x = np.log(np.array(lags, float))
    x = x - x.mean()
    y = pd.DataFrame({k: np.log(logp.diff(k).rolling(window).std()) for k in lags})
    return (y.sub(y.mean(axis=1), axis=0) * x).sum(axis=1) / (x @ x)


def engine(m: S.Market, sym: str, h_min: float | None, vol_max: float | None, safe_fill: bool,
           scale: pd.Series | None = None, downside: bool = False) -> pd.DataFrame:
    """Per day: net return of the account and its worst point inside the day, for one asset.
    `scale` multiplies the position decided at each close (0 = stay out); `downside` sizes by the
    volatility of the falling days only."""
    d, h = m.bars(sym, "D1"), m.bars(sym, "H1")
    c = d["close"]
    lr = np.log(c).diff()
    vol = lr.ewm(span=VOL_SPAN, min_periods=VOL_SPAN).std()
    on = (c.ewm(span=FAST).mean() > c.ewm(span=SLOW).mean()) & (np.arange(len(c)) >= SLOW)
    if h_min is not None:
        on &= hurst(np.log(c)) > h_min
    if vol_max is not None:
        short = lr.rolling(20).std()
        on &= short.rolling(500, min_periods=250).rank(pct=True) < vol_max
    if downside:
        vol = (lr.clip(upper=0.0) ** 2).ewm(span=2 * VOL_SPAN, min_periods=VOL_SPAN).mean().pow(0.5) * np.sqrt(2.0)
    size = on * (0.01 / vol).clip(upper=3.0)
    if scale is not None:
        size = size * scale.reindex(d.index).fillna(1.0)
    w = size.shift(1).fillna(0.0)                                         # decided at yesterday's close
    spec = m.spec.get(sym, {})
    point = float(spec.get("point") or 0.0)
    side, default_swap = m.cost(sym)
    fill, cost = d["open"], pd.Series(side, index=d.index)
    hd = h.index.normalize()
    if safe_fill:                                                          # first hourly bar from 01:00 on
        late = h[h.index.hour >= 1]
        first = late.groupby(late.index.normalize()).first()
        fill = first["open"].reindex(d.index).fillna(d["open"])
        if point:
            sp = (first["spread"].reindex(d.index) * point / fill).fillna(2 * side)
            cost = np.maximum(sp / 2, side - S.COMMISSION) * 1.25 + S.COMMISSION   # 25% slippage on the half spread
    swap = default_swap * 5 / 7                                          # the earlier study's yearly cost, spread over 7 nights
    if point and int(spec.get("swap_mode", -1)) == 1:                      # broker's swap in points, at today's price
        swap = max(swap, -float(spec.get("swap_long", 0.0)) * point / float(c.iloc[-1]))
    nights = pd.Series(np.where(d.index.dayofweek == int(spec.get("swap_rollover3days", 3)) - 1, 3.0, 1.0), index=d.index)
    gross = w * (fill.shift(-1) / fill - 1.0)
    turn = (w - w.shift(1).fillna(0.0)).abs()
    net = gross - turn * cost - w * swap * nights
    low = h["low"].groupby(hd).min().reindex(d.index).fillna(d["low"])
    worst = w * (low / fill - 1.0) - turn * cost                            # lowest point of the day, from the day's fill
    return pd.DataFrame({"net": net, "worst": np.minimum(worst, 0.0), "w": w}).dropna()


def portfolio(m: S.Market, h_min: float | None = None, vol_max: float | None = None, safe_fill: bool = True,
              scale: dict[str, pd.Series] | None = None, downside: bool = False) -> pd.DataFrame:
    parts = [engine(m, s, h_min, vol_max, safe_fill, (scale or {}).get(s), downside) for s in SYMS]
    col = lambda k: pd.DataFrame({i: p[k] for i, p in enumerate(parts)}).mean(axis=1)   # noqa: E731  (whatever exists that day, as in mt5_study)
    out = pd.DataFrame({"net": col("net"), "worst": col("worst"), "ativo": pd.DataFrame({i: (p["w"] > 0).astype(float) for i, p in enumerate(parts)}).mean(axis=1)}).dropna()
    out.attrs["parts"] = parts
    return out


def episodes(p: pd.DataFrame, start: pd.Timestamp) -> dict:
    """One trade = one stretch with a position in one asset (entries from `start` on)."""
    res = []
    for part in p.attrs["parts"]:
        held = part["w"] > 0
        run = (held != held.shift(1)).cumsum()[held]
        g = part.loc[held, "net"].groupby(run)
        first = part.index.to_series()[held].groupby(run).first()
        res += list(g.sum()[first >= start])
    r = np.array(res)
    months = max((p.index[-1] - max(start, p.index[0])).days / 30.44, 1e-9)
    return {"trades": len(r), "trades por mes": round(len(r) / months, 2), "acerto liquido %": round(100 * float((r > 0).mean()), 1) if len(r) else np.nan,
            "profit factor": round(float(r[r > 0].sum() / -r[r <= 0].sum()), 2) if (r <= 0).any() and (r > 0).any() else np.nan}


def to_trades(p: pd.DataFrame, unit: float, measured: bool) -> Trades:
    z = (p["net"].to_numpy() / unit)[:, None].repeat(4, axis=1)
    worst = (p["worst"].to_numpy() / unit)[:, None].repeat(4, axis=1) if measured else np.minimum(z * 1.5, -0.3)
    n = len(z)
    gap = np.r_[1.0, np.diff(p.index.values).astype("timedelta64[D]").astype(float)]
    return Trades(z, np.minimum(worst, z), np.full(n, 2), np.ones(n), np.full(n, 0.5), np.ones(n), np.ones(n, bool),
                  gap, (z[:, 0] > 0).astype(int), np.arange(n), pd.DataFrame())


def journey(name: str, days: Trades, design: np.ndarray, t1: float, t2: float, kill: float, paths: int = 10_000,
            menu: np.ndarray = VOL_MENU, discount: float = 0.999, fixed: float | None = None) -> dict:
    """Policy solved on `design` (before 2019), account replayed on `days` (2019-2026) under one firm's targets."""
    q = dataclasses.replace(Q, phase1_target=t1, phase2_target=t2, hard_daily_kill=kill)
    old = mcp.Q
    mcp.Q = q
    try:
        if fixed is not None:                                             # the same share of the account every day
            cfg = Controller(name, 0.0, "fixed", risk_hi=fixed, daily_kill=kill, cap_to_kill=True, funded="fixed", funded_risk=fixed, payout="trigger")
        else:
            vals, probs = bbc.outcome_distribution(np.clip(design, -4, 4), bin_r=0.5)
            kw = dict(trades_per_day=1.0, discount=discount, actions=menu, sweeps=1200, tol=1e-5, daily_kill=kill)
            barrier = {0: bbc.solve_evaluation(vals, probs, t1, **kw), 1: bbc.solve_evaluation(vals, probs, t2, **kw)}
            cfg = Controller(name, 0.0, "bellman", daily_kill=kill, cap_to_kill=True, funded="harvest", payout="trigger", barrier=barrier,
                             harvest=dbs.solve_funded(vals, probs, actions=FUNDED_MENU, sweeps=4000, tol=1e-7))
        st, out = mcp.monte_carlo(days, cfg, paths)
    finally:
        mcp.Q = old
    r = st.row()
    return {"aprovacao F1+F2 %": r["passa_F1+F2_%"], "aprovado em 12 meses %": r["aprovado_em_12m_%"],
            "reprova por perda diaria %": r["viola_diario_%"], "reprova por perda total %": r["viola_total_%"],
            "sem decisao %": r["indefinido_%"], "dias corridos (mediana)": r["dias_corridos"],
            "dias ate a meta da Fase 1 (media)": round(float(np.nanmean(out["p1_cal"])), 0) if np.isfinite(out["p1_cal"]).any() else np.nan,
            "dias ate aprovar F1+F2 (media)": round(float(np.nanmean(out["app_cal"])), 0) if np.isfinite(out["app_cal"]).any() else np.nan,
            "sobrevive 12 meses %": r["sobrevive_12m_%"], "saques 12 meses US$": r["saques_12m_usd"], "EV US$": r["EV_usd"]}


def stats(p: pd.DataFrame) -> dict:
    x = p["net"]
    c = x.cumsum()
    return {"sharpe": round(S.sharpe(x), 2), "dias com posicao %": round(100 * (p["ativo"] > 0).mean(), 1),
            "pior dia / dia normal": round(float(x.min() / x.std()), 1), "pior ponto dentro do dia / dia normal": round(float(p["worst"].min() / x.std()), 1),
            "queda maxima / dia normal": round(float((c - c.cummax()).min() / x.std()), 1)}


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/mt5")
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else folder
    m = S.Market(folder)
    rules = json.loads(RULES.read_text())
    pd.set_option("display.width", 250, "display.max_columns", 30)
    split = lambda p: (p[p.index < S.SPLIT], p[p.index >= S.SPLIT])  # noqa: E731

    print("=== 1) Filtro de regime: escolhido antes de 2019, julgado depois ===")
    rows, ports = [], {}
    for name, (hm, vm) in FILTERS.items():
        ports[name] = portfolio(m, hm, vm)
        a, b = split(ports[name])
        rows.append({"filtro": name, "sharpe antes de 2019": stats(a)["sharpe"], **{f"{k} (depois)": v for k, v in stats(b).items()},
                     **{f"{k} (depois)": v for k, v in episodes(ports[name], S.SPLIT).items()}})
    reg = pd.DataFrame(rows).set_index("filtro")
    best = reg["sharpe antes de 2019"].idxmax()
    print(reg.to_string())
    print(f"escolhido pelo periodo antes de 2019: {best}")

    print("\n=== 2) Jornada na mesa, 10.000 contas, dias de 2019 a 2026 ===")
    old = portfolio(m, safe_fill=False)
    cases = [("A. motor como no estudo anterior (pior ponto do dia suposto, corte a 64%)", old, False, 0.032),
             ("B. A + caminho real dentro do dia + ordem depois do rollover + swap triplo", ports["sem filtro"], True, 0.032),
             ("C. B + corte a 60% da perda diaria", ports["sem filtro"], True, 0.030)]
    cases += [(f"H1. C + filtro: {k}", v, True, 0.030) for k, v in ports.items() if k != "sem filtro"]
    firms = [("padrao / FundedNext (8% + 5%)", rules["padrao"]), ("FTMO / The5ers (10% + 5%)", rules["ftmo"])]
    out = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for label, p, measured, kill in cases:
            a, b = split(p)
            unit = float(a["net"].std())
            for firm, r in firms:
                j = journey(label, to_trades(b, unit, measured), a["net"].to_numpy() / unit, r["meta_fase1"], r["meta_fase2"], kill)
                worst = float(b["worst"].min() / unit * VOL_MENU.max())
                out.append({"caso": label, "mesa": firm, "sharpe depois": stats(b)["sharpe"],
                            "pior queda no dia sem corte % (limite 5)": round(100 * worst, 2), **j})
                print(f"  {label[:60]:60s} {firm:30s} {j['aprovacao F1+F2 %']:5.1f}%", flush=True)
    table = pd.DataFrame(out)
    print("\n" + table.to_string(index=False))
    out_dir.mkdir(parents=True, exist_ok=True)
    reg.to_csv(out_dir / "estagio2_regime.csv")
    table.to_csv(out_dir / "estagio2_jornada.csv", index=False)


if __name__ == "__main__":
    main()
