"""Cycle 2: calendar flows instead of price formulas (RESEARCH_LOG.md, "Ciclo 2").

    python -m prop.research.cycle2 C:\\Users\\kenui\\Projetos\\mt5data

  virada_mes   long stock indices only on the trading days around the turn of the month
  madrugada    long US indices from the New York afternoon to the next morning, every day

Same protocol as the other studies: decision on closed bars, fill at the next open, spread,
commission and swap; the variant is chosen on the days before 2019 and judged on 2019-2026.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from prop.fronts.common import bar_cost, daily_vol
from prop.research import mt5_study as S
from prop.research import new_engines as E

WINDOWS = {"ultimo + 3 primeiros": (1, 3), "ultimo + 1 primeiro": (1, 1), "3 ultimos + 3 primeiros": (3, 3)}
GROUPS = {"US500": ["US500"], "indices dos EUA": ["US500", "US30", "US2000"], "8 indices": S.INDEX}
US = {"US500": ["US500"], "indices dos EUA": ["US500", "US30", "US2000"]}


def in_window(index: pd.DatetimeIndex, last: int, first: int) -> pd.Series:
    """True on the `last` final and `first` initial trading days of each month of this calendar."""
    s = pd.Series(1, index=index)
    month = [index.year, index.month]
    from_start = s.groupby(month).cumsum()
    from_end = s[::-1].groupby([index[::-1].year, index[::-1].month]).cumsum()[::-1]
    return (from_start <= first) | (from_end <= last)


def turn_of_month(m: S.Market, syms: list[str], last: int, first: int) -> pd.Series:
    close, oo, vol, side, swap = E.panel(m, [s for s in syms if m.has(s)])
    held = pd.DataFrame({s: in_window(close[s].dropna().index, last, first) for s in close}).reindex(close.index).fillna(False)
    w = (0.01 / vol).clip(upper=3.0).where(held.shift(-1, fill_value=False), 0.0)     # row t is held on day t+1
    return E.net(w.div(max(len(close.columns), 1)), oo, side, swap)


def overnight(m: S.Market, sym: str, enter: int, leave: int) -> pd.Series:
    h = m.bars(sym, "H1")
    cost, vol = bar_cost(m, sym, h), daily_vol(h)
    _, swap = m.cost(sym)
    triple = int(m.spec.get(sym, {}).get("swap_rollover3days", 5))            # MetaTrader weekday, Sunday = 0
    op, hour = h["open"].to_numpy(), h.index.hour.to_numpy()
    out = {}
    starts = np.flatnonzero(hour == enter)
    ends = np.flatnonzero(hour == leave)
    for s in starts:
        k = np.searchsorted(ends, s + 1)
        if k >= len(ends) or not np.isfinite(vol[s]) or vol[s] <= 0:
            continue
        e = ends[k]
        days = (h.index[e].normalize() - h.index[s].normalize()).days
        if days < 1 or days > 4:
            continue
        nights = 3 if (h.index[s].dayofweek + 1) % 7 == triple else 1
        r = op[e] / op[s] - 1.0 - cost[s] - cost[e] - swap * nights
        out[h.index[e].normalize()] = min(0.01 / vol[s], 3.0) * r
    return pd.Series(out, dtype=float).sort_index()


def variants(m: S.Market) -> dict[str, pd.Series]:
    v = {}
    for wn, (last, first) in WINDOWS.items():
        for gn, syms in GROUPS.items():
            v[f"virada_mes|{gn}|{wn}"] = turn_of_month(m, syms, last, first)
    for enter in (22, 23):
        for leave in (16, 17):
            for gn, syms in US.items():
                cols = {s: overnight(m, s, enter, leave) for s in syms if m.has(s, "H1")}
                v[f"madrugada|{gn}|{enter}h a {leave}h"] = pd.DataFrame(cols).mean(axis=1)
    return v


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/mt5")
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else folder
    from prop.research import stage2 as G
    m = S.Market(folder)
    base = G.portfolio(m, downside=True)["net"]
    rows, v = [], variants(m)
    for k, x in v.items():
        fam, grp, var = k.split("|")
        a, b = S.before_after(x)
        after = x[x.index >= S.SPLIT]
        active = after[after != 0]
        rows.append({"familia": fam, "grupo": grp, "variante": var, "inicio": x.index[0].date(), "sharpe antes de 2019": a,
                     "sharpe 2019-2026": b, "dias com posicao por mes": round(len(active) / max(len(after), 1) * 21, 1),
                     "acerto dos dias %": round(100 * float((active > 0).mean()), 1),
                     "queda maxima / dia normal": round(float((after.cumsum().cummax() - after.cumsum()).max() / after.std()), 1),
                     "correlacao com a Frente 1": round(float(x.corr(base)), 2)})
    table = pd.DataFrame(rows)
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(table.to_string(index=False))
    out_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(out_dir / "ciclo2_variantes.csv", index=False)

    scale = lambda s: s / s[s.index < S.SPLIT].std()  # noqa: E731
    cand = {"Frente 1 (base)": base}
    for fam, g in table.groupby("familia"):
        r = g.loc[g["sharpe antes de 2019"].idxmax()]
        key = f"{fam}|{r['grupo']}|{r['variante']}"
        ok = r["sharpe antes de 2019"] >= E.MIN_IS and r["sharpe 2019-2026"] > 0
        print(f"\n{fam}: melhor antes de 2019 = {key} ({r['sharpe antes de 2019']} / {r['sharpe 2019-2026']}) {'passa' if ok else 'nao passa'}")
        if ok:
            cand[key] = v[key]
            if abs(r["correlacao com a Frente 1"]) < 0.25:
                cand[f"Frente 1 + {key}"] = pd.DataFrame({"a": scale(base), "b": scale(v[key])}).fillna(0.0).loc[lambda d: d.index >= max(base.index[0], v[key].index[0])].mean(axis=1)
    out = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for k, x in cand.items():
            a, b = x[x.index < S.SPLIT].dropna(), x[x.index >= S.SPLIT].dropna()
            unit = float(a.std())
            j = G.journey(k, G.to_trades(pd.DataFrame({"net": b, "worst": 0.0}), unit, False), a.to_numpy() / unit, 0.08, 0.05, 0.030)
            out.append({"motor": k, "sharpe antes de 2019": round(S.sharpe(a), 2), "sharpe 2019-2026": round(S.sharpe(b), 2), **j})
            print(f"  {k[:70]:70s} aprovacao {j['aprovacao F1+F2 %']:5.1f}%", flush=True)
    res = pd.DataFrame(out)
    print("\n" + res.T.to_string())
    res.to_csv(out_dir / "ciclo2_jornada.csv", index=False)


if __name__ == "__main__":
    main()
