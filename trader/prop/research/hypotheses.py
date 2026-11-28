"""Hypotheses 2, 3 and 4 on top of the Stage 2 base (gold and silver trend with the prop-firm guards).

    python -m prop.research.hypotheses C:\\Users\\kenui\\Projetos\\mt5data

Each one changes a single thing and is compared with the base under the same journey. Whatever
has variants is chosen on the days before 2019; 2019-2026 is only read.

  H2  meta-labeling with conformal prediction: a shallow LightGBM, refitted every year on the past
      only, estimates whether a held position gains over the next 5 days; a split-conformal set
      at 80% decides. "estrito" holds only when the set is {gain}; "leve" leaves only when it is {loss}.
  H3  position size: volatility of the falling days only; a patient Bellman policy (finer menu,
      slower discount); a fixed share of the account per day.
  H4  gold and silver read together: half size when only one metal is in an uptrend
      ("confirmacao"); half size when the price is stretched far above its 50-day average
      ("esticado"); both.
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from prop.research import mt5_study as S
from prop.research import stage2 as G

HORIZON = 5
ALPHA = 0.20
FIRST_TEST = 2010
FEATURES = ["gap", "r20", "r60", "r120", "vol_ratio", "hurst", "from_high", "ratio_z", "other_up", "stretch", "dow"]
PATIENT_MENU = np.array([0.0005, 0.001, 0.0015, 0.002, 0.003, 0.004, 0.006])


def features(m: S.Market) -> dict[str, pd.DataFrame]:
    """Everything known at the close of each day, per asset, plus the label (gain over the next 5 days)."""
    d = {s: m.bars(s, "D1") for s in G.SYMS}
    close = pd.DataFrame({s: x["close"] for s, x in d.items()})
    ratio = np.log(close[G.SYMS[0]] / close[G.SYMS[1]])
    ratio_z = (ratio - ratio.rolling(250).mean()) / ratio.rolling(250).std()
    up = {s: d[s]["close"].ewm(span=G.FAST).mean() > d[s]["close"].ewm(span=G.SLOW).mean() for s in G.SYMS}
    out = {}
    for i, s in enumerate(G.SYMS):
        c = d[s]["close"]
        lr = np.log(c).diff()
        vol = lr.ewm(span=G.VOL_SPAN, min_periods=G.VOL_SPAN).std()
        f = pd.DataFrame(index=c.index)
        f["gap"] = (c.ewm(span=G.FAST).mean() / c.ewm(span=G.SLOW).mean() - 1.0) / vol
        for n in (20, 60, 120):
            f[f"r{n}"] = np.log(c).diff(n) / (vol * np.sqrt(n))
        f["vol_ratio"] = lr.rolling(20).std() / lr.rolling(100).std()
        f["hurst"] = G.hurst(np.log(c))
        f["from_high"] = (c / c.rolling(50).max() - 1.0) / vol
        f["ratio_z"] = ratio_z.reindex(c.index) * (1 if i == 0 else -1)
        f["other_up"] = up[G.SYMS[1 - i]].reindex(c.index).astype(float)
        f["stretch"] = (c / c.ewm(span=G.FAST).mean() - 1.0) / (vol * np.sqrt(G.FAST))
        f["dow"] = c.index.dayofweek
        f["on"] = up[s] & (np.arange(len(c)) >= G.SLOW)
        f["y"] = (np.log(c).shift(-HORIZON) - np.log(c) > 0).astype(float).where(c.shift(-HORIZON).notna())
        out[s] = f
    return out


def meta_masks(feat: dict[str, pd.DataFrame]) -> dict[str, dict[str, pd.Series]]:
    """Walk-forward: for each year, fit on everything that was already known, calibrate the conformal
    scores on the last quarter of it, decide the days of that year. Returns 0/1 scales per asset."""
    import lightgbm as lgb
    rows = pd.concat([f[f["on"]].assign(sym=s) for s, f in feat.items()]).dropna(subset=FEATURES).sort_index()
    strict = {s: pd.Series(1.0, index=f.index) for s, f in feat.items()}
    lenient = {s: pd.Series(1.0, index=f.index) for s, f in feat.items()}
    for year in range(FIRST_TEST, int(rows.index.year.max()) + 1):
        start = pd.Timestamp(year, 1, 1)
        known = rows[(rows.index < start - pd.Timedelta(days=HORIZON + 3))].dropna(subset=["y"])   # labels fully in the past
        test = rows[rows.index.year == year]
        if len(known) < 800 or test.empty:
            continue
        cut = int(len(known) * 0.75)
        fit, cal = known.iloc[:cut - HORIZON], known.iloc[cut:]
        model = lgb.LGBMClassifier(n_estimators=200, learning_rate=0.03, max_depth=3, num_leaves=8, min_child_samples=50,
                                   subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=5.0, random_state=11, verbose=-1)
        model.fit(fit[FEATURES], fit["y"])
        pc = model.predict_proba(cal[FEATURES])[:, 1]
        score = np.sort(1.0 - np.where(cal["y"] == 1, pc, 1.0 - pc))               # nonconformity of the true label
        pt = model.predict_proba(test[FEATURES])[:, 1]
        pval = lambda p: (len(score) - np.searchsorted(score, 1.0 - p, side="left") + 1) / (len(score) + 1)  # noqa: E731
        gain_in, loss_in = pval(pt) > ALPHA, pval(1.0 - pt) > ALPHA
        for s in G.SYMS:
            k = (test["sym"] == s).to_numpy()
            strict[s].loc[test.index[k]] = (gain_in & ~loss_in)[k].astype(float)
            lenient[s].loc[test.index[k]] = (~(loss_in & ~gain_in))[k].astype(float)
    return {"H2 estrito (so com conjunto = ganho)": strict, "H2 leve (sai so com conjunto = perda)": lenient}


def gold_silver_scales(feat: dict[str, pd.DataFrame]) -> dict[str, dict[str, pd.Series]]:
    confirm = {s: 0.5 + 0.5 * f["other_up"] for s, f in feat.items()}
    stretched = {s: pd.Series(np.where(f["stretch"] > 2.0, 0.5, 1.0), index=f.index) for s, f in feat.items()}
    return {"H4 confirmacao ouro/prata": confirm, "H4 esticado acima da media": stretched,
            "H4 confirmacao + esticado": {s: confirm[s] * stretched[s] for s in feat}}


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/mt5")
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else folder
    m = S.Market(folder)
    rules = json.loads(G.RULES.read_text())
    firms = [("8% + 5%", rules["padrao"]), ("FTMO 10% + 5%", rules["ftmo"])]
    feat = features(m)
    base = G.portfolio(m)
    # name -> (portfolio, journey options, hypothesis)
    cases: dict[str, tuple[pd.DataFrame, dict, str]] = {"base (linha C)": (base, {}, "base")}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for k, v in meta_masks(feat).items():
            cases[k] = (G.portfolio(m, scale=v), {}, "H2")
    cases["H3 tamanho pela volatilidade de queda"] = (G.portfolio(m, downside=True), {}, "H3")
    cases["H3 politica paciente (menu fino, desconto lento)"] = (base, {"menu": PATIENT_MENU, "discount": 0.9997}, "H3")
    for f in (0.002, 0.003, 0.004):
        cases[f"H3 tamanho fixo {100 * f:.1f}% ao dia"] = (base, {"fixed": f}, "H3")
    for k, v in gold_silver_scales(feat).items():
        cases[k] = (G.portfolio(m, scale=v), {}, "H4")

    rows = []
    for name, (p, opt, hyp) in cases.items():
        a, b = p[p.index < S.SPLIT], p[p.index >= S.SPLIT]
        unit = float(a["net"].std())
        row = {"hipotese": hyp, "caso": name, "sharpe antes de 2019": G.stats(a)["sharpe"], "sharpe 2019-2026": G.stats(b)["sharpe"],
               "dias com posicao %": G.stats(b)["dias com posicao %"], **G.episodes(p, S.SPLIT),
               "queda maxima / dia normal": G.stats(b)["queda maxima / dia normal"]}
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for firm, r in firms:
                j = G.journey(name, G.to_trades(b, unit, True), a["net"].to_numpy() / unit, r["meta_fase1"], r["meta_fase2"], 0.030, **opt)
                row.update({f"{k} [{firm}]": v for k, v in j.items() if k in (
                    "aprovacao F1+F2 %", "aprovado em 12 meses %", "reprova por perda diaria %", "reprova por perda total %", "sem decisao %",
                    "dias ate a meta da Fase 1 (media)", "dias ate aprovar F1+F2 (media)", "saques 12 meses US$")})
        rows.append(row)
        print(f"{name:50s} sharpe {row['sharpe antes de 2019']:5.2f} / {row['sharpe 2019-2026']:5.2f}  aprovacao "
              f"{row['aprovacao F1+F2 % [8% + 5%]']:5.1f}% / {row['aprovacao F1+F2 % [FTMO 10% + 5%]']:5.1f}%", flush=True)
    table = pd.DataFrame(rows)
    out_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(out_dir / "hipoteses_2_3_4.csv", index=False)
    pd.set_option("display.width", 300, "display.max_columns", 40)
    print("\n" + table.T.to_string())


if __name__ == "__main__":
    main()
