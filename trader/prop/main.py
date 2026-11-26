"""Prop-challenge lab: download data, tune on the first 70%, judge on the last 30%.

    python -m prop.main --optimize   # re-tune parameters on the in-sample part (slow, ~6 min)
    python -m prop.main              # use the saved parameters

Four simulations on the same data, per market and for the three markets in one account:
  1. Engine 1 only (breakout)            3. Hybrid (engine chosen by regime)
  2. Engine 2 only (mean reversion)      4. Hybrid + prop-firm locks and dynamic lot
Then the challenge is simulated thousands of times (Monte Carlo) on the out-of-sample trades.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from prop.backtest import engine, metrics, montecarlo as mc  # noqa: E402
from prop.config.settings import INSTRUMENTS, SETTINGS, RiskConfig  # noqa: E402
from prop.data.data_loader import load_all  # noqa: E402
from prop.strategies import engine_breakout, engine_mean_reversion, hybrid_controller as hc  # noqa: E402

HERE = Path(__file__).resolve().parent
PARAMS = HERE / "config" / "best_params.json"
OUT = HERE / "output"
TIMEFRAMES = ("15min", "1h", "4h")
MIN_TRADES = 40
MODES = ("1 Rompimento", "2 Reversao", "3 Hibrido", "4 Hibrido+travas")


def split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cut = df.index[int(len(df) * SETTINGS.in_sample_frac)]
    return df[df.index < cut], df[df.index >= cut]


def score(bars: pd.DataFrame, name: str, sig: pd.DataFrame) -> dict:
    res = engine.run({name: bars}, {name: sig.loc[bars.index]}, RiskConfig.plain())
    return metrics.summarize(res)


def optimize(data: dict[str, pd.DataFrame]) -> dict:
    """Pick, per market, the timeframe and parameters of each engine with the best in-sample
    t-statistic, then the regime thresholds for the hybrid. Only in-sample bars are scored."""
    best: dict = {}
    for name, df in data.items():
        ins, _ = split(df)
        best[name] = {}
        for kind, mod in (("breakout", engine_breakout), ("reversion", engine_mean_reversion)):
            top, top_t, tried = None, -1e9, 0
            for tf in TIMEFRAMES:
                for prm in mod.GRID:
                    spec = {"tf": tf, "params": prm}
                    m = score(ins, name, hc.engine_signals(df, kind, spec))
                    tried += 1
                    if m["trades"] >= MIN_TRADES and m["t_stat"] > top_t:
                        top, top_t = spec, m["t_stat"]
            best[name][kind] = {**top, "in_sample_t": top_t, "tried": tried}
            print(f"  {name} {kind}: {top['tf']} {top['params']}  t={top_t}  (melhor de {tried})", flush=True)
        top, top_t = None, -1e9
        for reg in hc.REGIME_GRID:
            m = score(ins, name, hc.signals(df, best[name]["breakout"], best[name]["reversion"], reg))
            if m["trades"] >= 15 and m["t_stat"] > top_t:  # the hybrid trades less than each engine
                top, top_t = reg, m["t_stat"]
        best[name]["regime"] = top or hc.REGIME_GRID[0]
        print(f"  {name} regime: {best[name]['regime']}  t={top_t}", flush=True)
    PARAMS.write_text(json.dumps(best, indent=1))
    return best


def build_signals(data: dict[str, pd.DataFrame], best: dict) -> dict[str, dict[str, pd.DataFrame]]:
    """signals[mode][market], computed on the whole history (indicators only look backwards)."""
    out: dict[str, dict[str, pd.DataFrame]] = {m: {} for m in MODES}
    for name, df in data.items():
        b = best[name]
        hyb = hc.signals(df, b["breakout"], b["reversion"], b["regime"])
        out[MODES[0]][name] = hc.engine_signals(df, "breakout", b["breakout"])
        out[MODES[1]][name] = hc.engine_signals(df, "reversion", b["reversion"])
        out[MODES[2]][name] = hyb
        out[MODES[3]][name] = hyb
    return out


def run_modes(bars: dict[str, pd.DataFrame], sig: dict[str, dict[str, pd.DataFrame]]) -> dict[str, engine.BacktestResult]:
    res = {}
    for mode in MODES:
        risk = RiskConfig.prop() if mode == MODES[3] else RiskConfig.plain()
        res[mode] = engine.run(bars, {n: sig[mode][n].loc[bars[n].index] for n in bars}, risk)
    return res


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--optimize", action="store_true", help="re-tune parameters on the in-sample part")
    ap.add_argument("--paths", type=int, default=4000, help="Monte Carlo paths")
    args = ap.parse_args()
    pd.set_option("display.width", 250)
    OUT.mkdir(exist_ok=True)

    print("Baixando / lendo dados...", flush=True)
    data = load_all()
    parts = {n: split(df) for n, df in data.items()}
    ins = {n: p[0] for n, p in parts.items()}
    oos = {n: p[1] for n, p in parts.items()}
    first = next(iter(data))
    print(f"Dentro da amostra: {ins[first].index[0]:%Y-%m-%d} a {ins[first].index[-1]:%Y-%m-%d} | "
          f"Fora da amostra: {oos[first].index[0]:%Y-%m-%d} a {oos[first].index[-1]:%Y-%m-%d}")

    if args.optimize or not PARAMS.exists():
        print("Ajustando parametros so com os dados de dentro da amostra...", flush=True)
        best = optimize(data)
    else:
        best = json.loads(PARAMS.read_text())
    sig = build_signals(data, best)

    rows, curves = [], {}
    for label, bars in (("DENTRO", ins), ("FORA", oos)):
        for market in [*data, "CARTEIRA"]:
            sub = bars if market == "CARTEIRA" else {market: bars[market]}
            for mode, res in run_modes(sub, sig).items():
                rows.append({"amostra": label, "mercado": market, "simulacao": mode, **metrics.summarize(res)})
                if market == "CARTEIRA":
                    curves[(label, mode)] = res
    report = pd.DataFrame(rows)
    report.to_csv(OUT / "comparativo.csv", index=False)
    for label in ("DENTRO", "FORA"):
        print(f"\n=== {label} DA AMOSTRA ===")
        print(report[report["amostra"] == label].drop(columns="amostra").to_string(index=False))

    # Monte Carlo on the out-of-sample hybrid trades of the 3-market account (before the locks)
    res3 = curves[("FORA", MODES[2])]
    days = mc.trades_by_day(res3.trades, res3.equity.index[0], res3.equity.index[-1])
    prop = RiskConfig.prop()
    no_lock = dataclasses.replace(prop, max_drawdown_lock=None)
    stats = [
        mc.bootstrap(days, prop, "robo, travas completas", paths=args.paths),
        mc.bootstrap(days, no_lock, "robo, sem a trava de -6%", paths=args.paths),
        mc.bootstrap(mc.coin_flip_days(cost_r=0.0), no_lock, "cara ou coroa sem custo", paths=args.paths),
        mc.bootstrap(mc.coin_flip_days(cost_r=0.05), no_lock, "cara ou coroa com custo", paths=args.paths),
    ]
    mc_table = pd.DataFrame([s.row() for s in stats])
    mc_table.to_csv(OUT / "monte_carlo.csv", index=False)
    print(f"\n=== DESAFIO SIMULADO (Monte Carlo, {args.paths} caminhos, trades de FORA da amostra) ===")
    print(mc_table.to_string(index=False))
    print("\nDesafio iniciado em cada dia real de FORA da amostra (ordem real):", mc.rolling(days, prop))

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5), sharey=True)
    for ax, label in zip(axes, ("DENTRO", "FORA")):
        for mode in MODES:
            eq = curves[(label, mode)].equity.resample("1D").last().dropna()
            ax.plot(eq.index, eq / SETTINGS.rules.account_size * 100 - 100, label=mode)
        for y, c in ((8, "green"), (-10, "red")):
            ax.axhline(y, color=c, ls="--", lw=0.8)
        ax.set_title(f"Carteira (3 mercados), {label.lower()} da amostra")
        ax.set_ylabel("resultado da conta (%)")
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "equity_curve.png", dpi=130)
    print(f"\nGrafico: {OUT / 'equity_curve.png'}")


if __name__ == "__main__":
    main()
