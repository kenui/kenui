"""Search for a different engine on MetaTrader 5 markets: families that the earlier studies did not test.

    python -m prop.research.new_engines C:\\Users\\kenui\\Projetos\\mt5data

Same protocol as mt5_study: daily bars, decision at the close, trade at the next open, broker
costs (spread, commission, swap per night), every variant listed in advance, the choice made on
the days before 2019 and the judgement on 2019-2026.

  momento_relativo   long the strongest and short the weakest third of a group (indices, currencies)
  reversao_relativa  the opposite over a few days
  premio             plain long exposure with a volatility target (equity premium, gold), no signal
  carteira           equal risk in the gold and silver trend plus each family's pre-2019 choice

Currency carry is left out on purpose: the files only hold today's swap rates, so ranking past
days by them would use information from the future.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from prop.research import mt5_study as S
from prop.research import trend as T

INDEX = ["US500", "US30", "US2000", "DE40", "CHINA50", "IT40", "NETH25", "SWI20"]
USD_BASE = {"USDJPY", "USDCAD", "USDCHF"}                       # sign flipped so that every series is "currency vs dollar"
CURRENCIES = ["EURUSD", "GBPUSD", "AUDUSD", "NZDUSD", "USDJPY", "USDCAD", "USDCHF"]
MIN_IS = 0.5                                                    # a family goes on only with this Sharpe before 2019


def panel(m: S.Market, syms: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """close (log), next open-to-open return, daily volatility, cost per side and swap per night."""
    close, oo, vol, side, swap = {}, {}, {}, {}, {}
    for s in syms:
        if not m.has(s):
            continue
        d = m.bars(s, "D1")
        sign = -1.0 if s in USD_BASE else 1.0
        close[s] = sign * np.log(d["close"])
        oo[s] = sign * (d["open"].shift(-1) / d["open"] - 1.0).shift(-1)       # held from the open after the decision
        vol[s] = T.vol(d)
        side[s], swap[s] = m.cost(s)
    return pd.DataFrame(close), pd.DataFrame(oo), pd.DataFrame(vol), pd.Series(side), pd.Series(swap)


def net(w: pd.DataFrame, oo: pd.DataFrame, side: pd.Series, swap: pd.Series) -> pd.Series:
    """Account return of weights decided at each close (row t earns the open of t+1 to the open of t+2)."""
    w = w.fillna(0.0)
    turn = (w - w.shift(1).fillna(0.0)).abs()
    r = (w * oo).sum(axis=1) - (turn * side).sum(axis=1) - (w.abs() * swap).sum(axis=1)
    return r.shift(1).dropna()                                  # same dating as mt5_study: the day the position is held


def cross_section(m: S.Market, syms: list[str], lookback: int, skip: int, reverse: bool) -> pd.Series:
    close, oo, vol, side, swap = panel(m, syms)
    score = (close.shift(skip) - close.shift(skip + lookback)) / (vol * np.sqrt(lookback))
    n = score.notna().sum(axis=1)
    rank = score.rank(axis=1, pct=True)
    k = 1.0 / 3.0
    pos = (rank > 1 - k).astype(float) - (rank <= k).astype(float)
    pos = pos.where(score.notna()).where(n >= 4, 0.0) * (-1.0 if reverse else 1.0)
    per_side = pos.abs().sum(axis=1).replace(0, np.nan) / 2
    w = pos.div(per_side, axis=0) * (0.01 / vol).clip(upper=3.0) / 2      # each side worth about 1% of daily move
    return net(w, oo, side, swap)


def premium(m: S.Market, syms: list[str]) -> pd.Series:
    close, oo, vol, side, swap = panel(m, syms)
    w = (0.01 / vol).clip(upper=3.0).where(close.notna())
    w = w.div(w.notna().sum(axis=1).replace(0, np.nan), axis=0)
    return net(w, oo, side, swap)


def variants(m: S.Market) -> dict[str, pd.Series]:
    v = {}
    for n in (60, 126, 252):
        v[f"momento_relativo|indices|{n}d"] = cross_section(m, INDEX, n, 5, False)
    for n in (20, 60, 126):
        v[f"momento_relativo|moedas|{n}d"] = cross_section(m, CURRENCIES, n, 1, False)
    for n in (1, 3, 5):
        v[f"reversao_relativa|indices|{n}d"] = cross_section(m, INDEX, n, 0, True)
        v[f"reversao_relativa|moedas|{n}d"] = cross_section(m, CURRENCIES, n, 0, True)
    v["premio|US500"] = premium(m, ["US500"])
    v["premio|indices dos EUA"] = premium(m, ["US500", "US30", "US2000"])
    v["premio|todos os indices"] = premium(m, INDEX)
    v["premio|ouro"] = premium(m, ["XAUUSD"])
    return v


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/mt5")
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else folder
    m = S.Market(folder)
    v = variants(m)
    gold = S.trend(m, S.METALS, "ema50_200", True)
    rows = []
    for k, x in v.items():
        a, b = S.before_after(x)
        fam, grp, var = (k.split("|") + [""])[:3]
        rows.append({"familia": fam, "grupo": grp, "variante": var, "inicio": x.index[0].date(), "sharpe antes de 2019": a,
                     "sharpe 2019-2026": b, "correlacao com tendencia do ouro": round(float(x.corr(gold)), 2)})
    table = pd.DataFrame(rows)
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(table.to_string(index=False))

    # Choice on the days before 2019 only. A family stands alone with Sharpe >= MIN_IS; it joins the
    # gold and silver trend if the equal-risk pair beats the trend alone on their common days.
    best = table.loc[table.groupby(["familia", "grupo"])["sharpe antes de 2019"].idxmax()]
    scale = lambda s: s / s[s.index < S.SPLIT].std()  # noqa: E731
    cand, joined = {"tendencia de ouro e prata (base)": gold}, []
    print("\nescolha antes de 2019 (melhor de cada familia e grupo):")
    for _, r in best.iterrows():
        key = "|".join(x for x in (r["familia"], r["grupo"], r["variante"]) if x)
        pair = pd.DataFrame({"a": scale(gold), "b": scale(v[key])}).dropna()
        early = pair[pair.index < S.SPLIT]
        alone, both = S.sharpe(early["a"]), S.sharpe(early.mean(axis=1))
        ok = r["sharpe antes de 2019"] > 0 and both > alone
        print(f"  {key:40s} sozinha {r['sharpe antes de 2019']:5.2f} | ouro e prata nos mesmos dias {alone:5.2f} | os dois juntos {both:5.2f} | {'entra' if ok else 'fica fora'}")
        if r["sharpe antes de 2019"] >= MIN_IS:
            cand[key] = v[key]
        if ok:
            joined.append(key)
            cand[f"carteira: ouro e prata + {key}"] = pair.mean(axis=1)
    if len(joined) > 1:
        cand["carteira: ouro e prata + todas as que entram"] = pd.DataFrame({"g": scale(gold), **{k: scale(v[k]) for k in joined}}).dropna().mean(axis=1)

    from prop.research import stage2 as G
    out = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for k, x in cand.items():
            a, b = x[x.index < S.SPLIT].dropna(), x[x.index >= S.SPLIT].dropna()
            unit = float(a.std())
            p = pd.DataFrame({"net": b, "worst": 0.0})
            j = G.journey(k, G.to_trades(p, unit, False), a.to_numpy() / unit, 0.08, 0.05, 0.030)
            out.append({"motor": k, "sharpe antes de 2019": round(S.sharpe(a), 2), "sharpe 2019-2026": round(S.sharpe(b), 2), **j})
            print(f"  {k[:70]:70s} {out[-1]['sharpe antes de 2019']:5.2f} / {out[-1]['sharpe 2019-2026']:5.2f}  aprovacao {j['aprovacao F1+F2 %']:5.1f}%", flush=True)
    res = pd.DataFrame(out)
    print("\n" + res.T.to_string())
    out_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(out_dir / "novos_motores_variantes.csv", index=False)
    res.to_csv(out_dir / "novos_motores_jornada.csv", index=False)


if __name__ == "__main__":
    main()
