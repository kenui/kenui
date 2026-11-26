"""Quant V5 (final version): run everything and print the report.

    python -m prop.quant_main                 uses the cached walk-forward if it exists
    python -m prop.quant_main --rebuild       refits every model (about 25 minutes)
    python -m prop.quant_main --no-cpcv       skips the combinatorial cross-validation

Steps: data -> events and labels -> purged walk-forward (all model versions) -> trades each
version would have taken -> Bellman policies -> history in the real order -> Monte Carlo of the
whole journey (Phase 1, Phase 2, 12 months funded; 10,000 accounts) -> DSR, PBO, CPCV ->
SQLite state -> dashboard. The last block runs the same controller on the one alpha that showed
a real edge in the earlier research (short after a listing).
"""
from __future__ import annotations

import argparse
import dataclasses
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from prop.backtest import monte_carlo_prop as mcp
from prop.backtest import selection as sel
from prop.backtest import walk_forward as wf
from prop.candidates import listing_alpha
from prop.config.quant import Q
from prop.data.multi_asset_loader import aligned_returns, load_portfolio
from prop.persistence.state_store import StateStore
from prop.risk import bellman_barrier_controller as bbc
from prop.risk import dual_bellman_solver as dbs
from prop.risk.prop_firm_controller import Controller, presets
from prop.validation import cpcv_dsr_and_mc as val

CACHE = Path("data/quant_oos.pkl")
CPCV_CACHE = Path("data/quant_cpcv.pkl")
VERSIONS = ("v1", "v2", "v3", "v4", "v5", "v5s")
DESIGN_EDGE = 0.05      # edge (in R per trade) the Bellman policies are designed for


def walk_forward(rebuild: bool):
    fast, slow = load_portfolio()
    if CACHE.exists() and not rebuild:
        events, oos, cal = pickle.load(CACHE.open("rb"))
    else:
        print("Montando eventos e rotulos...", flush=True)
        events, ctx = wf.build_events(fast, slow)
        print("Walk-forward com purga (treina 6 meses, testa 1)...", flush=True)
        oos = wf.run(events, ctx, slow)
        cal = oos.attrs["calibration"]
        pickle.dump((events, oos, cal), CACHE.open("wb"))
    oos.attrs["calibration"] = cal
    return fast, slow, events, oos


def solve_policies(r: np.ndarray, edge: float, tag: str, trades_per_day: float = 2.0, discount: float = 0.999,
                   actions: np.ndarray = bbc.ACTIONS, funded_actions: np.ndarray = dbs.FUNDED_ACTIONS):
    vals, probs = bbc.outcome_distribution(r, design_edge=edge, bin_r=0.25)
    kw = dict(trades_per_day=trades_per_day, discount=discount, actions=actions)
    p1 = bbc.solve_evaluation(vals, probs, Q.phase1_target, **kw)
    p2 = bbc.solve_evaluation(vals, probs, Q.phase2_target, **kw)
    hv = dbs.solve_funded(vals, probs, actions=funded_actions)
    print(f"  politicas {tag}: risco medio F1 {100 * p1.risk.mean():.2f}%  F2 {100 * p2.risk.mean():.2f}%  "
          f"conta financiada {100 * hv.risk.mean():.2f}%", flush=True)
    return {0: p1, 1: p2}, hv


def daily_series(tr: sel.Trades, days: pd.DatetimeIndex, risk: float = 0.005) -> np.ndarray:
    """Daily result of the signal side alone (fixed risk), on a calendar of every day."""
    out = pd.Series(0.0, index=days)
    if len(tr):
        pnl = risk * tr.R[np.arange(len(tr)), tr.arm] * tr.mult
        d = pd.DatetimeIndex(tr.time).tz_localize("UTC").normalize() if pd.DatetimeIndex(tr.time).tz is None \
            else pd.DatetimeIndex(tr.time).normalize()
        s = pd.Series(pnl).groupby(d.values).sum()
        s.index = pd.DatetimeIndex(s.index).tz_localize(None)
        out = out.add(s.reindex(days, fill_value=0.0), fill_value=0.0)
    return out.to_numpy()


def trade_stats(tr: sel.Trades) -> dict:
    if not len(tr):
        return {"trades": 0}
    r = tr.R[np.arange(len(tr)), tr.arm]
    t = r.mean() / (r.std(ddof=1) / np.sqrt(len(r))) if len(r) > 2 and r.std() > 0 else 0.0
    return {"trades": len(r), "R_medio": round(float(r.mean()), 3), "t": round(float(t), 2),
            "acerto_%": round(100 * float((r > 0).mean()), 1)}


def variants_grid(oos: pd.DataFrame, corr, days: pd.DatetimeIndex) -> tuple[pd.DataFrame, dict]:
    """Every variant that was on the table: version x threshold shift x exit policy."""
    cols, default = {}, {}
    for v in VERSIONS[1:]:
        for shift in (-0.05, 0.0, 0.05):
            for arm in (None, "arm0", "arm1", "arm2"):
                tr = sel.select(oos, v, corr, threshold_shift=shift, fixed_arm=arm)
                cols[f"{v}|{shift:+.2f}|{arm or 'padrao'}"] = daily_series(tr, days)
                if shift == 0.0 and arm is None:
                    default[v] = tr
    for arm in ("plain", "arm0", "arm1", "arm2"):
        cols[f"v1|+0.00|{arm}"] = daily_series(sel.select(oos, "v1", corr, fixed_arm=arm), days)
    default["v1"] = sel.select(oos, "v1", corr)
    return pd.DataFrame(cols, index=days), default


def cpcv_paths(events, slow, rebuild: bool):
    if CPCV_CACHE.exists() and not rebuild:
        return pickle.load(CPCV_CACHE.open("rb"))
    print("CPCV (6 grupos, 2 de fora, 15 ajustes, 5 caminhos)...", flush=True)
    fast, slow2 = load_portfolio()
    ev, ctx = wf.build_events(fast, slow2)
    paths = val.cpcv(ev, ctx, slow2)
    cals = paths[0].attrs["calibration"]
    pickle.dump((paths, cals), CPCV_CACHE.open("wb"))
    return paths, cals


def cpcv_summary(paths, cals, corr, days_all) -> pd.DataFrame:
    rows = []
    for v in ("v5", "v5s"):
        srs, means = [], []
        for p in paths:
            p.attrs["calibration"] = cals
            tr = sel.select(p, v, corr)
            d = pd.date_range(pd.Timestamp(p["time"].min()).tz_localize(None).normalize(),
                               pd.Timestamp(p["time"].max()).tz_localize(None).normalize())
            srs.append(val.sharpe(daily_series(tr, d)) * np.sqrt(365))
            means.append(trade_stats(tr).get("R_medio", 0.0))
        rows.append({"versao": v, "caminhos": len(srs), "sharpe_medio": round(float(np.mean(srs)), 2),
                     "sharpe_pior": round(float(np.min(srs)), 2), "sharpe_melhor": round(float(np.max(srs)), 2),
                     "caminhos_positivos": int(np.sum(np.array(srs) > 0)), "R_medio_por_trade": round(float(np.mean(means)), 3)})
    return pd.DataFrame(rows)


def zero_edge(tr: sel.Trades) -> sel.Trades:
    """Same trades with the average result forced to zero: what luck alone achieves."""
    r = tr.R - tr.R[np.arange(len(tr)), tr.arm].mean()
    return dataclasses.replace(tr, R=r, MAE=np.minimum(tr.MAE, r))


def dashboard(hist: dict, mc_rows: pd.DataFrame, fan: np.ndarray, side: pd.DataFrame, path: Path, title: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 3, figsize=(19, 10))
    for name, h in hist.items():
        if h.get("trades", 0):
            ax[0, 0].plot(pd.DatetimeIndex(h["time"]), 100 * h["curve"], label=name, lw=1.2)
    ax[0, 0].axhline(0, color="k", lw=0.5)
    ax[0, 0].set_title("Resultado acumulado fora da amostra (ordem real, % da conta)")
    ax[0, 0].legend(fontsize=7)
    names = mc_rows["versao"].tolist()
    y = np.arange(len(names))
    ax[0, 1].barh(y, mc_rows["passa_F1+F2_%"], color="#3b7dd8")
    ax[0, 1].set_yticks(y, names, fontsize=7)
    ax[0, 1].invert_yaxis()
    ax[0, 1].set_title("Aprovacao nas 2 fases (% de 10.000 contas simuladas)")
    ax[0, 2].barh(y, mc_rows["EV_usd"], color=["#2a9d5c" if v > 0 else "#c94f4f" for v in mc_rows["EV_usd"]])
    ax[0, 2].set_yticks(y, names, fontsize=7)
    ax[0, 2].invert_yaxis()
    ax[0, 2].axvline(0, color="k", lw=0.5)
    ax[0, 2].set_title("Valor esperado por tentativa (USD, taxa de 50)")
    if len(fan):
        ax[1, 0].plot(100 * fan[:150].T, lw=0.5, alpha=0.5)
        ax[1, 0].axhline(100 * Q.phase1_target, color="g", ls="--")
        ax[1, 0].axhline(-100 * Q.max_dd_limit, color="r", ls="--")
        ax[1, 0].set_xlim(0, min(fan.shape[1], 150))
    ax[1, 0].set_title("Fase 1: 150 contas simuladas, V5 + alfa de listagem")
    ax[1, 1].barh(y, mc_rows["sobrevive_12m_%"], color="#8a6fd1")
    ax[1, 1].set_yticks(y, names, fontsize=7)
    ax[1, 1].invert_yaxis()
    ax[1, 1].set_title("Contas financiadas que sobrevivem 12 meses (%)")
    ax[1, 2].axis("off")
    tb = ax[1, 2].table(cellText=side.astype(str).values, rowLabels=side.index, colLabels=side.columns, loc="center")
    tb.auto_set_font_size(False)
    tb.set_fontsize(8)
    tb.scale(1, 1.3)
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--no-cpcv", action="store_true")
    ap.add_argument("--paths", type=int, default=Q.mc_paths)
    args = ap.parse_args()
    warnings.filterwarnings("ignore")
    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 40)
    Q.out_dir.mkdir(parents=True, exist_ok=True)

    print("1) Dados e walk-forward", flush=True)
    fast, slow, events, oos = walk_forward(args.rebuild)
    corr = sel.rolling_correlations(aligned_returns(slow))
    oos_start = oos["time"].min()
    days = pd.date_range(pd.Timestamp(oos_start).tz_localize(None).normalize(),
                          pd.Timestamp(oos["time"].max()).tz_localize(None).normalize())
    print(f"   {len(events)} sinais primarios, {len(oos)} fora da amostra, de {oos_start:%Y-%m} a {oos['time'].max():%Y-%m}")

    print("2) Politicas de risco (Bellman) calculadas so com dados anteriores ao periodo de teste", flush=True)
    warm = events[events["label_end"] < oos_start]
    barrier, harvest = solve_policies(warm["r_arm1"].to_numpy(), DESIGN_EDGE, "V4/V5")
    ctl = presets(sel.THRESHOLDS)
    for c in ctl.values():
        c.barrier, c.harvest = barrier, harvest

    print("3) Trades de cada versao, grade de variantes, DSR e PBO", flush=True)
    grid, chosen = variants_grid(oos, corr, days)
    sr = grid.apply(lambda c: val.sharpe(c.to_numpy()))
    pbo = val.pbo_cscv(grid.to_numpy())
    quality = []
    for v in VERSIONS:
        d = daily_series(chosen[v], days)
        quality.append({"versao": ctl[v].name, **trade_stats(chosen[v]),
                        "sharpe_anual": round(val.sharpe(d) * np.sqrt(365), 2),
                        "DSR": round(val.deflated_sharpe(d, len(sr), float(sr.var())), 3)})
    quality = pd.DataFrame(quality)
    print(quality.to_string(index=False))
    print(f"   PBO (CSCV, {pbo['variants']} variantes, {pbo['splits']} divisoes): {pbo['pbo']:.2f}   "
          f"chance de a melhor variante perder fora da amostra: {pbo['oos_loss_prob']:.2f}")

    print("4) Historico na ordem real (desafio reiniciado a cada aprovacao ou reprovacao)", flush=True)
    hist = {ctl[v].name: mcp.history(chosen[v], ctl[v]) for v in VERSIONS}
    hrows = pd.DataFrame([{k: x for k, x in h.items() if k not in ("curve", "time", "daily")} for h in hist.values()])
    print(hrows.to_string(index=False))

    print(f"5) Monte Carlo da jornada completa ({args.paths} contas por versao)", flush=True)
    stats, fan = [], np.empty((0, 0))
    for v in VERSIONS:
        st, out = mcp.monte_carlo(chosen[v], ctl[v], args.paths, record_paths=150 if v == "v5s" else 0)
        stats.append(st.row())
        if v == "v5s" and out:
            fan = out["xpath"]
    luck = dataclasses.replace(ctl["v4"], name="referencia: sorte pura (trades do V4 com media zero)")
    stats.append(mcp.monte_carlo(zero_edge(chosen["v4"]), luck, args.paths)[0].row())
    mc = pd.DataFrame(stats)
    print(mc.to_string(index=False))

    cp = None
    if not args.no_cpcv:
        print("6) CPCV", flush=True)
        paths, cals = cpcv_paths(events, slow, args.rebuild)
        cp = cpcv_summary(paths, cals, corr, days)
        print(cp.to_string(index=False))

    print("7) Estado persistente (SQLite, modo WAL)", flush=True)
    ex = chosen["v5s"].extra or {}
    store = StateStore(Q.state_db)
    store.save_learners(ex.get("aci"), ex.get("bandit"), ex.get("cusum"),
                        account={"phase": 0, "x_total": 0.0, "x_daily": 0.0})
    aci = ex.get("aci")
    print(f"   {Q.state_db}: ACI alpha = {aci.alpha:.3f} apos {aci.n_updates} sinais com resultado conhecido; "
          f"LinUCB e CUSUM gravados na mesma transacao")
    store.close()

    print("\n=== Quant V5 Base vs Quant V5 + Path Signatures & ACI ===")
    a, b = ctl["v5"].name, ctl["v5s"].name
    q, m = quality.set_index("versao"), mc.set_index("versao")
    side = pd.DataFrame({
        "Quant V5 Base": [q.loc[a, "trades"], q.loc[a, "R_medio"], q.loc[a, "sharpe_anual"], q.loc[a, "DSR"], round(pbo["pbo"], 2),
                          m.loc[a, "passa_F1+F2_%"], m.loc[a, "viola_diario_%"], m.loc[a, "sobrevive_12m_%"],
                          m.loc[a, "saques_12m_usd"], m.loc[a, "EV_usd"]],
        "V5 + Signatures & ACI": [q.loc[b, "trades"], q.loc[b, "R_medio"], q.loc[b, "sharpe_anual"], q.loc[b, "DSR"], round(pbo["pbo"], 2),
                                  m.loc[b, "passa_F1+F2_%"], m.loc[b, "viola_diario_%"], m.loc[b, "sobrevive_12m_%"],
                                  m.loc[b, "saques_12m_usd"], m.loc[b, "EV_usd"]]},
        index=["Trades fora da amostra", "Resultado medio (R)", "Sharpe anual", "Deflated Sharpe (DSR)", "PBO (grade toda)",
               "Aprovacao F1+F2 (%)", "Violacao de DD diario (%)", "Sobrevive 12 meses (%)",
               "Saques liquidos medios (US$)", "EV por tentativa (US$)"])
    print(side.to_string())

    print("\n=== Mesmo controlador V5 com o alfa de listagem (short 24h apos a listagem) ===", flush=True)
    table = listing_alpha.trade_table()
    alpha_r = listing_alpha.net_r(table)            # costs and funding included
    # Risk menu and patience of the solver came from a small declared sweep (max risk 1%, 1.5%, 2%;
    # discount 0.97, 0.99, 0.998) judged at HALF the measured edge: the patient policy won.
    acts = np.array([0.0025, 0.005, 0.0075, 0.010, 0.0125, 0.015, 0.02])
    facts = np.array([0.0035, 0.005, 0.0075, 0.010])
    alpha_rows = []
    for label, cut in (("alfa listagem, vantagem medida", 0.0), ("alfa listagem, metade da vantagem", 0.5),
                       ("alfa listagem, sem vantagem", 1.0)):
        tr = listing_alpha.trades(cut, table)
        r = tr.R[:, 2]
        bar, hv = solve_policies(alpha_r, 0.5 * float(alpha_r.mean()), label, trades_per_day=1.0,
                                 discount=0.998, actions=acts, funded_actions=facts)
        c = Controller(f"V5 + {label}", 0.0, "bellman", 0.005, 0.02, daily_kill=Q.hard_daily_kill, cap_to_kill=True,
                       zones=False, funded="harvest", payout="trigger", barrier=bar, harvest=hv)
        st, out = mcp.monte_carlo(tr, c, args.paths, record_paths=150 if cut == 0.0 else 0)
        st = st.row()
        st["R_medio"] = round(float(r.mean()), 3)
        alpha_rows.append(st)
        if cut == 0.0:
            fan = out["xpath"]
            h = mcp.history(tr, c)
            hist[c.name] = h
            print(f"   ordem real das {len(tr)} listagens: {h['aprovacoes_F1']} aprovacoes da Fase 1, {h['reprovacoes']} reprovacoes, "
                  f"retorno {h['retorno_%']}%, pior queda {h['dd_max_%']}%, profit factor {h['profit_factor']}", flush=True)
            roll = pd.DataFrame([{"regra": "V5 Bellman", **mcp.rolling_starts(tr, c)}] + [
                {"regra": f"risco fixo {100 * f:.1f}%",
                 **mcp.rolling_starts(tr, Controller("f", 0.0, "fixed", f, f, daily_kill=Q.hard_daily_kill))}
                for f in (0.005, 0.01, 0.02)])
            print("   Desafio iniciado em cada listagem real, sem sorteio (indefinido = o historico acabou antes):")
            print(roll.to_string(index=False), flush=True)
            roll.to_csv(Q.out_dir / "quant_v5_alfa_ordem_real.csv", index=False)
        fixed = Controller(f"risco fixo 1% + {label}", 0.0, "fixed", 0.01, 0.01, daily_kill=Q.hard_daily_kill)
        st = mcp.monte_carlo(tr, fixed, args.paths)[0].row()
        st["R_medio"] = round(float(r.mean()), 3)
        alpha_rows.append(st)
    alpha = pd.DataFrame(alpha_rows)
    print(alpha.to_string(index=False))
    try:
        vm = listing_alpha.variant_matrix().fillna(0.0)
        vsr = vm.apply(lambda c: val.sharpe(c.to_numpy()))
        vp = val.pbo_cscv(vm.to_numpy(), blocks=8)
        rule = "w24_h7_s0.3"
        half = len(vm) // 2
        print(f"   Regra escolhida entre {vm.shape[1]} variantes (espera x duracao x stop); todas as {int((vm.mean() > 0).sum())} "
              f"variantes com media positiva.\n   DSR da regra: {val.deflated_sharpe(vm[rule].to_numpy(), vm.shape[1], float(vsr.var())):.2f}   "
              f"PBO: {vp['pbo']:.2f}   melhor variante perde fora da amostra em {100 * vp['oos_loss_prob']:.0f}% das divisoes\n"
              f"   Retorno medio por operacao: primeira metade das listagens {100 * vm[rule].iloc[:half].mean():.1f}%, "
              f"segunda metade {100 * vm[rule].iloc[half:].mean():.1f}%")
    except Exception as exc:  # the grid needs the futures histories; the rest of the report does not
        print(f"   (grade de variantes da listagem indisponivel: {exc})")

    mc_all = pd.concat([mc, alpha.drop(columns="R_medio")], ignore_index=True)
    mc_all.to_csv(Q.out_dir / "quant_v5_monte_carlo.csv", index=False)
    quality.to_csv(Q.out_dir / "quant_v5_qualidade.csv", index=False)
    side.to_csv(Q.out_dir / "quant_v5_base_vs_assinaturas_aci.csv")
    if cp is not None:
        cp.to_csv(Q.out_dir / "quant_v5_cpcv.csv", index=False)
    dashboard(hist, mc_all, fan, side, Q.out_dir / "quant_v5_final_dashboard.png",
              "Quant V5 final: mesa proprietaria de 2 fases, conta de 10.000 USD")
    print(f"\nPainel: {Q.out_dir / 'quant_v5_final_dashboard.png'}")


if __name__ == "__main__":
    main()
