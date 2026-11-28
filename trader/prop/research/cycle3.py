"""Cycle 3: month-end currency hedging flow (RESEARCH_LOG.md, "Ciclo 3").

    python -m prop.research.cycle3 C:\\Users\\kenui\\Projetos\\mt5data

In the last N trading days of the month, hold the currencies against the dollar with the sign of
the month-to-date return of US stocks: foreign funds that hedge a fixed share of their US stocks
must sell dollars after a good month and buy them after a bad one. Decision on closed bars, fill
at the next open, spread, commission and swap; chosen on the days before 2019, judged after.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from prop.research import mt5_study as S
from prop.research import new_engines as E
from prop.research.cycle2 import in_window

EUROPE = ["DE40", "IT40", "NETH25", "SWI20"]
BASKETS = {"7 moedas": E.CURRENCIES, "EUR, GBP e CHF": ["EURUSD", "GBPUSD", "USDCHF"]}


def month_to_date(close: pd.Series) -> pd.Series:
    """Log return since the last close of the previous month."""
    c = np.log(close)
    last = c.groupby([c.index.year, c.index.month]).transform("last")
    prev = last.shift(1).where(c.index.to_series().dt.month != c.index.to_series().shift(1).dt.month).ffill()
    return c - prev


def signal(m: S.Market, relative: bool) -> pd.Series:
    us = month_to_date(m.bars("US500", "D1")["close"])
    if not relative:
        return us
    eu = pd.DataFrame({s: month_to_date(m.bars(s, "D1")["close"]) for s in EUROPE if m.has(s)}).mean(axis=1)
    return (us - eu.reindex(us.index).ffill()).dropna()


def month_end(m: S.Market, syms: list[str], days: int, relative: bool) -> pd.Series:
    close, oo, vol, side, swap = E.panel(m, [s for s in syms if m.has(s)])
    held = in_window(close.index, days, 0)
    enter = held.shift(-1, fill_value=False)                           # row t is held on day t+1
    first = enter & ~enter.shift(1, fill_value=False)                  # the close where the trade is decided
    sig = np.sign(signal(m, relative).reindex(close.index).ffill())
    sig = sig.where(first).where(enter).ffill().where(enter, 0.0)      # one sign per month, kept until the month ends
    w = (0.01 / vol).clip(upper=3.0).mul(sig, axis=0)
    return E.net(w.div(len(close.columns)), oo, side, swap)


def trades(x: pd.Series) -> pd.Series:
    """One result per month-end: days are grouped by the month in which the trade started."""
    a = x[x != 0]
    key = (a.index - pd.Timedelta(days=10)).to_period("M")            # the exit day falls in the next month
    return a.groupby(key).sum()


def variants(m: S.Market) -> dict[str, pd.Series]:
    return {f"{bn}|{'US500 menos Europa' if rel else 'US500'}|{n} dia(s)": month_end(m, syms, n, rel)
            for bn, syms in BASKETS.items() for rel in (False, True) for n in (1, 2, 3)}


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/mt5")
    from prop.research import stage2 as G
    m = S.Market(folder)
    base = G.portfolio(m, downside=True)["net"]
    rows = []
    for k, x in variants(m).items():
        a, b = S.before_after(x)
        t = trades(x[x.index >= S.SPLIT])
        months = max((x.index[-1] - S.SPLIT).days / 30.44, 1)
        rows.append({"variante": k, "inicio": x.index[0].date(), "sharpe antes de 2019": a, "sharpe 2019-2026": b,
                     "operacoes 2019-2026": len(t), "operacoes por mes": round(len(t) / months, 2),
                     "t das operacoes": round(float(t.mean() / t.std() * np.sqrt(len(t))), 2) if len(t) > 2 else np.nan,
                     "acerto %": round(100 * float((t > 0).mean()), 1), "correlacao com a Frente 1": round(float(x.corr(base)), 2)})
    table = pd.DataFrame(rows)
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(table.to_string(index=False))
    table.to_csv(folder / "ciclo3_variantes.csv", index=False)
    r = table.loc[table["sharpe antes de 2019"].idxmax()]
    ok = (r["sharpe antes de 2019"] >= E.MIN_IS and r["sharpe 2019-2026"] >= 0.5 and r["operacoes 2019-2026"] >= 30
          and r["t das operacoes"] >= 2 and abs(r["correlacao com a Frente 1"]) < 0.25)
    print(f"\nmelhor antes de 2019: {r['variante']} ({r['sharpe antes de 2019']} / {r['sharpe 2019-2026']}) {'PASSA' if ok else 'nao passa'}")


if __name__ == "__main__":
    main()
