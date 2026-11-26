"""PAPER forward test (fake money, public data, no API key) of the final setup:
the listing short sized by the V5 Bellman controller on a simulated US$ 10,000 challenge.

Rule: when Binance lists a new USDT spot pair, wait 24 hours; if its perpetual future exists,
short it, stop 30% above the entry, close after 7 days. Risk per trade comes from the account
state (distance to the target and to the loss limits). Every result is booked on a simulated
2-step challenge, so the log shows "Fase 1 aprovada", "reprovado", payouts.

    python -m prop.live.listing_paper            run forever (checks every 10 minutes)
    python -m prop.live.listing_paper --once     one check
    python -m prop.live.listing_paper --report   show the simulated account and its trades

State lives in SQLite (data/listing_paper.db), so a restart continues where it stopped.
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd

from prop.config.quant import Q
from prop.live.challenge_account import ChallengeAccount
from prop.persistence.state_store import StateStore
from prop.risk import bellman_barrier_controller as bbc
from prop.risk import dual_bellman_solver as dbs

log = logging.getLogger("listing-paper")
WAIT_H, HOLD_H, STOP = 24, 7 * 24, 0.30
COST = 0.00045 + 0.0010                 # per side: taker fee + slippage, same as the backtest
ENTRY_GRACE_H = 6                       # skip the entry if the bot was offline for longer than this
ACTIONS = np.array([0.0025, 0.005, 0.0075, 0.010, 0.0125, 0.015, 0.02])
FUNDED_ACTIONS = np.array([0.0035, 0.005, 0.0075, 0.010])
SKIP = ("UP", "DOWN", "BULL", "BEAR")
STABLE = {"USDC", "FDUSD", "TUSD", "USDP", "DAI", "EUR", "USD1", "RLUSD", "AEUR", "EURI", "XUSD", "BFUSD", "USDE",
          "PYUSD", "U"}
DB = Path("data/listing_paper.db")
R_SAMPLE = Path(__file__).resolve().parent.parent / "config" / "listing_alpha_r.json"


class BinanceApi:
    """The four public calls the bot needs."""

    def __init__(self) -> None:
        from kenui_trader import live
        self.live = live

    def spot_symbols(self) -> set[str]:
        info = self.live.get(self.live.SPOT, "/api/v3/exchangeInfo")
        return {s["symbol"] for s in info["symbols"] if s["status"] == "TRADING" and s["quoteAsset"] == "USDT"}

    def perp_symbols(self) -> set[str]:
        info = self.live.get(self.live.FUT, "/fapi/v1/exchangeInfo")
        return {s["symbol"] for s in info["symbols"] if s["status"] == "TRADING" and s["contractType"] == "PERPETUAL"}

    def hourly(self, perp: str, start: pd.Timestamp) -> pd.DataFrame:
        rows = self.live.get(self.live.FUT, "/fapi/v1/klines", {"symbol": perp, "interval": "1h", "limit": 500,
                                                                "startTime": int(start.timestamp() * 1000)})
        df = pd.DataFrame(rows).iloc[:, :5].set_axis(["t", "open", "high", "low", "close"], axis=1).astype(float)
        df.index = pd.to_datetime(df.pop("t"), unit="ms", utc=True)
        return df

    def funding(self, perp: str, start: pd.Timestamp, end: pd.Timestamp) -> float:
        rows = self.live.get(self.live.FUT, "/fapi/v1/fundingRate",
                             {"symbol": perp, "startTime": int(start.timestamp() * 1000),
                              "endTime": int(end.timestamp() * 1000), "limit": 1000})
        return float(sum(float(r["fundingRate"]) for r in rows))


POLICY = R_SAMPLE.with_name("listing_policy.npz")


def policies(solve: bool = False):
    """Designed for HALF of the measured edge. The solved tables ship with the code
    (`python -m prop.live.listing_paper --solve` rebuilds them, about 2 minutes)."""
    if POLICY.exists() and not solve:
        z = np.load(POLICY)
        barrier = {k: bbc.BarrierPolicy(z["xg%d" % k], z["dg"], z["risk%d" % k], z["value%d" % k], float(z["target%d" % k]))
                   for k in (0, 1)}
        return barrier, dbs.HarvestPolicy(z["hx"], z["hrisk"], z["hvalue"], float(z["trigger"]))
    barrier, harvest = _solve()
    np.savez_compressed(POLICY, dg=barrier[0].d_grid, hx=harvest.x_grid, hrisk=harvest.risk, hvalue=harvest.value,
                        trigger=harvest.trigger, **{f"{n}{k}": getattr(barrier[k], a) for k in (0, 1) for n, a in
                                                    (("xg", "x_grid"), ("risk", "risk"), ("value", "value"), ("target", "target"))})
    return barrier, harvest


def _solve():
    r = np.array(json.loads(R_SAMPLE.read_text())["r"], float)
    vals, probs = bbc.outcome_distribution(r, design_edge=0.5 * float(r.mean()), bin_r=0.25)
    kw = dict(trades_per_day=1.0, discount=0.998, actions=ACTIONS)
    barrier = {0: bbc.solve_evaluation(vals, probs, Q.phase1_target, **kw),
               1: bbc.solve_evaluation(vals, probs, Q.phase2_target, **kw)}
    return barrier, dbs.solve_funded(vals, probs, actions=FUNDED_ACTIONS)


def eligible(symbol: str) -> bool:
    base = symbol[:-4]
    return symbol.endswith("USDT") and base not in STABLE and not any(base.endswith(k) for k in SKIP)


def prague_day(now: pd.Timestamp) -> str:
    return now.tz_convert("Europe/Prague").strftime("%Y-%m-%d")


class ListingPaper:
    def __init__(self, store: StateStore, api, barrier, harvest) -> None:
        self.store, self.api, self.barrier, self.harvest = store, api, barrier, harvest
        s = store.load("listing_paper") or {}
        self.known: set[str] | None = set(s["known"]) if "known" in s else None
        self.pending: dict[str, str] = s.get("pending", {})        # symbol -> listing time (ISO)
        self.open: list[dict] = s.get("open", [])
        self.closed: list[dict] = s.get("closed", [])
        self.skipped: list[list] = s.get("skipped", [])
        self.account = ChallengeAccount.from_dict(s["account"]) if "account" in s else ChallengeAccount()

    def save(self) -> None:
        self.store.save_many({"listing_paper": {
            "known": sorted(self.known or []), "pending": self.pending, "open": self.open, "closed": self.closed,
            "skipped": self.skipped, "account": self.account.to_dict()}})

    # one cycle ----------------------------------------------------------------
    def step(self, now: pd.Timestamp) -> None:
        self.account.new_day(prague_day(now))
        self.detect(now)
        self.manage(now)
        self.enter(now)
        self.save()

    def detect(self, now: pd.Timestamp) -> None:
        current = self.api.spot_symbols()
        if self.known is None:
            self.known = set(current)
            log.info("primeira execucao: %d pares USDT conhecidos; a contagem comeca na proxima listagem", len(current))
            return
        for sym in sorted(current - self.known):
            if eligible(sym):
                self.pending[sym] = now.isoformat()
                log.info("NOVA LISTAGEM %s: entrada simulada em 24 horas se houver contrato perpetuo", sym)
        self.known |= current

    def enter(self, now: pd.Timestamp) -> None:
        due = {s: t for s, t in self.pending.items() if now >= pd.Timestamp(t) + pd.Timedelta(hours=WAIT_H)}
        if not due:
            return
        perps = self.api.perp_symbols()
        for sym, t in due.items():
            del self.pending[sym]
            perp = sym if sym in perps else ("1000" + sym if "1000" + sym in perps else None)
            late = now - (pd.Timestamp(t) + pd.Timedelta(hours=WAIT_H))
            open_risk = sum(p["risk"] for p in self.open)
            risk = self.account.risk(self.barrier, self.harvest, open_risk)
            why = ("sem contrato perpetuo" if perp is None else
                   "robo estava desligado na hora da entrada" if late > pd.Timedelta(hours=ENTRY_GRACE_H) else
                   "trava de risco do dia ou risco aberto no limite" if risk <= 0 else None)
            if why:
                self.skipped.append([now.isoformat(), sym, why])
                log.info("%s ignorada: %s", sym, why)
                continue
            bars = self.api.hourly(perp, now - pd.Timedelta(hours=2))
            entry = float(bars["close"].iloc[-1])
            self.open.append({"symbol": sym, "perp": perp, "entry_time": now.isoformat(), "entry": entry,
                              "stop": entry * (1 + STOP), "risk": risk, "phase": self.account.phase,
                              "checked": now.isoformat()})
            log.info("PAPER SHORT %s a %.6g, stop %.6g, risco %.2f%% da conta (fase %d)", perp, entry,
                     entry * (1 + STOP), 100 * risk, self.account.phase + 1)

    def manage(self, now: pd.Timestamp) -> None:
        still, floating = [], 0.0
        for p in self.open:
            t0 = pd.Timestamp(p["entry_time"])
            bars = self.api.hourly(p["perp"], pd.Timestamp(p["checked"]).floor("h"))
            bars = bars[bars.index >= t0.floor("h")]
            after = bars[bars.index >= t0]          # the entry bar's high may predate the entry: not a stop
            end = t0 + pd.Timedelta(hours=HOLD_H)
            hit = after[(after["high"] >= p["stop"]) & (after.index < end)]
            exit_px = exit_t = reason = None
            if len(hit):
                exit_t, reason = hit.index[0], "stop"
                exit_px = max(p["stop"], float(hit["open"].iloc[0]))
            elif now >= end:
                last = bars[bars.index < end]
                exit_t, reason = end, "tempo"
                exit_px = float(last["close"].iloc[-1]) if len(last) else p["entry"]
            if exit_px is None:
                p["checked"] = now.isoformat()
                last_px = float(bars["close"].iloc[-1]) if len(bars) else p["entry"]
                floating += p["risk"] * (-(last_px / p["entry"] - 1)) / STOP
                still.append(p)
                continue
            self.close(p, exit_px, pd.Timestamp(exit_t), reason, now)
        self.open = still
        if self.open and self.account.day_pnl + min(floating, 0.0) <= -Q.hard_daily_kill:
            log.info("TRAVA DIARIA: perda do dia chegou a %.1f%%, fechando tudo", 100 * Q.hard_daily_kill)
            for p in self.open:
                bars = self.api.hourly(p["perp"], now - pd.Timedelta(hours=2))
                self.close(p, float(bars["close"].iloc[-1]), now, "trava diaria", now)
            self.open, self.account.day_locked = [], True

    def close(self, p: dict, exit_px: float, exit_t: pd.Timestamp, reason: str, now: pd.Timestamp) -> None:
        try:
            fund = self.api.funding(p["perp"], pd.Timestamp(p["entry_time"]), exit_t)   # a short receives positive funding
        except Exception as exc:  # funding is a detail; never lose the trade result because of it
            log.info("funding indisponivel para %s: %s", p["perp"], exc)
            fund = 0.0
        ret = -(exit_px / p["entry"] - 1) - 2 * COST + fund
        r = ret / STOP
        event = self.account.book(p["risk"] * r, now.isoformat())
        self.closed.append({**p, "exit_time": exit_t.isoformat(), "exit": exit_px, "reason": reason,
                            "funding": fund, "ret": ret, "r": r, "pnl_pct": 100 * p["risk"] * r})
        log.info("PAPER FECHOU %s (%s): %+.1f%% no preco, %+.2fR, conta %+.2f%% | fase %d, acumulado %+.2f%%",
                 p["perp"], reason, 100 * ret, r, 100 * p["risk"] * r, self.account.phase + 1, 100 * self.account.x)
        if event:
            log.info("CONTA SIMULADA: %s", event)


def report(store: StateStore) -> str:
    s = store.load("listing_paper")
    if not s:
        return "Ainda sem dados: o robo nao rodou nenhum ciclo."
    a, closed = s["account"], s.get("closed", [])
    rs = [c["r"] for c in closed]
    lines = [
        "ROBO DE LISTAGEM EM MODO PAPER (dinheiro de mentira)",
        f"Conta simulada de US$ {Q.account_size:,.0f}: fase {a['phase'] + 1 if a['phase'] < 2 else 'financiada'}, "
        f"resultado na fase {100 * a['x']:+.2f}%, tentativa {a['attempts']}",
        f"Fases 1 aprovadas: {a['passed_p1']} | contas financiadas: {a['funded']} | reprovacoes: {a['failed']} | "
        f"saques simulados: US$ {a['payouts_usd']:.0f}",
        f"Operacoes fechadas: {len(rs)}" + (f", media {np.mean(rs):+.2f}R, acerto {100 * np.mean(np.array(rs) > 0):.0f}%"
                                              if rs else ""),
        f"Abertas: {len(s.get('open', []))} | aguardando 24h: {', '.join(s.get('pending', {})) or 'nenhuma'} | "
        f"ignoradas: {len(s.get('skipped', []))}"]
    lines += [f"  {c['exit_time'][:16]} {c['perp']:<14} {c['reason']:<13} {c['r']:+.2f}R  conta {c['pnl_pct']:+.2f}%"
              for c in closed[-15:]]
    lines += [f"  {t[:16]} {e}" for t, e in a.get("events", [])[-10:]]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--every", type=int, default=600, help="seconds between checks")
    ap.add_argument("--solve", action="store_true", help="rebuild the risk policy tables and exit")
    args = ap.parse_args()
    if args.solve:
        policies(solve=True)
        print(f"politica gravada em {POLICY}")
        return
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    DB.parent.mkdir(parents=True, exist_ok=True)
    store = StateStore(DB)
    if args.report:
        print(report(store))
        return
    barrier, harvest = policies()
    bot = ListingPaper(store, BinanceApi(), barrier, harvest)
    while True:
        try:
            bot.step(pd.Timestamp.now(tz="UTC"))
            log.info("ciclo ok: %d aguardando, %d abertas, %d fechadas | fase %d, %+.2f%%", len(bot.pending), len(bot.open),
                     len(bot.closed), bot.account.phase + 1, 100 * bot.account.x)
        except Exception:
            log.exception("ciclo falhou; tenta de novo no proximo")
        if args.once:
            return
        time.sleep(args.every)


if __name__ == "__main__":
    main()
