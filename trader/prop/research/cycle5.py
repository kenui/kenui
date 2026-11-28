"""Cycle 5: positioning of large speculators from the weekly CFTC report (RESEARCH_LOG.md, "Ciclo 5").

    python -m prop.research.cycle5 C:\\Users\\kenui\\Projetos\\mt5data          # reads <folder>/cot/<code>.csv
    python -m prop.research.cycle5 C:\\Users\\kenui\\Projetos\\mt5data --baixar # downloads those files first

Measure = net position of non-commercials / open interest (legacy report, futures only). The report
shows Tuesday's positions and comes out on Friday: the signal counts from that Friday's close and the
order is filled at Monday's open. Costs of the broker; chosen before 2019, judged after.
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from prop.research import mt5_study as S
from prop.research import new_engines as E

CODES = {"XAUUSD": "088691", "XAGUSD": "084691", "EURUSD": "099741", "GBPUSD": "096742", "USDJPY": "097741",
         "AUDUSD": "232741", "USDCAD": "090741", "USDCHF": "092741", "NZDUSD": "112741"}
BASKETS = {"metais": ["XAUUSD", "XAGUSD"], "moedas": E.CURRENCIES}
URL = ("https://publicreporting.cftc.gov/resource/6dca-aqww.csv?$limit=5000&$order=report_date_as_yyyy_mm_dd&$select="
       "report_date_as_yyyy_mm_dd,open_interest_all,noncomm_positions_long_all,noncomm_positions_short_all&cftc_contract_market_code=")
START = pd.Timestamp("1993-01-01")            # weekly reports released on Fridays only from late 1992
LAG = pd.Timedelta(days=3)                    # Tuesday's positions are public on Friday afternoon


def fetch(folder: Path) -> None:
    (folder / "cot").mkdir(parents=True, exist_ok=True)
    for code in CODES.values():
        with urllib.request.urlopen(URL + code, timeout=90) as r:
            (folder / "cot" / f"{code}.csv").write_bytes(r.read())


def measure(folder: Path, sym: str) -> pd.Series:
    """Net speculative position over open interest, indexed by the day it became public."""
    d = pd.read_csv(folder / "cot" / f"{CODES[sym]}.csv")
    x = (d["noncomm_positions_long_all"] - d["noncomm_positions_short_all"]) / d["open_interest_all"]
    x.index = pd.to_datetime(d["report_date_as_yyyy_mm_dd"]) + LAG
    return x[~x.index.duplicated()].sort_index()[START:]


def extreme(x: pd.Series, weeks: int) -> pd.Series:
    """-1 after the z-score goes above 1.5, +1 below -1.5, flat again inside 0.5."""
    z = ((x - x.rolling(weeks).mean()) / x.rolling(weeks).std()).to_numpy()
    out, pos = np.zeros(len(z)), 0.0
    for i, v in enumerate(z):
        if np.isnan(v):
            continue
        if pos == 0.0:
            pos = -1.0 if v > 1.5 else (1.0 if v < -1.5 else 0.0)
        elif abs(v) < 0.5:
            pos = 0.0
        out[i] = pos
    return pd.Series(out, index=x.index)


def flow(x: pd.Series, weeks: int) -> pd.Series:
    return np.sign(x.diff(weeks)).fillna(0.0)


RULES = {"contraria 52 semanas": lambda x: extreme(x, 52), "contraria 156 semanas": lambda x: extreme(x, 156),
         "fluxo 4 semanas": lambda x: flow(x, 4), "fluxo 13 semanas": lambda x: flow(x, 13)}


def basket(m: S.Market, folder: Path, syms: list[str], rule: str) -> tuple[pd.Series, int]:
    close, oo, vol, side, swap = E.panel(m, [s for s in syms if m.has(s)])
    sig, n = {}, 0
    for s in close.columns:
        weekly = RULES[rule](measure(folder, s))
        both = weekly.index.union(close.index)
        sig[s] = weekly.reindex(both).ffill(limit=10).reindex(close.index).fillna(0.0)   # a missing report ends the position
        after = weekly[weekly.index >= S.SPLIT]
        n += int(((after != after.shift(1)) & (after != 0)).sum())
    w = (0.01 / vol).clip(upper=3.0) * pd.DataFrame(sig)
    return E.net(w.div(len(close.columns)), oo, side, swap)[START:], n


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    folder = Path(args[0]) if args else Path("data/mt5")
    if "--baixar" in sys.argv:
        fetch(folder)
    from prop.research import stage2 as G
    m = S.Market(folder)
    base = G.portfolio(m, downside=True)["net"]
    rows = []
    for bn, syms in BASKETS.items():
        for rule in RULES:
            x, n = basket(m, folder, syms, rule)
            a, b = S.before_after(x)
            after = x[x.index >= S.SPLIT]
            months = max((x.index[-1] - S.SPLIT).days / 30.44, 1)
            rows.append({"cesta": bn, "regra": rule, "sharpe antes de 2019": a, "sharpe 2019-2026": b,
                         "t 2019-2026": round(float(after.mean() / after.std() * np.sqrt(len(after))), 2),
                         "operacoes 2019-2026": n, "operacoes por mes": round(n / months, 2),
                         "dias com posicao %": round(100 * float((after != 0).mean()), 0),
                         "correlacao com a Frente 1": round(float(x.corr(base)), 2)})
    table = pd.DataFrame(rows)
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(table.to_string(index=False))
    table.to_csv(folder / "ciclo5_variantes.csv", index=False)
    print()
    for bn, g in table.groupby("cesta", sort=False):
        r = g.loc[g["sharpe antes de 2019"].idxmax()]
        ok = (r["sharpe antes de 2019"] >= 0.5 and r["sharpe 2019-2026"] >= 0.5 and r["operacoes 2019-2026"] >= 30
              and r["t 2019-2026"] >= 2.3 and abs(r["correlacao com a Frente 1"]) < 0.25)
        print(f"{bn}: melhor antes de 2019 = {r['regra']} ({r['sharpe antes de 2019']} / {r['sharpe 2019-2026']}, t {r['t 2019-2026']}) {'PASSA' if ok else 'nao passa'}")


if __name__ == "__main__":
    main()
