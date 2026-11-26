"""Adaptive ensemble on real MetaTrader 5 history: many weak rules, no hand-picking.

Every family from mt5_study plus four new ones (intraday momentum and overnight drift in US
indices, turn of the month in indices, short-term reversal in forex) becomes one "stream": the
plain average of ALL its parameter variants, so no parameter is ever chosen. An online allocator
then decides, day by day and using only the past, how much each stream deserves: weight grows
with the stream's own running t-statistic (exponential forgetting) and is zero while the
evidence is weak or negative. Nothing is fitted on the judged period, so the whole history after
the warm-up is out of sample, and the robot keeps adapting without being re-tuned.

    python -m prop.research.ensemble_study C:\\Users\\kenui\\Projetos\\mt5data [--no-journey]
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from prop.research import mt5_study as S
from prop.research import trend as T

US_INDEX = ["US500", "US30", "US2000", "USTEC", "US100", "NAS100"]
CASH_FIRST, LAST_BAR = 16, 22          # server time = New York + 7 h: cash opens 16:30, closes 23:00
HALF_LIFE, MIN_DAYS, T_MIN = 750, 500, 0.5


# ---- new families ------------------------------------------------------------------------------
def _session(h: pd.DataFrame) -> pd.DataFrame:
    """One row per day: previous session close, end of the first cash bar, 22:00 price, last-hour open/close."""
    day, hour = h.index.normalize(), h.index.hour
    pick = lambda col, hr: h[col][hour == hr].groupby(day[hour == hr]).last()      # noqa: E731
    out = pd.DataFrame({"first": pick("close", CASH_FIRST), "pre": pick("close", LAST_BAR - 1),
                        "last_open": pick("open", LAST_BAR), "close": pick("close", LAST_BAR),
                        "open16": pick("open", CASH_FIRST)}).dropna()
    out["prev"] = out["close"].shift(1)
    lr = np.log(out["close"]).diff()
    out["w"] = (0.01 / lr.ewm(span=30, min_periods=20).std().shift(1)).clip(upper=5.0)
    return out.dropna()


def intraday_momentum(m: S.Market, syms: list[str], mode: str) -> pd.Series:
    """Direction of the day so far, traded into the close (Gao et al. 2018; Zarattini et al. 2024).
    first: sign of previous close -> end of first cash bar, traded in the last hour.
    sofar: sign of previous close -> 22:00, traded in the last hour.
    both:  last hour only when the two agree.   hold: enter after the first cash bar, out at the close."""
    out = {}
    for s in syms:
        if not m.has(s, "H1"):
            continue
        d = _session(m.bars(s, "H1"))
        first, sofar = np.sign(d["first"] / d["prev"] - 1), np.sign(d["pre"] / d["prev"] - 1)
        if mode == "hold":
            sig, ret = first, d["close"] / d["first"] - 1
        else:
            sig = {"first": first, "sofar": sofar, "both": first.where(first == sofar, 0.0)}[mode]
            ret = d["close"] / d["last_open"] - 1
        out[s] = d["w"] * (sig * ret - sig.abs() * 2 * m.cost(s)[0])
    return S.portfolio(out)


def overnight(m: S.Market, syms: list[str], trend_filter: bool) -> pd.Series:
    """Long from the cash close to just before the next cash open, paying the swap for every night."""
    out = {}
    for s in syms:
        if not m.has(s, "H1"):
            continue
        d = _session(m.bars(s, "H1"))
        nights = pd.Series(d.index, index=d.index).diff().dt.days.fillna(1.0)
        ret = d["open16"] / d["prev"] - 1
        on = (d["prev"] > d["close"].rolling(200).mean().shift(1)).astype(float) if trend_filter else 1.0
        side, swap = m.cost(s)
        out[s] = d["w"].shift(1) * on * (ret - 2 * side - swap * nights)
    return S.portfolio({k: v.dropna() for k, v in out.items()})


def turn_of_month(m: S.Market, syms: list[str], before: int, after: int) -> pd.Series:
    """Long only on the last `before` and the first `after` trading days of each month."""
    out = {}
    for s in syms:
        if not m.has(s):
            continue
        d = m.bars(s, "D1")
        month = pd.Series(d.index.to_period("M"), index=d.index)
        window = (month.groupby(month).cumcount(ascending=False) < before) | (month.groupby(month).cumcount() < after)
        out[s] = T.net_returns(d, window.shift(-1).fillna(False).astype(float), m.cost(s), long_only=True)
    return S.portfolio(out)


def fx_reversal(m: S.Market, syms: list[str], low: float) -> pd.Series:
    """Daily RSI(2) fade in currencies: long below `low`, short above 100 - low, flat again at 50."""
    out = {}
    for s in syms:
        if not m.has(s):
            continue
        d = m.bars(s, "D1")
        ch = d["close"].diff()
        up, dn = ch.clip(lower=0).ewm(alpha=0.5, adjust=False).mean(), (-ch.clip(upper=0)).ewm(alpha=0.5, adjust=False).mean()
        rsi = (100 - 100 / (1 + up / (dn + 1e-12))).to_numpy()
        pos, state = np.zeros(len(d)), 0
        for i in range(len(d)):
            if state == 0:
                state = 1 if rsi[i] < low else (-1 if rsi[i] > 100 - low else 0)
            elif (state == 1 and rsi[i] > 50) or (state == -1 and rsi[i] < 50):
                state = 0
            pos[i] = state
        out[s] = T.net_returns(d, pd.Series(pos, index=d.index), m.cost(s))
    return S.portfolio(out)


def last_half_hour(m: S.Market, syms: list[str]) -> pd.Series:
    """Baltussen et al. (2021) on 15-minute bars: sign of previous close -> 22:30, held 22:30-23:00."""
    out = {}
    for s in syms:
        if not m.has(s, "M15"):
            continue
        h = m.bars(s, "M15")
        day, hm = h.index.normalize(), h.index.hour * 100 + h.index.minute
        pick = lambda col, t: h[col][hm == t].groupby(day[hm == t]).last()          # noqa: E731
        d = pd.DataFrame({"entry": pick("open", 2230), "close": pick("close", 2245)}).dropna()
        sig = np.sign(d["entry"] / d["close"].shift(1) - 1)
        w = (0.01 / np.log(d["close"]).diff().ewm(span=30, min_periods=20).std().shift(1)).clip(upper=5.0)
        out[s] = (w * (sig * (d["close"] / d["entry"] - 1) - sig.abs() * 2 * m.cost(s)[0])).dropna()
    return S.portfolio(out)


def month_end_reversal(m: S.Market, syms: list[str], short_too: bool) -> pd.Series:
    """Graziani (2024): if the index fell from the fourth Friday to the month end, be long the next
    month; if it rose, stay flat (or short)."""
    out = {}
    for s in syms:
        if not m.has(s):
            continue
        d = m.bars(s, "D1")
        c, month = d["close"], d.index.to_period("M")
        sig = pd.Series(0.0, index=d.index)
        ends = c.groupby(month).tail(1)
        for end_day, end_px in ends.items():
            mdays = c[month == end_day.to_period("M")]
            fridays = mdays[mdays.index.dayofweek == 4]
            if len(fridays) < 4 or fridays.index[3] >= end_day:
                continue
            nxt = month == (end_day.to_period("M") + 1)
            sig[nxt] = 1.0 if end_px < fridays.iloc[3] else (-1.0 if short_too else 0.0)
            sig[end_day] = sig[nxt].iloc[0] if nxt.any() else 0.0        # decided at the month-end close
        sig = sig.shift(1).fillna(0.0).where(~pd.Series(d.index.isin(ends.index), index=d.index), sig)
        out[s] = T.net_returns(d, sig, m.cost(s))
    return S.portfolio(out)


def all_variants(m: S.Market) -> dict[str, pd.Series]:
    v = S.study(m)
    us = [s for s in US_INDEX if m.has(s, "H1")]
    for mode in ("first", "sofar", "both", "hold"):
        v[f"momento_intradia|indices_eua|{mode}"] = intraday_momentum(m, us, mode)
    for filt in (False, True):
        v[f"noite|indices_eua|{'com_filtro' if filt else 'sempre'}"] = overnight(m, us, filt)
    for before, after in ((1, 3), (2, 3), (1, 1), (3, 5)):
        v[f"virada_do_mes|indices|{before}_{after}"] = turn_of_month(m, S.INDEX, before, after)
    v["ultima_meia_hora|indices_eua|m15"] = last_half_hour(m, us)
    for short_too in (False, True):
        v[f"reversao_fim_de_mes|indices_eua|{'compra_e_venda' if short_too else 'so_compra'}"] = month_end_reversal(m, us, short_too)
    for low in (5.0, 10.0, 20.0):
        v[f"reversao_diaria|fx|rsi{low:.0f}"] = fx_reversal(m, S.FX, low)
    return {k: s for k, s in v.items() if len(s) > 400}


def streams(v: dict[str, pd.Series]) -> pd.DataFrame:
    """One column per family and group: the plain average of every variant (no parameter is picked)."""
    groups: dict[str, list[pd.Series]] = {}
    for name, s in v.items():
        p = name.split("|")
        key = "|".join(p[:2] + ([p[3]] if p[0] == "tendencia" else []))
        groups.setdefault(key, []).append(s[~s.index.duplicated()])
    return pd.DataFrame({k: pd.concat(g, axis=1).mean(axis=1) for k, g in groups.items()}).sort_index()


# ---- the allocator -----------------------------------------------------------------------------
def allocate(x: pd.DataFrame, half_life: int = HALF_LIFE, min_days: int = MIN_DAYS, t_min: float = T_MIN,
             target: float = 0.01) -> tuple[pd.Series, pd.DataFrame]:
    """Daily return of the ensemble (about `target` daily volatility) and the weights used.
    Everything that sets today's weight was known yesterday."""
    vol = x.ewm(span=60, min_periods=40).std().shift(1).replace(0.0, np.nan)
    z = x / vol                                                   # every stream at the same risk
    mean = z.ewm(halflife=half_life, min_periods=min_days).mean().shift(1)
    sd = z.ewm(halflife=half_life, min_periods=min_days).std().shift(1)
    n_eff = z.notna().cumsum().clip(upper=2.89 * half_life)
    t = mean / sd * np.sqrt(n_eff)
    w = (t - t_min).clip(lower=0.0).where(z.notna(), 0.0)
    w = w.div(w.sum(axis=1).replace(0.0, np.nan), axis=0).fillna(0.0)
    raw = (w * z.fillna(0.0)).sum(axis=1)
    pvol = raw.ewm(span=60, min_periods=40).std().shift(1)
    scale = (target / pvol).replace([np.inf, -np.inf], np.nan).clip(upper=3.0 * target / pvol.median()).fillna(0.0)
    out = (raw * scale)[w.sum(axis=1) > 0]
    return out, w


def by_year(x: pd.Series) -> str:
    return " ".join(f"{y}:{S.sharpe(g):.1f}" for y, g in x.groupby(x.index.year) if len(g) > 60)


def main() -> None:
    warnings.filterwarnings("ignore")
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 500)
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "data/mt5")
    m = S.Market(folder)
    v = all_variants(m)
    x = streams(v)
    print(f"{len(v)} variantes em {x.shape[1]} fluxos (cada fluxo = media de todas as suas variantes, sem escolher parametro)")
    new = [k for k in v if k.split("|")[0] in ("momento_intradia", "noite", "virada_do_mes", "reversao_diaria", "ultima_meia_hora", "reversao_fim_de_mes")]
    print("\nfamilias novas, variante por variante (Sharpe antes de 2019 / 2019-2026):")
    for k in new:
        a, b = S.before_after(v[k])
        print(f"  {k:45s} {a:6.2f} {b:6.2f}  desde {v[k].index[0].date()}")

    ens, w = allocate(x)
    after = ens.index >= S.SPLIT
    print("\nfluxos (Sharpe antes / depois de 2019, peso medio que o alocador deu depois de 2019, em %):")
    rows = []
    for k in x.columns:
        a, b = S.before_after(x[k].dropna())
        rows.append({"fluxo": k, "antes": a, "depois": b, "peso_%": round(100 * float(w[k][w.index >= S.SPLIT].mean()), 1),
                     "inicio": x[k].dropna().index[0].date()})
    print(pd.DataFrame(rows).sort_values("peso_%", ascending=False).to_string(index=False))

    print(f"\nCONJUNTO ADAPTATIVO (meia-vida {HALF_LIFE} dias, t minimo {T_MIN}): comeca em {ens.index[0].date()}")
    print(f"  Sharpe total {S.sharpe(ens):.2f} | antes de 2019 {S.sharpe(ens[~after]):.2f} | 2019-2026 {S.sharpe(ens[after]):.2f}")
    print(f"  ano a ano: {by_year(ens)}")
    eq = x.div(x.ewm(span=60, min_periods=40).std().shift(1)).mean(axis=1).dropna()
    print(f"  comparacao, todos os fluxos com peso igual: total {S.sharpe(eq):.2f} | 2019-2026 {S.sharpe(eq[eq.index >= S.SPLIT]):.2f}")
    print("\nsensibilidade do alocador (nenhuma destas foi escolhida; a do meio e a padrao):")
    sens = []
    for hl in (375, 750, 1500):
        for tm in (0.0, 0.5, 1.0):
            e, _ = allocate(x, hl, MIN_DAYS, tm)
            sens.append(S.sharpe(e[e.index >= S.SPLIT]))
            print(f"  meia-vida {hl:4d}, t minimo {tm:.1f}: total {S.sharpe(e):.2f}  2019-2026 {sens[-1]:.2f}")
    print(f"  mediana 2019-2026: {np.nanmedian(sens):.2f}, pior {np.nanmin(sens):.2f}, melhor {np.nanmax(sens):.2f}")
    top = w[w.index >= S.SPLIT].mean().sort_values(ascending=False).head(6).index
    print("\ncorrelacao entre os fluxos mais usados (2019-2026):")
    print(x.loc[x.index >= S.SPLIT, top].corr().round(2).to_string())
    ens.to_csv(folder / "ensemble_returns.csv")
    w.to_csv(folder / "ensemble_weights.csv.gz")
    x.to_csv(folder / "ensemble_streams.csv.gz")
    try:
        from prop.validation.cpcv_dsr_and_mc import deflated_sharpe
        o = ens[after].to_numpy()
        print(f"\nDSR do conjunto em 2019-2026 contando {len(v)} variantes tentadas: "
              f"{deflated_sharpe(o, len(v), float(np.nanvar([S.sharpe(s[s.index >= S.SPLIT]) / np.sqrt(252) for s in v.values()]))):.2f}")
    except Exception as err:
        print(f"\nDSR nao calculado: {err}")

    if "--no-journey" not in sys.argv and after.sum() > 500 and (~after).sum() > 250:
        from prop.research.approval_map import as_days, journey
        ins, oos = ens[~after], ens[after]
        unit = float(ins.std())
        print("\njornada na mesa do conjunto (Fase 1 +8%, Fase 2 +5%, 12 meses financiada; politica desenhada com dados antes de 2019):")
        res = {"sharpe_2019_2026": round(S.sharpe(oos), 2), **journey("conjunto adaptativo", as_days(oos.to_numpy(), unit), ins.to_numpy() / unit, 4000)}
        print(res, flush=True)
        pd.DataFrame([res]).to_csv(folder / "ensemble_journey.csv", index=False)


if __name__ == "__main__":
    main()
