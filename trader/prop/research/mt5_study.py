"""Strategy study on REAL broker data exported from MetaTrader 5 (needs only numpy and pandas).

    python -m prop.research.mt5_study C:\\Users\\kenui\\Projetos\\mt5data

Input: <SYMBOL>_<D1|H1>.csv.gz (time, open, high, low, close, tick_volume, spread, real_volume)
and symbols.json, as written by the collector script. Every rule is chosen on the data before
2019-01-01 ("antes") and judged on 2019-2026 ("depois"). Families:

  tendencia        daily trend rules (same nine as on the Binance data), long/short and long only
  pares            Kalman-filter cointegration pairs with z-score entries (V8 "Nucleo A")
  reversao         fade an extreme hourly move
  hora             best and worst hours of the week
  queda_indice     buy a short dip of a stock index that is above its 200-day average

Costs: half the recorded spread plus commission per side, and the broker's swap per night.
The last block pushes the candidates through the prop-firm journey (Phase 1, Phase 2, 12 months).
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from prop.research import trend as T

SPLIT = pd.Timestamp("2019-01-01")
HOUR_FIT = pd.Timestamp("2016-01-01")
COMMISSION = 0.00003                       # per side, fraction of notional (about US$ 3 per lot)
FX = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD", "EURJPY", "GBPJPY", "EURGBP"]
METALS = ["XAUUSD", "XAGUSD"]
INDEX = ["US500", "US30", "US2000", "DE40", "CHINA50", "IT40", "NETH25", "SWI20"]      # history from 2012 or earlier
PAIRS = [("EURUSD", "GBPUSD"), ("AUDUSD", "NZDUSD"), ("EURJPY", "GBPJPY"), ("EURUSD", "USDCHF"), ("AUDUSD", "USDCAD"),
         ("GBPUSD", "EURGBP"), ("XAUUSD", "XAGUSD"), ("US500", "US30"), ("US500", "US2000"), ("DE40", "NETH25"),
         ("DE40", "SWI20")]
DEFAULT_SWAP = {"fx": 0.00003, "metal": 0.00012, "index": 0.00016}   # per night, when the file has no usable swap


class Market:
    def __init__(self, folder: Path) -> None:
        self.folder = Path(folder)
        f = self.folder / "symbols.json"
        self.spec = json.loads(f.read_text()) if f.exists() else {}
        self.cache: dict[tuple[str, str], pd.DataFrame] = {}

    def has(self, sym: str, tf: str = "D1") -> bool:
        return (self.folder / f"{sym}_{tf}.csv.gz").exists()

    def bars(self, sym: str, tf: str) -> pd.DataFrame:
        if (sym, tf) not in self.cache:
            df = pd.read_csv(self.folder / f"{sym}_{tf}.csv.gz")
            df.index = pd.to_datetime(df.pop("time"), unit="s")
            df = df[~df.index.duplicated()].sort_index()
            self.cache[(sym, tf)] = df[df["close"] > 0]
        return self.cache[(sym, tf)]

    def kind(self, sym: str) -> str:
        return "fx" if sym in FX else ("metal" if sym.startswith("X") else "index")

    def cost(self, sym: str) -> tuple[float, float]:
        """(cost per side, swap per night), fractions of the notional, both positive = paid."""
        d = self.bars(sym, "D1").iloc[-750:]
        s = self.spec.get(sym, {})
        point = float(s.get("point") or 0.0)
        px = float(d["close"].iloc[-1])
        spread = float(d["spread"].median()) * point / px if point else 0.0
        floor = {"fx": 0.00004, "metal": 0.00010, "index": 0.00010}[self.kind(sym)]
        side = max(spread, floor) / 2 + COMMISSION
        swap = DEFAULT_SWAP[self.kind(sym)]
        if point and int(s.get("swap_mode", -1)) == 1:
            paid = [-float(s.get(k, 0.0)) * point / px for k in ("swap_long", "swap_short")]
            swap = max(swap, float(np.mean(paid)))                 # average of both sides, never below the default
        return side, swap


def sharpe(x: pd.Series) -> float:
    x = x.dropna()
    return float(x.mean() / x.std() * np.sqrt(252)) if len(x) > 60 and x.std() > 0 else float("nan")


def before_after(x: pd.Series) -> tuple[float, float]:
    return round(sharpe(x[x.index < SPLIT]), 2), round(sharpe(x[x.index >= SPLIT]), 2)


def by_day(x: pd.Series) -> pd.Series:
    """Sum of hourly results per trading day (days without bars are left out)."""
    return x.groupby(x.index.normalize()).sum()


def portfolio(cols: dict[str, pd.Series]) -> pd.Series:
    """Equal weight of whatever is trading that day."""
    return pd.DataFrame(cols).mean(axis=1).dropna() if cols else pd.Series(dtype=float)


# ---- families ----------------------------------------------------------------------------------
def trend(m: Market, syms: list[str], rule: str, long_only: bool) -> pd.Series:
    out = {}
    for s in syms:
        if m.has(s):
            d = m.bars(s, "D1")
            out[s] = T.net_returns(d, T.RULES[rule](d), m.cost(s), long_only)
    return portfolio(out)


def kalman_z(y: np.ndarray, x: np.ndarray, delta: float) -> tuple[np.ndarray, np.ndarray]:
    """Dynamic regression y = a + b x. Returns the one-step forecast error (the caller turns it
    into a z-score with its own past spread) and the hedge ratio known BEFORE each bar."""
    n = len(y)
    z, beta = np.zeros(n), np.zeros(n)
    th = np.array([0.0, 1.0])
    P = np.eye(2)
    W = np.eye(2) * delta / (1 - delta)
    ve = 1e-3
    for t in range(n):
        H = np.array([1.0, x[t]])
        P = P + W
        e = y[t] - H @ th
        q = H @ P @ H + ve
        z[t], beta[t] = e, th[1]
        K = P @ H / q
        th = th + K * e
        P = P - np.outer(K, H) @ P
    return z, beta


def pair(m: Market, a: str, b: str, tf: str, entry: float, delta: float) -> pd.Series:
    """Long the spread when z < -entry, short when z > entry; flat again at |z| < 0.5 or |z| > 4."""
    pa, pb = m.bars(a, tf), m.bars(b, tf)
    idx = pa.index.intersection(pb.index)
    la, lb = np.log(pa.loc[idx, "close"].to_numpy()), np.log(pb.loc[idx, "close"].to_numpy())
    e, beta = kalman_z(la, lb, delta)
    per_day = {"D1": 1, "H1": 24}[tf]
    es = pd.Series(e)
    z = (es / es.ewm(span=60 * per_day, min_periods=20 * per_day).std().shift(1)).fillna(0.0).to_numpy()
    pos, state = np.zeros(len(idx)), 0
    for t in range(len(idx)):
        if state == 0:
            state = -1 if z[t] > entry else (1 if z[t] < -entry else 0)
            if abs(z[t]) > 4:
                state = 0
        elif abs(z[t]) < 0.5 or abs(z[t]) > 4:
            state = 0
        pos[t] = state
    ra, rb = np.diff(la, append=la[-1]), np.diff(lb, append=lb[-1])        # return of the NEXT bar
    spread_ret = pd.Series(ra - beta * rb, index=idx)
    vol = spread_ret.ewm(span=30 * per_day, min_periods=10 * per_day).std().shift(1) * np.sqrt(per_day)
    w = pd.Series(pos, index=idx) * (0.01 / vol).clip(upper=5.0)
    w = w.fillna(0.0)
    (ca, sa), (cb, sb) = m.cost(a), m.cost(b)
    hedge = pd.Series(np.abs(beta), index=idx)
    turn = (w - w.shift(1).fillna(0.0)).abs()
    net = w * spread_ret - turn * (ca + hedge * cb) - w.abs() * (sa + hedge * sb) / per_day
    return by_day(net) if tf == "H1" else net


def pairs(m: Market, tf: str, entry: float, delta: float, which: str = "all") -> pd.Series:
    out = {}
    for a, b in PAIRS:
        fx = m.kind(a) != "index"
        if (which == "fx" and not fx) or (which == "index" and fx) or not (m.has(a, tf) and m.has(b, tf)):
            continue
        out[f"{a}/{b}"] = pair(m, a, b, tf, entry, delta)
    return portfolio(out)


def reversal(m: Market, syms: list[str], zmin: float, hold: int) -> pd.Series:
    out = {}
    for s in syms:
        if not m.has(s, "H1"):
            continue
        h = m.bars(s, "H1")
        lr = np.log(h["close"]).diff()
        sd = lr.ewm(span=24 * 30, min_periods=24 * 10).std().shift(1)
        sig = pd.Series(np.where(lr > zmin * sd, -1.0, np.where(lr < -zmin * sd, 1.0, 0.0)), index=h.index)
        fwd = h["close"].shift(-hold) / h["close"] - 1.0
        w = sig * (0.01 / (sd * np.sqrt(24))).clip(upper=5.0)
        out[s] = ((w * fwd - w.abs() * 2 * m.cost(s)[0]) / hold).pipe(by_day)
    return portfolio(out)


def hour_of_week(m: Market, syms: list[str], top: int) -> pd.Series:
    out = {}
    for s in syms:
        if not m.has(s, "H1"):
            continue
        h = m.bars(s, "H1")
        r = h["close"] / h["open"] - 1.0
        key = h.index.dayofweek * 24 + h.index.hour
        early = h.index < HOUR_FIT                 # hours picked before 2016, so 2016 to 2018 is a fair "before"
        mean = r[early].groupby(key[early]).mean()
        side = pd.Series(0.0, index=h.index)
        side[np.isin(key, mean.nlargest(top).index)] = 1.0
        side[np.isin(key, mean.nsmallest(top).index)] = -1.0
        hv = np.log(h["close"]).diff().ewm(span=24 * 30, min_periods=24 * 10).std().shift(1)
        w = side * (0.01 / (hv * np.sqrt(24))).clip(upper=5.0)
        out[s] = by_day(w * r - w.abs() * 2 * m.cost(s)[0])[lambda x: x.index >= HOUR_FIT]
    return portfolio(out)


def index_dip(m: Market, syms: list[str], rsi_max: float) -> pd.Series:
    """Long at the next open when RSI(2) < rsi_max and the close is above its 200-day average;
    out at the open after the close rises above its 5-day average."""
    out = {}
    for s in syms:
        if not m.has(s):
            continue
        d = m.bars(s, "D1")
        c = d["close"]
        ch = c.diff()
        up, dn = ch.clip(lower=0).ewm(alpha=0.5, adjust=False).mean(), (-ch.clip(upper=0)).ewm(alpha=0.5, adjust=False).mean()
        rsi = 100 - 100 / (1 + up / (dn + 1e-12))
        buy = (rsi < rsi_max) & (c > c.rolling(200).mean())
        sell = c > c.rolling(5).mean()
        pos, state = np.zeros(len(d)), 0
        for i in range(len(d)):
            state = 1 if (state == 0 and buy.iloc[i]) else (0 if (state == 1 and sell.iloc[i]) else state)
            pos[i] = state
        out[s] = T.net_returns(d, pd.Series(pos, index=d.index), m.cost(s))
    return portfolio(out)


def study(m: Market) -> dict[str, pd.Series]:
    """Every variant on the table: name -> daily net returns (1% daily volatility per position)."""
    v: dict[str, pd.Series] = {}
    groups = {"fx": FX, "metais": METALS, "indices": INDEX}
    for g, syms in groups.items():
        for rule in T.RULES:
            v[f"tendencia|{g}|{rule}|compra_e_venda"] = trend(m, syms, rule, False)
            v[f"tendencia|{g}|{rule}|so_compra"] = trend(m, syms, rule, True)
    for tf, delta in (("D1", 1e-4), ("H1", 1e-6)):
        for entry in (1.5, 2.0):
            for which in ("fx", "index"):
                v[f"pares|{which}|{tf}|z{entry}"] = pairs(m, tf, entry, delta, which)
    for zmin in (3.0, 5.0):
        for hold in (4, 24):
            for g in ("fx", "metais", "indices"):
                v[f"reversao|{g}|z{zmin:.0f}|{hold}h"] = reversal(m, groups[g], zmin, hold)
    for top in (3, 10):
        for g in ("fx", "metais", "indices"):
            v[f"hora|{g}|top{top}"] = hour_of_week(m, groups[g], top)
    for r in (5.0, 10.0, 25.0):
        v[f"queda_indice|indices|rsi{r:.0f}"] = index_dip(m, INDEX, r)
    return {k: s for k, s in v.items() if len(s) > 500}


def main() -> None:
    warnings.filterwarnings("ignore")
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 500)
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "data/mt5")
    m = Market(folder)
    print("custos por lado e swap por noite (% do valor da posicao):")
    print("  " + "  ".join(f"{s} {100 * m.cost(s)[0]:.4f}/{100 * m.cost(s)[1]:.4f}" for s in FX + METALS + INDEX if m.has(s)))
    v = study(m)
    rows = []
    for name, s in v.items():
        fam, grp = name.split("|")[:2]
        a, b = before_after(s)
        rows.append({"familia": fam, "grupo": grp, "variante": name, "sharpe_antes_2019": a, "sharpe_2019_2026": b,
                     "inicio": s.index[0].date()})
    tab = pd.DataFrame(rows)
    print(f"\n{len(tab)} variantes (antes = escolha, depois = julgamento):")
    print(tab.to_string(index=False))
    print(f"\ncorrelacao entre o Sharpe de antes e o de depois: {tab['sharpe_antes_2019'].corr(tab['sharpe_2019_2026']):.2f}; "
          f"variantes positivas antes: {(tab['sharpe_antes_2019'] > 0).sum()}, dessas, positivas depois: "
          f"{((tab['sharpe_antes_2019'] > 0) & (tab['sharpe_2019_2026'] > 0)).sum()}")

    print("\nmelhor variante de cada familia e grupo, escolhida SO pelo periodo de antes:")
    best = tab.dropna(subset=["sharpe_antes_2019"]).sort_values("sharpe_antes_2019", ascending=False).groupby(["familia", "grupo"]).head(1)
    print(best.to_string(index=False))
    chosen = {r["variante"]: v[r["variante"]] for _, r in best.iterrows() if r["sharpe_antes_2019"] >= 0.5}
    cand: dict[str, pd.Series] = dict(chosen)
    if len(chosen) > 1:
        scaled = {k: s / s[s.index < SPLIT].std() for k, s in chosen.items()}
        cand["CARTEIRA das escolhidas (Sharpe antes >= 0,5)"] = pd.DataFrame(scaled).mean(axis=1).dropna()
    print("\ncandidatas (Sharpe antes >= 0,5), ano a ano no periodo de julgamento:")
    for k, s in cand.items():
        a, b = before_after(s)
        o = s[s.index >= SPLIT]
        print(f"  {k}: antes {a}  depois {b}  | " + " ".join(f"{y}:{sharpe(g):.1f}" for y, g in o.groupby(o.index.year)))
    pd.DataFrame(cand).to_csv(folder / "study_returns.csv")
    tab.to_csv(folder / "study_table.csv", index=False)
    pd.DataFrame(v).to_csv(folder / "study_all_returns.csv.gz")
    try:                                                  # how much of the best result is luck of many tries
        from prop.validation.cpcv_dsr_and_mc import deflated_sharpe, pbo_cscv
        mat = pd.DataFrame(v).loc["2012-06-01":].fillna(0.0)
        print(f"\nPBO (todas as variantes, desde 2012): {pbo_cscv(mat.to_numpy())}")
        var_trials = float(np.nanvar([sharpe(s[s.index >= SPLIT]) / np.sqrt(252) for s in v.values()]))
        for k, s in cand.items():
            print(f"  DSR no julgamento, {k}: {deflated_sharpe(s[s.index >= SPLIT].dropna().to_numpy(), len(v), var_trials):.2f}")
    except Exception as err:                              # scipy missing on the PC is not fatal
        print(f"\nPBO/DSR nao calculados: {err}")

    if cand and "--no-journey" not in sys.argv:
        from prop.research.approval_map import as_days, journey
        print("\njornada na mesa (Fase 1 +8%, Fase 2 +5%, 12 meses financiada; politica desenhada no periodo de antes):")
        out = []
        for k, s in cand.items():
            ins, oos = s[s.index < SPLIT].dropna(), s[s.index >= SPLIT].dropna()
            unit = float(ins.std())
            out.append({"sharpe_depois": round(sharpe(oos), 2), **journey(k[:60], as_days(oos.to_numpy(), unit), ins.to_numpy() / unit, 4000)})
            print(out[-1], flush=True)
        pd.DataFrame(out).to_csv(folder / "study_journey.csv", index=False)


if __name__ == "__main__":
    main()
