"""Overfitting check: score EVERY configuration of the grid inside and outside the sample.

If tuning on the past had any value, the configurations that did best in-sample would also
do best out-of-sample (positive rank correlation). Run: python -m prop.robustness
"""
from __future__ import annotations

import pandas as pd

from prop.backtest import engine, metrics
from prop.config.settings import RiskConfig
from prop.data.data_loader import load_all
from prop.main import OUT, TIMEFRAMES, split
from prop.strategies import engine_breakout, engine_mean_reversion, hybrid_controller as hc


def main() -> None:
    rows = []
    for name, df in load_all().items():
        ins, oos = split(df)
        for kind, mod in (("breakout", engine_breakout), ("reversion", engine_mean_reversion)):
            for tf in TIMEFRAMES:
                for prm in mod.GRID:
                    sg = hc.engine_signals(df, kind, {"tf": tf, "params": prm})
                    a = metrics.summarize(engine.run({name: ins}, {name: sg.loc[ins.index]}, RiskConfig.plain()))
                    b = metrics.summarize(engine.run({name: oos}, {name: sg.loc[oos.index]}, RiskConfig.plain()))
                    rows.append(dict(mercado=name, motor=kind, tf=tf, params=str(prm),
                                     trades_dentro=a["trades"], R_dentro=a["expect_R"], t_dentro=a["t_stat"],
                                     trades_fora=b["trades"], R_fora=b["expect_R"], t_fora=b["t_stat"]))
    grid = pd.DataFrame(rows)
    OUT.mkdir(exist_ok=True)
    grid.to_csv(OUT / "grade_dentro_vs_fora.csv", index=False)
    ok = grid[(grid["trades_dentro"] >= 40) & (grid["trades_fora"] >= 15)]
    pd.set_option("display.width", 200)
    print(f"{len(grid)} configuracoes, {len(ok)} com trades suficientes")
    print("Correlacao de ranking dentro x fora (expectativa em R):",
          round(ok[["R_dentro", "R_fora"]].corr(method="spearman").iloc[0, 1], 3))
    print("Lucrativas dentro: %.0f%% | lucrativas fora: %.0f%% | lucrativas fora dado que eram dentro: %.0f%%" % (
        100 * (ok["R_dentro"] > 0).mean(), 100 * (ok["R_fora"] > 0).mean(),
        100 * (ok.loc[ok["R_dentro"] > 0, "R_fora"] > 0).mean()))
    print("\nMediana por familia (R por trade):")
    print(ok.groupby(["mercado", "motor", "tf"])[["R_dentro", "R_fora"]].median().round(3))
    print("\nAs 15 melhores dentro da amostra e o que fizeram fora:")
    top = ok.sort_values("t_dentro", ascending=False).head(15)
    print(top[["mercado", "motor", "tf", "R_dentro", "t_dentro", "R_fora", "t_fora", "trades_fora"]].to_string(index=False))


if __name__ == "__main__":
    main()
