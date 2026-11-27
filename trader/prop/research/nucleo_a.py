"""Step 1 of the four-layer plan: plain "Nucleo A" baseline, out of sample, on real MetaTrader 5 data.

    python -m prop.research.nucleo_a C:\\Users\\kenui\\Projetos\\mt5data

Nucleo A = cointegrated baskets traded on the forecast error of an online Kalman regression,
with an Ornstein-Uhlenbeck half-life requirement. No regime filter, no meta-model, no guards.

Walk-forward: rolling windows of 60 months, the first 42 (70%) calibrate and the last 18 (30%)
are traded blind; the window slides 18 months, so every out-of-sample month is used once.
Inside the calibration part, and only there, each basket must (a) pass an Engle-Granger
cointegration test, (b) have a Kalman-spread half-life of at most MAX_HALF_LIFE hours, (c) have
at least 30 trades and a positive net result; its Kalman speed and entry threshold are the best
of a 3 x 3 grid on calibration net Sharpe.

Timing: a signal uses bars closed up to t and is filled at the OPEN of bar t+1.
Costs per side and per leg: half of the spread recorded on the fill bar (never below the symbol's
running median, because the H1 file keeps one spread per bar, not every tick), slippage of a
quarter of that spread, commission, and the broker's swap per night with the triple night
(Wednesday for forex and metals, Friday for indices). Swap credits are not counted.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from prop.research import mt5_study as S

BASKETS = [("EURUSD", "GBPUSD"), ("AUDUSD", "NZDUSD"), ("EURJPY", "GBPJPY"), ("EURUSD", "USDCHF"), ("AUDUSD", "USDCAD"),
           ("USDJPY", "EURJPY"), ("NZDUSD", "USDCAD"), ("GBPUSD", "GBPJPY"), ("XAUUSD", "XAGUSD"), ("XAUUSD", "AUDUSD"),
           ("US500", "US30"), ("US500", "US2000"), ("US30", "US2000"), ("DE40", "NETH25"), ("DE40", "SWI20"),
           ("US500", "DE40"), ("AUDUSD", "NZDUSD", "USDCAD"), ("EURUSD", "GBPUSD", "USDCHF"),
           ("US500", "US30", "US2000"), ("DE40", "NETH25", "SWI20")]
DELTAS = (1e-6, 1e-5, 1e-4)
ENTRIES = (1.5, 2.0, 2.5)
Z_EXIT, Z_STOP = 0.5, 4.0
MAX_HOLD = 120                 # hours
MAX_HALF_LIFE = 120            # hours
TRAIN_M, TEST_M = 42, 18
EG_CRIT = {2: -3.04, 3: -3.45}  # Engle-Granger 10% critical values (MacKinnon), constant, 2 and 3 series
SLIP = 0.25                    # slippage per side, as a share of the spread
MIN_TRADES = 30
COVER = 0.0                    # selective mode: expected move back to the mean must be COVER x the round-trip cost
STOP_GAP = None                # selective mode: stop this many z beyond the entry (None = fixed Z_STOP)


def kalman(y: np.ndarray, X: np.ndarray, delta: float) -> tuple[np.ndarray, np.ndarray]:
    """y = a + b.X with slowly moving a, b. Returns the forecast error of each bar and the b known BEFORE it."""
    n, k = X.shape
    e, beta = np.zeros(n), np.zeros((n, k))
    th = np.r_[0.0, np.ones(k) / k]
    P = np.eye(k + 1)
    W = np.eye(k + 1) * delta / (1 - delta)
    H = np.ones(k + 1)
    for t in range(n):
        H[1:] = X[t]
        P = P + W
        err = y[t] - H @ th
        PH = P @ H
        q = H @ PH + 1e-3
        e[t], beta[t] = err, th[1:]
        K = PH / q
        th = th + K * err
        P = P - np.outer(K, PH)
    return e, beta


def adf_t(x: np.ndarray) -> float:
    """t statistic of rho in  dx = c + rho x(-1) + phi dx(-1)."""
    dx = np.diff(x)
    A = np.column_stack([np.ones(len(dx) - 1), x[1:-1], dx[:-1]])
    b, res, *_ = np.linalg.lstsq(A, dx[1:], rcond=None)
    r = dx[1:] - A @ b
    cov = (r @ r / (len(r) - 3)) * np.linalg.inv(A.T @ A)
    return float(b[1] / np.sqrt(cov[1, 1]))


def half_life(x: np.ndarray) -> float:
    a, b = x[:-1] - x[:-1].mean(), x[1:] - x[1:].mean()
    phi = float(a @ b / (a @ a))
    return float(-np.log(2) / np.log(phi)) if 0 < phi < 1 else (0.5 if phi <= 0 else np.inf)


class Basket:
    """Aligned hourly data of one basket, with cost and swap per bar for every leg."""

    def __init__(self, m: S.Market, syms: tuple[str, ...]) -> None:
        self.syms = syms
        bars = [m.bars(s, "H1") for s in syms]
        idx = bars[0].index
        for b in bars[1:]:
            idx = idx.intersection(b.index)
        self.idx = idx
        self.close = np.column_stack([np.log(b.loc[idx, "close"].to_numpy()) for b in bars])
        op = np.column_stack([np.log(b.loc[idx, "open"].to_numpy()) for b in bars])
        self.ro = np.vstack([np.diff(op, axis=0), np.zeros((1, len(syms)))])    # open[k] to open[k+1]
        self.cost, self.swap = [], []
        for s, b in zip(syms, bars):
            spec = m.spec.get(s, {})
            point, px = float(spec.get("point") or 0.0), b.loc[idx, "open"]
            raw = b.loc[idx, "spread"].astype(float)
            med = raw.rolling(2000, min_periods=100).median().shift(1).bfill()
            floor = {"fx": 0.00004, "metal": 0.00010, "index": 0.00010}[m.kind(s)]
            spread = np.maximum(np.maximum(raw, med) * point / px, floor) if point else pd.Series(floor, index=idx)
            self.cost.append((spread * (0.5 + SLIP) + S.COMMISSION).to_numpy())
            default = S.DEFAULT_SWAP[m.kind(s)]
            if point and int(spec.get("swap_mode", -1)) == 1:             # points per night; credits ignored
                frac = float(point / px.iloc[-2000:].median())
                sw = (max(0.0, -float(spec.get("swap_long", 0.0)) * frac), max(0.0, -float(spec.get("swap_short", 0.0)) * frac))
            else:
                sw = (default, default)
            self.swap.append((sw, int(spec.get("swap_rollover3days", 3)) - 1))   # MetaTrader counts Sunday = 0
        day = idx.normalize()
        self.new_day = np.r_[False, day[1:] != day[:-1]]
        self.prev_wd = np.r_[0, idx.dayofweek[:-1]]
        self.cache: dict[float, tuple] = {}

    def spread(self, delta: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        if delta not in self.cache:
            e, beta = kalman(self.close[:, 0], self.close[:, 1:], delta)
            es = pd.Series(e)
            sd = es.ewm(span=480, min_periods=240).std().shift(1).to_numpy()
            sret = pd.Series(np.diff(self.close[:, 0], prepend=self.close[0, 0]) - (beta * np.diff(self.close[:, 1:], axis=0, prepend=self.close[:1, 1:])).sum(axis=1))
            dvol = (sret.ewm(span=720, min_periods=240).std().shift(1) * np.sqrt(24)).to_numpy()
            self.cache[delta] = (e, beta, sd, dvol)
        return self.cache[delta]

    def simulate(self, delta: float, entry: float) -> tuple[pd.DataFrame, pd.Series]:
        """All trades of the whole history (every decision is causal) and the net result per bar,
        sized to 1% of spread volatility per day."""
        e, beta, sd, dvol = self.spread(delta)
        n = len(e)
        z = np.where(sd > 0, e / sd, 0.0)
        z[~np.isfinite(z)] = 0.0
        bar = np.zeros(n)
        trades = []
        t = 0
        while t < n - 2:
            stop = Z_STOP if STOP_GAP is None else entry + STOP_GAP
            if not (entry < abs(z[t]) < stop) or not np.isfinite(dvol[t]) or dvol[t] <= 0:
                t += 1
                continue
            d = -np.sign(z[t])                                   # +1 buys the spread
            w = d * np.r_[1.0, -beta[t]]                         # leg weights, fixed for the whole trade
            if COVER and (abs(z[t]) - Z_EXIT) * sd[t] < COVER * 2 * sum(abs(w[i]) * self.cost[i][t] for i in range(len(w))):
                t += 1
                continue
            units = min(0.01 / dvol[t], 20.0 / np.abs(w).sum())
            k = t + 1                                            # filled at the open of bar t+1
            fee_in = sum(abs(w[i]) * self.cost[i][k] for i in range(len(w)))
            gross = swap = 0.0
            bar[k] -= units * fee_in
            reason = "tempo"
            while True:
                g = float(w @ self.ro[k])
                gross += g
                bar[k] += units * g
                if self.new_day[k]:
                    for i in range(len(w)):
                        (lo, sh), triple = self.swap[i]
                        c = abs(w[i]) * (lo if w[i] > 0 else sh) * (3 if self.prev_wd[k] == triple else 1)
                        swap += c
                        bar[k] -= units * c
                zc = z[k] * -d                                   # how far the spread still is from the mean
                if zc < Z_EXIT:
                    reason = "media"
                elif abs(z[k]) > stop:
                    reason = "stop"
                if reason != "tempo" or k - t >= MAX_HOLD or k >= n - 2:
                    break
                k += 1
            x = k + 1                                            # exit at the open of the next bar
            fee_out = sum(abs(w[i]) * self.cost[i][x] for i in range(len(w)))
            bar[x] -= units * fee_out
            risk = (stop - entry) * sd[t]
            trades.append((self.idx[t + 1], self.idx[x], "/".join(self.syms), d, gross / risk, (gross - fee_in - fee_out - swap) / risk,
                           units * (gross - fee_in - fee_out - swap), k - t, reason))
            t = x
        cols = ["entrada", "saida", "cesta", "lado", "r_bruto", "r", "ret", "horas", "motivo"]
        return pd.DataFrame(trades, columns=cols), pd.Series(bar, index=self.idx)


def folds(start: pd.Timestamp, end: pd.Timestamp) -> list[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp]]:
    out, a = [], start
    while a + pd.DateOffset(months=TRAIN_M) < end:
        b = a + pd.DateOffset(months=TRAIN_M)
        out.append((a, b, min(b + pd.DateOffset(months=TEST_M), end)))
        a = a + pd.DateOffset(months=TEST_M)
    return out


def calibrate(bk: Basket, sims: dict, a: pd.Timestamp, b: pd.Timestamp) -> tuple[tuple | None, dict]:
    """Best (delta, entry) of one basket on [a, b), or None when it fails the requirements."""
    win = (bk.idx >= a) & (bk.idx < b)
    info = {"cesta": "/".join(bk.syms), "treino_de": a.date(), "adf": np.nan, "meia_vida_h": np.nan, "motivo": ""}
    if win.sum() < 24 * 250 * 2:
        return None, {**info, "motivo": "historico curto"}
    c = bk.close[win][::24]                                       # one point per day for the test
    A = np.column_stack([np.ones(len(c)), c[:, 1:]])
    info["adf"] = round(adf_t(c[:, 0] - A @ np.linalg.lstsq(A, c[:, 0], rcond=None)[0]), 2)
    if info["adf"] > EG_CRIT[len(bk.syms)]:
        return None, {**info, "motivo": "sem cointegracao"}
    best, best_sh = None, 0.0
    for delta in DELTAS:
        hl = half_life(bk.spread(delta)[0][win])
        if hl > MAX_HALF_LIFE:
            continue
        for entry in ENTRIES:
            tr, bar = sims[(delta, entry)]
            n = int(((tr["entrada"] >= a) & (tr["entrada"] < b)).sum())
            d = S.by_day(bar[win])
            sh = float(d.mean() / d.std() * np.sqrt(252)) if d.std() > 0 else -9.0
            if n >= MIN_TRADES and sh > best_sh:
                best, best_sh, info["meia_vida_h"] = (delta, entry), sh, round(hl, 1)
    return best, {**info, "motivo": "" if best else "sem resultado liquido positivo no treino", "sharpe_treino": round(best_sh, 2)}


def run(m: S.Market) -> dict:
    baskets = [Basket(m, b) for b in BASKETS if all(m.has(s, "H1") for s in b)]
    sims = {}
    for bk in baskets:
        sims[bk.syms] = {(d, e): bk.simulate(d, e) for d in DELTAS for e in ENTRIES}
        print(f"  simulada {'/'.join(bk.syms)} ({len(bk.idx)} barras)", flush=True)
    start = min(bk.idx[0] for bk in baskets).normalize()
    end = max(bk.idx[-1] for bk in baskets)
    oos_days, is_days, trades, log = [], [], [], []
    for a, b, c in folds(start, end):
        chosen = []
        for bk in baskets:
            pick, info = calibrate(bk, sims[bk.syms], a, b)
            log.append({**info, "teste_de": b.date(), "teste_ate": c.date(), "escolhida": pick})
            if pick:
                chosen.append((bk, pick))
        days_is = pd.date_range(a, b, freq="B", inclusive="left")
        days_oos = pd.date_range(b, c, freq="B", inclusive="left")
        if not chosen:
            oos_days.append(pd.Series(0.0, index=days_oos))
            continue
        cols_is, cols_oos = {}, {}
        for bk, pick in chosen:
            tr, bar = sims[bk.syms][pick]
            d = S.by_day(bar)
            cols_is[bk.syms] = d[(d.index >= a) & (d.index < b)]
            cols_oos[bk.syms] = d[(d.index >= b) & (d.index < c)]
            trades.append(tr[(tr["entrada"] >= b) & (tr["entrada"] < c)])
        ins = pd.DataFrame(cols_is).reindex(days_is).fillna(0.0).mean(axis=1)
        out = pd.DataFrame(cols_oos).reindex(days_oos).fillna(0.0).mean(axis=1)
        unit = float(ins.std())                                  # risk is scaled with the calibration window only
        is_days.append(ins / unit)
        oos_days.append(out / unit)
    tr = pd.concat(trades, ignore_index=True) if trades else pd.DataFrame(columns=["r", "r_bruto", "motivo", "cesta", "horas", "entrada"])
    return {"oos": pd.concat(oos_days), "ins": pd.concat(is_days) if is_days else pd.Series(dtype=float), "trades": tr,
            "log": pd.DataFrame(log)}


def max_drawdown(x: pd.Series) -> float:
    c = x.cumsum()
    return float((c - c.cummax()).min())


def summary(res: dict, paths: int = 10_000) -> pd.DataFrame:
    from prop.research.approval_map import as_days, journey
    tr, oos, ins = res["trades"], res["oos"], res["ins"]
    wins, losses = tr.loc[tr["r"] > 0, "r"], tr.loc[tr["r"] <= 0, "r"]
    years = max((oos.index[-1] - oos.index[0]).days / 365.25, 1e-9)
    row = {"trades fora da amostra": len(tr), "trades por ano": round(len(tr) / years, 1),
           "acerto liquido %": round(100 * (tr["r"] > 0).mean(), 1) if len(tr) else np.nan,
           "acerto bruto %": round(100 * (tr["r_bruto"] > 0).mean(), 1) if len(tr) else np.nan,
           "R medio bruto": round(tr["r_bruto"].mean(), 3), "R medio liquido": round(tr["r"].mean(), 3),
           "t do R liquido": round(tr["r"].mean() / tr["r"].std() * np.sqrt(len(tr)), 2) if len(tr) > 2 else np.nan,
           "ganho medio / perda media": round(wins.mean() / -losses.mean(), 2) if len(wins) and len(losses) else np.nan,
           "sharpe anual fora da amostra": round(S.sharpe(oos), 2), "sharpe anual no treino": round(S.sharpe(ins), 2),
           "queda maxima % (conta a 0,3% de oscilacao por dia)": round(100 * 0.003 * max_drawdown(oos), 1)}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        j = journey("nucleo A", as_days(oos.to_numpy(), 1.0), ins.to_numpy(), paths)
        luck = journey("sorte", as_days((oos - oos.mean()).to_numpy(), 1.0), (ins - ins.mean()).to_numpy(), paths)
    row.update({"aprovacao F1+F2 %": j["aprovacao_F1+F2_%"], "aprovado em 12 meses %": j["aprovado_em_12m_%"],
                "reprova %": j["reprova_%"], "saques 12 meses US$": j["saques_12m_usd"], "EV por tentativa US$": j["EV_usd"],
                "aprovacao com media zero (sorte pura) %": luck["aprovacao_F1+F2_%"]})
    return pd.DataFrame({"Nucleo A (Kalman/OU)": row})


def main() -> None:
    global ENTRIES, COVER, STOP_GAP
    if "--seletivo" in sys.argv:                                 # pivot 1: trade only where the deviation pays the costs several times
        sys.argv.remove("--seletivo")
        ENTRIES, COVER, STOP_GAP = (2.5, 3.0, 3.5), 5.0, 2.0
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/mt5")
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else folder
    m = S.Market(folder)
    print(f"pasta {folder}: {len(list(folder.glob('*_H1.csv.gz')))} arquivos H1")
    res = run(m)
    log, tr = res["log"], res["trades"]
    pd.set_option("display.width", 250, "display.max_rows", 500, "display.max_columns", 30)
    print("\n=== Calibracao por janela (so dados de treino) ===")
    print(log.groupby("teste_de").agg(cestas=("cesta", "size"), cointegradas=("motivo", lambda s: int((s != "sem cointegracao").sum() - (s == "historico curto").sum())),
                                      escolhidas=("escolhida", lambda s: int(s.notna().sum()))).to_string())
    if len(tr):
        print("\n=== Trades fora da amostra por cesta ===")
        print(tr.groupby("cesta").agg(trades=("r", "size"), r_bruto=("r_bruto", "mean"), r_liquido=("r", "mean"),
                                      acerto=("r", lambda s: (s > 0).mean()), horas=("horas", "mean")).round(3).to_string())
        print("\n=== Motivo de saida ===")
        print(tr.groupby("motivo").agg(trades=("r", "size"), r_liquido=("r", "mean")).round(3).to_string())
        print("\n=== Por ano ===")
        print(tr.groupby(tr["entrada"].dt.year).agg(trades=("r", "size"), r_bruto=("r_bruto", "mean"), r_liquido=("r", "mean")).round(3).to_string())
    table = summary(res)
    print("\n=== Passo 1: Nucleo A fora da amostra ===")
    print(table.to_string())
    out_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(out_dir / "nucleo_a_resumo.csv")
    tr.to_csv(out_dir / "nucleo_a_trades_oos.csv", index=False)
    log.to_csv(out_dir / "nucleo_a_calibracao.csv", index=False)
    res["oos"].to_csv(out_dir / "nucleo_a_dias_oos.csv")


if __name__ == "__main__":
    main()
