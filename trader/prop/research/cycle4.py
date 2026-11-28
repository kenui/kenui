"""Cycle 4: daily trend on markets the server only offers as exchange-traded funds (RESEARCH_LOG.md, "Ciclo 4").

    python -m prop.research.cycle4 C:\\Users\\kenui\\Projetos\\mt5data

Same trend rules as trend.RULES, long and short, equal weight inside each group fixed in the log.
Cost per side = half the median spread (floor of 2 basis points) plus commission; financing of
0.016% per night. Splits are not adjusted in the server history: an overnight gap above 40% is
treated as a split and the earlier prices are rescaled.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from prop.research import mt5_study as S
from prop.research import trend as T

GROUPS = {"energia": ["USO", "BNO", "UNG"], "juros e credito": ["TLT", "IEF", "TIP", "LQD", "HYG", "EMB"],
          "materias-primas": ["DBC", "DBA", "CPER", "PPLT"], "moedas": ["UUP", "FXE", "FXY"],
          "paises": ["EFA", "EEM", "EWJ", "EWZ", "FXI", "INDA", "EWG", "EWU"], "cripto (so informacao)": ["IBIT", "BITO", "ETHA"]}
FLOOR, SWAP, MIN_DAYS, T_MIN = 0.0002, 0.00016, 1500, 2.6


def split_adjusted(d: pd.DataFrame) -> pd.DataFrame:
    """Rescales the prices before each overnight gap larger than 40% (a split the server did not adjust)."""
    gap = (d["open"] / d["close"].shift(1)).fillna(1.0)
    factor = gap.where((gap - 1.0).abs() > 0.4, 1.0)
    back = factor[::-1].cumprod()[::-1].shift(-1).fillna(1.0)          # product of the later splits
    out = d.copy()
    for c in ("open", "high", "low", "close"):
        out[c] = d[c] * back
    return out


def cost(m: S.Market, sym: str, d: pd.DataFrame) -> tuple[float, float]:
    point = float(m.spec.get(sym, {}).get("point") or 0.0)
    raw = m.bars(sym, "D1")
    spread = float(raw["spread"].iloc[-750:].median()) * point / float(raw["close"].iloc[-1])
    return max(spread / 2, FLOOR) + S.COMMISSION, SWAP


def group(m: S.Market, syms: list[str], rule: str) -> tuple[pd.Series, int]:
    """Equal-weight daily return of the group and the number of position changes after the split date."""
    cols, n = {}, 0
    for s in syms:
        if not m.has(s) or len(m.bars(s, "D1")) < MIN_DAYS:
            continue
        d = split_adjusted(m.bars(s, "D1"))
        sig = T.RULES[rule](d)
        cols[s] = T.net_returns(d, sig, cost(m, s, d))
        after = sig[sig.index >= S.SPLIT]
        n += int(((after != after.shift(1)) & (after != 0)).sum())
    return S.portfolio(cols), n


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/mt5")
    from prop.research import stage2 as G
    m = S.Market(folder)
    base = G.portfolio(m, downside=True)["net"]
    rows = []
    for gn, syms in GROUPS.items():
        used = [s for s in syms if m.has(s) and len(m.bars(s, "D1")) >= MIN_DAYS]
        for rule in T.RULES:
            x, n = group(m, syms, rule)
            if x.empty:
                continue
            a, b = S.before_after(x)
            after = x[x.index >= S.SPLIT]
            months = max((x.index[-1] - S.SPLIT).days / 30.44, 1)
            rows.append({"grupo": gn, "fundos": " ".join(used), "regra": rule, "inicio": x.index[0].date(), "sharpe antes de 2019": a,
                         "sharpe 2019-2026": b, "t 2019-2026": round(float(after.mean() / after.std() * np.sqrt(len(after))), 2),
                         "operacoes 2019-2026": n, "operacoes por mes": round(n / months, 2),
                         "correlacao com a Frente 1": round(float(x.corr(base)), 2)})
    table = pd.DataFrame(rows)
    pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 200)
    print(table.drop(columns="fundos").to_string(index=False))
    table.to_csv(folder / "ciclo4_variantes.csv", index=False)
    print()
    for gn, g in table.groupby("grupo", sort=False):
        if g["sharpe antes de 2019"].isna().all():
            print(f"{gn} ({g['fundos'].iloc[0]}): sem historico antes de 2019, nao pode ser escolhido")
            continue
        r = g.loc[g["sharpe antes de 2019"].idxmax()]
        ok = (r["sharpe antes de 2019"] >= 0.5 and r["sharpe 2019-2026"] >= 0.5 and r["operacoes 2019-2026"] >= 30
              and r["t 2019-2026"] >= T_MIN and abs(r["correlacao com a Frente 1"]) < 0.25)
        print(f"{gn} ({r['fundos']}): melhor antes de 2019 = {r['regra']} ({r['sharpe antes de 2019']} / {r['sharpe 2019-2026']}, "
              f"t {r['t 2019-2026']}, {r['operacoes 2019-2026']} operacoes, correlacao {r['correlacao com a Frente 1']}) {'PASSA' if ok else 'nao passa'}")


if __name__ == "__main__":
    main()
