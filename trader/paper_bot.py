"""Paper-trading bot: runs the step-2 candidate live with FAKE money. No API key, no real orders.

Every 5 minutes:
  1. download the newest public candles / futures data for the 39 coins
  2. compute the same ~110 signals used in research and ask the model for a 1-hour forecast
  3. rule: buy (on paper) when forecast > +0.5%; hold 1 hour; keep while forecast stays > +0.5%;
     at most 5 positions, each 1/5 of the account
  4. fills use the real bid/ask at that moment and pay the 0.075% fee per side
Everything is logged in data/paper/ (trades.csv, cycles.csv, state.json).

Run:   python paper_bot.py            (loops forever)
       python paper_bot.py --once     (one cycle, for testing)
Must run outside the US (Binance blocks US IPs).
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from kenui_trader import live, vision
from research import dataset as DS, features as F, panel as P

HERE = Path(__file__).resolve().parent
OUT = HERE / "data" / "paper"
MODEL = HERE / "models" / "pred_1h"
THETA, HOLD_BARS, K = 0.005, 12, 5
FEE = 0.00075
START_CAPITAL = 60.0
HIST_DAYS = 41
BAR = pd.Timedelta(minutes=5)
log = logging.getLogger("paper")


# ---------------------------------------------------------------- data store
class Store:
    """Keeps the last HIST_DAYS of raw data per coin, bootstrapped from the archive, updated by REST."""

    def __init__(self, universe):
        self.universe = universe
        self.raw: dict[str, dict[str, pd.DataFrame]] = {}

    @staticmethod
    def _topup(fn, old: pd.DataFrame, max_calls=12, **kw) -> pd.DataFrame:
        cur = old
        for _ in range(max_calls):
            start = (cur.index[-1] + BAR) if len(cur) else pd.Timestamp.now(tz="UTC") - timedelta(days=3)
            new = fn(start=start, **kw)
            if not len(new):
                break
            cur = pd.concat([cur, new])
            cur = cur[~cur.index.duplicated(keep="last")].sort_index()
            if cur.index[-1] >= pd.Timestamp.now(tz="UTC") - 3 * BAR:
                break
        return cur

    def bootstrap(self):
        today = pd.Timestamp.now(tz="UTC").date()
        a, b = today - timedelta(days=HIST_DAYS), today - timedelta(days=2)
        for u in self.universe:
            f, sp = u["fut"], u["spot"]
            try:
                r = {"s": vision.fetch("spot", "klines", sp, a, b, "5m"),
                     "f": vision.fetch("futures/um", "klines", f, a, b, "5m"),
                     "p": vision.fetch("futures/um", "premiumIndexKlines", f, a, b, "5m"),
                     "m": vision.fetch("futures/um", "metrics", f, a, b)}
                r["s"] = self._topup(lambda start: live.spot_klines(sp, 1000, start), r["s"])
                r["f"] = self._topup(lambda start: live.fut_klines(f, 1000, start), r["f"])
                r["p"] = self._topup(lambda start: live.fut_klines(f, 1000, start, "premiumIndexKlines"), r["p"])
                r["m"] = self._topup(lambda start: live.metrics(f, 500, start), r["m"])
                r["fr"] = live.funding(f, 200)
                self.raw[f] = r
                log.info("bootstrap %s: %d candles, last %s", f, len(r["s"]), r["s"].index[-1])
            except Exception as e:  # a delisted or broken coin must not stop the bot
                log.warning("bootstrap %s failed: %s", f, e)

    def _update_one(self, u, cut):
        f, sp = u["fut"], u["spot"]
        r = self.raw.get(f)
        if r is None:
            return
        try:
            r["s"] = self._topup(lambda start: live.spot_klines(sp, 1000, start), r["s"])
            r["f"] = self._topup(lambda start: live.fut_klines(f, 1000, start), r["f"])
            r["p"] = self._topup(lambda start: live.fut_klines(f, 1000, start, "premiumIndexKlines"), r["p"])
            r["m"] = self._topup(lambda start: live.metrics(f, 500, start), r["m"])
            if pd.Timestamp.now(tz="UTC").minute < 5:
                r["fr"] = live.funding(f, 200)
            for k in ("s", "f", "p", "m"):
                r[k] = r[k][r[k].index >= cut]
        except Exception as e:
            log.warning("update %s failed: %s", f, e)

    def update(self):
        cut = pd.Timestamp.now(tz="UTC") - timedelta(days=HIST_DAYS)
        with ThreadPoolExecutor(6) as ex:
            list(ex.map(lambda u: self._update_one(u, cut), self.universe))

    def panels(self) -> dict[str, pd.DataFrame]:
        out = {}
        for u in self.universe:
            r = self.raw.get(u["fut"])
            if r is None:
                continue
            df = P.merge(u, r["s"], r["f"], r["p"], r["fr"], r["m"])
            if df is not None and len(df) > 8 * F.D:
                out[u["fut"]] = df
        return out


# ---------------------------------------------------------------- model
def latest_features(panels: dict[str, pd.DataFrame], T: pd.Timestamp | None = None) -> pd.DataFrame:
    """Feature row of every coin for the candle that opened at T (default: the newest common candle)."""
    btc = panels["BTCUSDT"]
    T = T or btc.index[-1]
    Xs = {}
    for s, df in panels.items():
        df = df.loc[:T]
        X = F.make(df, btc.loc[:T])
        X["ok"] = (df["traded"].rolling(12).sum() >= 10).astype("float32")
        Xs[s] = X
    DS.add_context(Xs, btc.loc[:T].index)
    rows = {s: X.loc[T] for s, X in Xs.items() if T in X.index}
    return pd.DataFrame(rows).T


class Model:
    def __init__(self):
        meta = json.loads(Path(str(MODEL) + ".json").read_text())
        self.feats, self.scale, self.trained_until = meta["features"], meta["scale"], meta["trained_until"]
        self.booster = lgb.Booster(model_file=str(MODEL) + ".txt")

    def predict(self, feat_rows: pd.DataFrame) -> pd.Series:
        X = feat_rows[self.feats].to_numpy(dtype="float32")
        p = pd.Series(self.booster.predict(X) * self.scale, index=feat_rows.index)
        return p.where(feat_rows["ok"] > 0)


# ---------------------------------------------------------------- paper account
class Account:
    def __init__(self):
        OUT.mkdir(parents=True, exist_ok=True)
        self.path = OUT / "state.json"
        if self.path.exists():
            st = json.loads(self.path.read_text())
            self.equity, self.pos = st["equity"], st["positions"]
        else:
            self.equity, self.pos = START_CAPITAL, {}

    def save(self):
        self.path.write_text(json.dumps({"equity": self.equity, "positions": self.pos}, indent=1))

    def step(self, T: pd.Timestamp, pred: pd.Series, book: pd.DataFrame, spot_of: dict):
        trades = []
        for sym in list(self.pos):
            p = self.pos[sym]
            held = int((T - pd.Timestamp(p["t_in"])) / BAR)
            still_good = pred.get(sym, np.nan) > THETA
            sp = spot_of[sym]
            if held >= HOLD_BARS and not still_good and sp in book.index:
                bid = book.loc[sp, "bidPrice"]
                ret = (bid * (1 - FEE)) / (p["entry_px"] * (1 + FEE)) - 1
                pnl = p["alloc"] * ret
                self.equity += pnl
                trades.append({"t_in": p["t_in"], "t_out": str(T + BAR), "sym": sym, "entry": p["entry_px"], "exit": bid,
                               "alloc": round(p["alloc"], 4), "ret_net_%": round(ret * 100, 4), "pnl": round(pnl, 4),
                               "equity": round(self.equity, 4), "pred_in_%": p["pred"]})
                del self.pos[sym]
        free = K - len(self.pos)
        cand = pred[(pred > THETA) & ~pred.index.isin(self.pos)].sort_values(ascending=False)
        for sym, pr in cand.items():
            if free <= 0:
                break
            sp = spot_of[sym]
            if sp not in book.index:
                continue
            self.pos[sym] = {"t_in": str(T), "entry_px": float(book.loc[sp, "askPrice"]),
                             "alloc": self.equity / K, "pred": round(float(pr) * 100, 3)}
            free -= 1
            log.info("PAPER BUY %s at %s (forecast +%.2f%%)", sym, self.pos[sym]["entry_px"], pr * 100)
        if trades:
            f = OUT / "trades.csv"
            pd.DataFrame(trades).to_csv(f, mode="a", header=not f.exists(), index=False)
            for t in trades:
                log.info("PAPER SELL %s ret %.2f%% equity %.2f", t["sym"], t["ret_net_%"], t["equity"])
        self.save()
        return trades


# ---------------------------------------------------------------- main loop
def cycle(store: Store, model: Model, acct: Account, spot_of: dict):
    store.update()
    panels = store.panels()
    T = panels["BTCUSDT"].index[-1]
    age = pd.Timestamp.now(tz="UTC") - (T + BAR)
    if age > 2 * BAR:
        log.warning("data is stale (%s old): no new entries this cycle", age)
        return
    feats = latest_features(panels, T)
    pred = model.predict(feats)
    book = live.book(list(spot_of.values()))
    acct.step(T, pred, book, spot_of)
    top = pred.sort_values(ascending=False).head(3)
    row = {"time": str(T + BAR), "equity": round(acct.equity, 4), "positions": len(acct.pos), "coins": int(pred.notna().sum()),
           "best": top.index[0], "best_pred_%": round(top.iloc[0] * 100, 3), "median_pred_%": round(pred.median() * 100, 3)}
    f = OUT / "cycles.csv"
    pd.DataFrame([row]).to_csv(f, mode="a", header=not f.exists(), index=False)
    log.info("cycle %s equity %.2f positions %d best %s %+.2f%%", row["time"], acct.equity, len(acct.pos), row["best"], row["best_pred_%"])


def report():
    """Plain summary of the paper account so far."""
    acct = Account()
    f = OUT / "trades.csv"
    cyc = pd.read_csv(OUT / "cycles.csv") if (OUT / "cycles.csv").exists() else pd.DataFrame()
    print(f"Paper account: {acct.equity:.2f} USDT (started with {START_CAPITAL:.2f}); open positions: {list(acct.pos) or 'none'}")
    if len(cyc):
        print(f"Running since {cyc['time'].iloc[0]}; cycles: {len(cyc)}; last: {cyc['time'].iloc[-1]}")
    if f.exists():
        t = pd.read_csv(f)
        print(f"Closed trades: {len(t)}; winners: {(t['pnl'] > 0).mean() * 100:.0f}%; average net per trade: {t['ret_net_%'].mean():.2f}%")
        print(t.tail(10).to_string(index=False))
    else:
        print("No closed trades yet (this rule trades only on a few days per month).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.report:
        return report()
    OUT.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(OUT / "paper.log")])
    universe = [u for u in P.UNIVERSE if u["fut"] != "FTMUSDT"]
    spot_of = {u["fut"]: u["spot"] for u in universe}
    model, acct, store = Model(), Account(), Store(universe)
    log.info("model trained until %s; paper equity %.2f; bootstrapping history...", model.trained_until, acct.equity)
    store.bootstrap()
    while True:
        try:
            cycle(store, model, acct, spot_of)
        except Exception:
            log.exception("cycle failed")
        if a.once:
            break
        now = time.time()
        time.sleep(300 - (now % 300) + 25)   # 25 s after each 5-minute boundary


if __name__ == "__main__":
    main()
