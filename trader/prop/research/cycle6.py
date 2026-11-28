"""Cycle 6: currencies and metals not tested before (RESEARCH_LOG.md, "Ciclo 6").

    python -m prop.research.cycle6 C:\\Users\\kenui\\Projetos\\mt5data

  tendencia   trend.RULES, long and short, on emerging pairs against the dollar, crosses of the
              major currencies and the new metals
  juro        short dollar against a fixed list of high-interest currencies, always or only while
              the 180-day return of the currency is not negative

Cost per side = half the median spread plus commission. Swap comes from symbols.json: the paid
average of both sides for the trend, each side with its own sign for the interest premium (today's
swap used for the whole past, a known limit written in the log).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from prop.research import mt5_study as S
from prop.research import trend as T

GROUPS = {"emergentes contra o dolar": ["USDMXN", "USDZAR", "USDTRY", "USDBRL", "USDCNH", "USDPLN", "USDHUF", "USDCZK", "USDSGD",
                                        "USDTHB", "USDILS", "USDCLP", "USDCOP", "USDNOK", "USDSEK"],
          "cruzamentos principais": ["EURAUD", "EURCAD", "EURCHF", "EURNZD", "GBPAUD", "GBPCAD", "GBPCHF", "GBPNZD", "AUDCAD",
                                     "AUDCHF", "AUDJPY", "AUDNZD", "CADCHF", "CADJPY", "CHFJPY", "NZDCAD", "NZDCHF", "NZDJPY"],
          "metais novos": ["XPTUSD", "XPDUSD", "NICKEL", "LEAD"]}
HIGH = ["USDMXN", "USDZAR", "USDTRY", "USDBRL", "USDHUF", "USDPLN", "USDCOP", "USDCLP"]
MIN_DAYS, T_MIN = 1500, 2.5


def usable(m: S.Market, syms: list[str]) -> list[str]:
    return [s for s in syms if m.has(s) and len(m.bars(s, "D1")) >= MIN_DAYS]


def side_cost(m: S.Market, sym: str) -> float:
    d = m.bars(sym, "D1")
    point = float(m.spec.get(sym, {}).get("point") or 0.0)
    return float(d["spread"].iloc[-750:].median()) * point / float(d["close"].iloc[-1]) / 2 + S.COMMISSION


def swaps(m: S.Market, sym: str) -> tuple[float, float]:
    """Swap paid per night by a long and by a short, fractions of the notional (negative = received)."""
    s, px = m.spec.get(sym, {}), float(m.bars(sym, "D1")["close"].iloc[-1])
    if int(s.get("swap_mode", -1)) != 1 or not s.get("point"):
        return 0.00016, 0.00016
    return -float(s.get("swap_long", 0.0)) * s["point"] / px, -float(s.get("swap_short", 0.0)) * s["point"] / px


def trend_group(m: S.Market, syms: list[str], rule: str) -> tuple[pd.Series, int]:
    cols, n = {}, 0
    for s in usable(m, syms):
        d = m.bars(s, "D1")
        sig = T.RULES[rule](d)
        cols[s] = T.net_returns(d, sig, (side_cost(m, s), max(float(np.mean(swaps(m, s))), 0.00003)))
        after = sig[sig.index >= S.SPLIT]
        n += int(((after != after.shift(1)) & (after != 0)).sum())
    return S.portfolio(cols), n


def premium(m: S.Market, filtered: bool) -> tuple[pd.Series, int]:
    cols, n = {}, 0
    for s in usable(m, HIGH):
        d = m.bars(s, "D1")
        sig = pd.Series(-1.0, index=d.index)                             # short the dollar
        if filtered:
            sig = sig.where(d["close"].pct_change(180) <= 0, 0.0)        # the pair is not rising = the currency is not falling
        w = (sig * (0.01 / T.vol(d)).clip(upper=3.0)).shift(1).fillna(0.0)
        oo = d["open"].shift(-1) / d["open"] - 1.0
        turn = (w - w.shift(1).fillna(0.0)).abs()
        cols[s] = (w * oo - turn * side_cost(m, s) - w.abs() * swaps(m, s)[1]).dropna()
        after = sig[sig.index >= S.SPLIT]
        n += int(((after != after.shift(1)) & (after != 0)).sum())
    return S.portfolio(cols), n


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/mt5")
    from prop.research import stage2 as G
    m = S.Market(folder)
    base = G.portfolio(m, downside=True)["net"]
    runs = [(gn, " ".join(usable(m, syms)), rule, *trend_group(m, syms, rule)) for gn, syms in GROUPS.items() for rule in T.RULES]
    runs += [("premio de juro", " ".join(usable(m, HIGH)), name, *premium(m, f)) for name, f in (("sempre", False), ("com filtro de 180 dias", True))]
    rows = []
    for gn, used, rule, x, n in runs:
        if x.empty:
            continue
        a, b = S.before_after(x)
        after = x[x.index >= S.SPLIT]
        months = max((x.index[-1] - S.SPLIT).days / 30.44, 1)
        rows.append({"grupo": gn, "simbolos": used, "regra": rule, "inicio": x.index[0].date(), "sharpe antes de 2019": a, "sharpe 2019-2026": b,
                     "t 2019-2026": round(float(after.mean() / after.std() * np.sqrt(len(after))), 2), "operacoes 2019-2026": n,
                     "operacoes por mes": round(n / months, 2), "correlacao com a Frente 1": round(float(x.corr(base)), 2)})
    table = pd.DataFrame(rows)
    pd.set_option("display.width", 250, "display.max_columns", 30, "display.max_rows", 200)
    print(table.drop(columns="simbolos").to_string(index=False))
    table.to_csv(folder / "ciclo6_variantes.csv", index=False)
    print()
    for gn, g in table.groupby("grupo", sort=False):
        r = g.loc[g["sharpe antes de 2019"].idxmax()]
        ok = (r["sharpe antes de 2019"] >= 0.5 and r["sharpe 2019-2026"] >= 0.5 and r["operacoes 2019-2026"] >= 30
              and r["t 2019-2026"] >= T_MIN and abs(r["correlacao com a Frente 1"]) < 0.25)
        print(f"{gn} ({r['simbolos']}): melhor antes de 2019 = {r['regra']} ({r['sharpe antes de 2019']} / {r['sharpe 2019-2026']}, "
              f"t {r['t 2019-2026']}, {r['operacoes 2019-2026']} operacoes, correlacao {r['correlacao com a Frente 1']}) {'PASSA' if ok else 'nao passa'}")


if __name__ == "__main__":
    main()
