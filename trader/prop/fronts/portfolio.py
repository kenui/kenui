"""V9 portfolio: which fronts are added to the anchor and how the risk is split.

    python -m prop.fronts.portfolio C:\\Users\\kenui\\Projetos\\mt5data

Front 1 (anchor) is the gold and silver trend sized by downside volatility. For every other front
the variant with the best Sharpe before 2019 is the candidate. It is added only if, before 2019,
(a) its own net Sharpe is positive, (b) its daily correlation with every front already in is below
0.25 and (c) the combined Sharpe goes up. Risk is split by hierarchical risk parity on the
pre-2019 days. 2019-2026 is only read. If something is added, the 10,000-account journey is run
for the anchor alone and for the portfolio.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import leaves_list, linkage
from scipy.spatial.distance import squareform

from prop.fronts import asia, ny_open
from prop.research import mt5_study as S
from prop.research import stage2 as G

MAX_CORR = 0.25


def hrp(x: pd.DataFrame) -> pd.Series:
    """Hierarchical risk parity (Lopez de Prado): cluster by correlation, then split the risk down the
    tree in inverse proportion to each branch's variance."""
    if x.shape[1] == 1:
        return pd.Series(1.0, index=x.columns)
    cov, corr = x.cov(), x.corr()
    dist = np.sqrt(np.clip((1 - corr) / 2, 0, 1))
    order = [x.columns[i] for i in leaves_list(linkage(squareform(dist.to_numpy(), checks=False), "single"))]
    w = pd.Series(1.0, index=order)
    groups = [order]
    while groups:
        groups = [g[i:j] for g in groups for i, j in ((0, len(g) // 2), (len(g) // 2, len(g))) if len(g) > 1]
        for a, b in zip(groups[::2], groups[1::2]):
            var = []
            for g in (a, b):
                iv = 1 / np.diag(cov.loc[g, g])
                iv /= iv.sum()
                var.append(float(iv @ cov.loc[g, g].to_numpy() @ iv))
            share = 1 - var[0] / (var[0] + var[1])
            w[a] *= share
            w[b] *= 1 - share
    return w / w.sum()


def gate(anchor: pd.Series, candidates: dict[str, pd.Series]) -> tuple[dict[str, pd.Series], list[dict]]:
    """Add candidates one by one, on the days before 2019 only."""
    early = lambda s: s[s.index < S.SPLIT]  # noqa: E731
    inside, log = {"frente 1": anchor}, []
    for name, x in candidates.items():
        own = S.sharpe(early(x))
        frame = pd.DataFrame({**inside, name: x}).dropna()
        frame = early(frame)
        corr = float(frame.corr()[name].drop(name).abs().max()) if len(frame) > 60 else float("nan")
        unit = frame / frame.std()
        before, after = S.sharpe(unit.drop(columns=name).mean(axis=1)), S.sharpe(unit.mean(axis=1))
        ok = bool(own > 0 and corr < MAX_CORR and after > before)
        log.append({"frente": name, "sharpe proprio antes de 2019": round(own, 2), "sharpe proprio 2019-2026": round(S.sharpe(x[x.index >= S.SPLIT]), 2),
                    "maior correlacao com as frentes ativas": round(corr, 2), "sharpe do conjunto sem ela": round(before, 2),
                    "sharpe do conjunto com ela": round(after, 2), "decisao": "entra" if ok else "fica fora"})
        if ok:
            inside[name] = x
    return inside, log


def best_before(variants: dict[str, tuple[pd.Series, list[float]]]) -> tuple[str, pd.Series, list[float], pd.DataFrame]:
    rows = []
    for k, (d, tr) in variants.items():
        a, b = S.before_after(d)
        t = np.array(tr)
        oos_days = d[d.index >= S.SPLIT]
        rows.append({"variante": k, "sharpe antes de 2019": a, "sharpe 2019-2026": b, "trades": len(t),
                     "trades por mes": round(len(t) / max((d.index[-1] - d.index[0]).days / 30.44, 1), 1),
                     "acerto liquido %": round(100 * float((t > 0).mean()), 1) if len(t) else np.nan,
                     "profit factor": round(float(t[t > 0].sum() / -t[t <= 0].sum()), 2) if (t > 0).any() and (t <= 0).any() else np.nan,
                     "dias positivos % (2019-2026)": round(100 * float((oos_days > 0).mean()), 1)})
    table = pd.DataFrame(rows)
    k = table.loc[table["sharpe antes de 2019"].fillna(-9).idxmax(), "variante"]
    return k, variants[k][0], variants[k][1], table


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/mt5")
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else folder
    m = S.Market(folder)
    pd.set_option("display.width", 250, "display.max_columns", 30)
    anchor = G.portfolio(m, downside=True)
    cands, tables = {}, []
    for label, mod in (("frente 2 (Asia)", asia), ("frente 3 (abertura NY)", ny_open)):
        k, days, _, table = best_before(mod.variants(m))
        print(f"\n=== {label}: variantes ===\n{table.to_string(index=False)}\nmelhor antes de 2019: {k}")
        cands[f"{label}: {k}"] = days
        tables.append(table.assign(frente=label))
    inside, log = gate(anchor["net"], cands)
    log = pd.DataFrame(log)
    print("\n=== Portao de entrada no portfolio (so dados antes de 2019) ===\n" + log.to_string(index=False))
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.concat(tables).to_csv(out_dir / "v9_frentes_variantes.csv", index=False)
    log.to_csv(out_dir / "v9_portao.csv", index=False)
    if len(inside) == 1:
        print("\nNenhuma frente nova entrou. O portfolio continua sendo a Frente 1 sozinha.")
        return
    frame = pd.DataFrame(inside).fillna(0.0)
    frame = frame[frame.index >= max(s.index[0] for s in inside.values())]
    early = frame[frame.index < S.SPLIT]
    w = hrp(early / early.std())
    print("\npesos por paridade de risco hierarquica:\n" + w.round(3).to_string())
    port = ((frame / early.std()) * w).sum(axis=1)
    worst = anchor["worst"].reindex(port.index).fillna(0.0) / early["frente 1"].std() * w["frente 1"] + \
        sum((frame[c] / early[c].std()).clip(upper=0.0) * 1.5 * w[c] for c in frame.columns if c != "frente 1")
    rows = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for name, p in (("Frente 1 sozinha", anchor), ("Portfolio", pd.DataFrame({"net": port, "worst": worst}))):
            a, b = p[p.index < S.SPLIT], p[p.index >= S.SPLIT]
            unit = float(a["net"].std())
            for firm, t1 in (("8% + 5%", 0.08), ("FTMO 10% + 5%", 0.10)):
                rows.append({"caso": name, "mesa": firm, "sharpe 2019-2026": round(S.sharpe(b["net"]), 2),
                             **G.journey(name, G.to_trades(b, unit, True), a["net"].to_numpy() / unit, t1, 0.05, 0.030)})
    res = pd.DataFrame(rows)
    print("\n" + res.T.to_string())
    res.to_csv(out_dir / "v9_jornada.csv", index=False)


if __name__ == "__main__":
    main()
