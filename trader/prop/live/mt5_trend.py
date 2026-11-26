"""MetaTrader 5 robot for the one rule that survived the real-data study: long-only trend in
gold and silver (50/200-day averages), sized by daily volatility and by the prop-firm account
state (Phase 1, Phase 2, funded).

It talks to the terminal that is already open and logged in (MetaTrader5 Python package), so it
never sees a password. Safety, in this order:
  - without --live it only prints the plan;
  - --live refuses any account that is not a DEMO account unless --conta-real is also given;
  - circuit breaker: at 60% of the firm's daily loss limit everything is closed and the day is locked;
  - every position carries a stop on the broker's server, in case this computer goes off;
  - no new orders in the rollover window or when the spread is abnormal.

    python -m prop.live.mt5_trend --solve C:\\...\\mt5data      # once: sizing policy from history before 2019
    python -m prop.live.mt5_trend                              # plan only
    python -m prop.live.mt5_trend --live                       # one pass, sends orders (demo)
    python -m prop.live.mt5_trend --live --loop                # keeps running
    python -m prop.live.mt5_trend --live --flatten             # close everything of this robot
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RULES_FILE = ROOT / "config" / "prop_rules.json"
STATE_DB = ROOT / "state" / "mt5_trend.db"
SYMBOLS = ("XAUUSD", "XAGUSD")
FAST, SLOW, VOL_SPAN = 50, 200, 30
MAGIC = 550055                        # same as the MQL5 guardian, so its kill switch covers these positions
BREAKER = 0.60                        # share of the daily loss limit that triggers the circuit breaker
DEFAULT_BUDGET = 0.003                # daily volatility of the account when no policy file exists
DEFAULT_UNIT = 0.006                  # daily std of the 1%-per-asset portfolio (replaced by --solve)
STOP_SIGMAS = 4.0                     # server-side stop: this many daily volatilities below the price
ROLLOVER_UTC = (21.75, 23.25)
REBALANCE_BAND = 0.25                 # trade only when the lot is off by more than this share of the target


# ---- pure logic (tested without MetaTrader) --------------------------------------------------------
def load_rules(firm: str = "padrao") -> dict:
    rules = json.loads(RULES_FILE.read_text(encoding="utf-8"))
    if firm not in rules or firm.startswith("_"):
        raise SystemExit(f"mesa desconhecida: {firm}. Opcoes: {[k for k in rules if not k.startswith('_')]}")
    return rules[firm]


def policy_file(firm: str) -> Path:
    return ROOT / "config" / f"mt5_trend_policy_{firm}.npz"


def weight(d: pd.DataFrame) -> float:
    """Notional of one asset as a multiple of the account for a 1% daily move budget:
    0 when the 50-day average is below the 200-day one, else 1% / daily volatility (max 3)."""
    c = d["close"]
    if len(c) < SLOW:
        return 0.0
    up = c.ewm(span=FAST).mean().iloc[-1] > c.ewm(span=SLOW).mean().iloc[-1]
    vol = float(np.log(c).diff().ewm(span=VOL_SPAN, min_periods=VOL_SPAN).std().iloc[-1])
    return float(min(0.01 / vol, 3.0)) if up and vol > 0 else 0.0


def daily_vol(d: pd.DataFrame) -> float:
    return float(np.log(d["close"]).diff().ewm(span=VOL_SPAN, min_periods=VOL_SPAN).std().iloc[-1])


@dataclass
class Policy:
    """Daily volatility budget of the account for each state. Built by --solve."""
    unit: float = DEFAULT_UNIT
    tables: dict | None = None

    @classmethod
    def load(cls, path: Path) -> "Policy":
        if not path.exists():
            return cls()
        z = np.load(path)
        return cls(float(z["unit"]), {k: z[k] for k in z.files if k != "unit"})

    def budget(self, phase: int, x: float, day: float) -> float:
        if self.tables is None:
            return DEFAULT_BUDGET
        t = self.tables
        if phase >= 2:
            xg = t["h_x"]
            return float(t["h_risk"][int(np.clip(round((x - xg[0]) / (xg[1] - xg[0])), 0, len(xg) - 1))])
        xg, dg, risk = t[f"b{phase}_x"], t[f"b{phase}_d"], t[f"b{phase}_risk"]
        ix = int(np.clip(round((x - xg[0]) / (xg[1] - xg[0])), 0, len(xg) - 1))
        idd = int(np.clip(round((day - dg[0]) / (dg[1] - dg[0])), 0, len(dg) - 1))
        return float(risk[ix, idd])


def target_lots(w: float, budget: float, unit: float, n_assets: int, equity: float, price: float, contract: float,
                step: float, vmin: float, vmax: float) -> float:
    """Lots that give this asset its share of the account's daily volatility budget."""
    notional = equity * w * budget / unit / n_assets
    lots = notional / (contract * price) if contract * price > 0 else 0.0
    lots = round(lots / step) * step
    return 0.0 if lots < vmin else float(min(round(lots, 8), vmax))


def needs_trade(current: float, target: float, step: float) -> bool:
    if target == 0.0:
        return current > 0.0
    return abs(target - current) >= max(step, REBALANCE_BAND * target) - 1e-9


def in_rollover(now: datetime) -> bool:
    h = now.hour + now.minute / 60
    return ROLLOVER_UTC[0] <= h < ROLLOVER_UTC[1]


class State:
    """Account state that must survive a restart (SQLite in WAL mode)."""

    def __init__(self, path: Path = STATE_DB) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS log (t TEXT, event TEXT)")
        self.db.commit()

    def get(self, k: str, default=None):
        row = self.db.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, **kv) -> None:
        self.db.executemany("INSERT OR REPLACE INTO kv VALUES (?,?)", [(k, json.dumps(v)) for k, v in kv.items()])
        self.db.commit()

    def log(self, event: str) -> None:
        self.db.execute("INSERT INTO log VALUES (?,?)", (datetime.now(timezone.utc).isoformat(timespec="seconds"), event))
        self.db.commit()
        print(f"  [{event}]", flush=True)


def account_step(st: State, rules: dict, equity: float, now: datetime) -> dict:
    """Updates phase, day and breaker from the current equity. Returns the state to act on:
    phase, x (result of the phase), day (result of the day), locked, flatten (close everything now)."""
    day = now.astimezone(ZoneInfo(rules["fuso_do_dia"])).strftime("%Y-%m-%d")
    phase, start = st.get("phase", 0), st.get("phase_start")
    if start is None:
        start = equity
        st.set(phase=phase, phase_start=start)
        st.log(f"inicio: Fase 1 com saldo {equity:.2f}")
    if st.get("day") != day:
        st.set(day=day, day_start=equity, locked=False)
    day_start, locked = st.get("day_start"), st.get("locked", False)
    x, d = equity / start - 1.0, equity / day_start - 1.0
    flatten = False
    if not locked and d <= -BREAKER * rules["perda_diaria"]:
        locked = flatten = True
        st.set(locked=True)
        st.log(f"freio do dia: {100 * d:.2f}% (limite da mesa {100 * rules['perda_diaria']:.0f}%)")
    if x <= -rules["perda_total"] or d <= -rules["perda_diaria"]:
        st.log(f"REGRA DA MESA VIOLADA (fase {phase + 1}): total {100 * x:.2f}%, dia {100 * d:.2f}%. Recomeca na Fase 1")
        phase, start, flatten = 0, equity, True
        st.set(phase=0, phase_start=equity, failed=st.get("failed", 0) + 1)
        x = 0.0
    elif phase < 2 and x >= rules["meta_fase1" if phase == 0 else "meta_fase2"]:
        st.log(f"Fase {phase + 1} aprovada com {100 * x:.2f}%")
        phase, flatten = phase + 1, True
        st.set(phase=phase, phase_start=equity)
        x = 0.0
    elif phase == 2 and x >= rules["gatilho_saque"]:
        usd = rules["divisao_lucro"] * (equity - start)
        st.log(f"saque simulado de US$ {usd:.2f}")
        st.set(phase_start=equity, payouts=st.get("payouts", 0.0) + usd)
        x = 0.0
    return {"phase": phase, "x": x, "day": d, "locked": locked, "flatten": flatten}


# ---- policy from history ------------------------------------------------------------------------------
def solve(folder: Path, firm: str) -> None:
    """Sizing policy from the days BEFORE 2019 only, with the firm's targets and limits."""
    from prop.research import mt5_study as S
    from prop.research.approval_map import FUNDED_MENU, VOL_MENU
    from prop.risk import bellman_barrier_controller as bbc
    from prop.risk import dual_bellman_solver as dbs

    rules = load_rules(firm)
    m = S.Market(folder)
    r = S.trend(m, list(SYMBOLS), f"ema{FAST}_{SLOW}", True)
    ins = r[r.index < S.SPLIT].dropna()
    unit = float(ins.std())
    vals, probs = bbc.outcome_distribution(np.clip(ins.to_numpy() / unit, -4, 4), bin_r=0.5)
    kill = BREAKER * rules["perda_diaria"]
    kw = dict(max_loss=rules["perda_total"], daily_kill=kill, trades_per_day=1.0, discount=0.999, actions=VOL_MENU,
              sweeps=1200, tol=1e-5)
    b0 = bbc.solve_evaluation(vals, probs, rules["meta_fase1"], **kw)
    b1 = bbc.solve_evaluation(vals, probs, rules["meta_fase2"], **kw)
    h = dbs.solve_funded(vals, probs, trigger=rules["gatilho_saque"], max_loss=rules["perda_total"],
                         split=rules["divisao_lucro"], actions=FUNDED_MENU, sweeps=4000, tol=1e-7)
    np.savez_compressed(policy_file(firm), unit=unit, b0_x=b0.x_grid, b0_d=b0.d_grid, b0_risk=b0.risk, b1_x=b1.x_grid,
                        b1_d=b1.d_grid, b1_risk=b1.risk, h_x=h.x_grid, h_risk=h.risk)
    p = Policy.load(policy_file(firm))
    print(f"politica salva em {policy_file(firm)} ({len(ins)} dias antes de 2019, desvio diario da carteira {100 * unit:.3f}%)")
    print("orcamento de volatilidade diaria da conta (%), por resultado da fase:")
    for x in (-0.08, -0.05, -0.02, 0.0, 0.02, 0.04, 0.06):
        print(f"  resultado {100 * x:+.0f}%: Fase 1 {100 * p.budget(0, x, 0):.2f}  Fase 2 {100 * p.budget(1, x, 0):.2f}  "
              f"financiada {100 * p.budget(2, min(x, 0.04), 0):.2f}")


# ---- MetaTrader side ----------------------------------------------------------------------------------
class Terminal:
    def __init__(self) -> None:
        import MetaTrader5 as mt5
        self.mt5 = mt5
        if not mt5.initialize():
            raise SystemExit(f"nao consegui falar com o MetaTrader 5 (abra o terminal e entre na conta): {mt5.last_error()}")
        self.acc = mt5.account_info()
        if self.acc is None:
            raise SystemExit("o terminal esta aberto mas sem conta conectada")

    def is_demo(self) -> bool:
        return self.acc.trade_mode == self.mt5.ACCOUNT_TRADE_MODE_DEMO

    def equity(self) -> float:
        return float(self.mt5.account_info().equity)

    def bars(self, sym: str, n: int = 700) -> pd.DataFrame:
        self.mt5.symbol_select(sym, True)
        r = self.mt5.copy_rates_from_pos(sym, self.mt5.TIMEFRAME_D1, 0, n)
        if r is None or len(r) < SLOW:
            return pd.DataFrame(columns=["close"])
        df = pd.DataFrame(r)
        df.index = pd.to_datetime(df.pop("time"), unit="s")
        return df.iloc[:-1]                                   # the last bar is still forming

    def held(self, sym: str) -> tuple[float, list]:
        pos = [p for p in (self.mt5.positions_get(symbol=sym) or []) if p.magic == MAGIC]
        return sum(p.volume if p.type == 0 else -p.volume for p in pos), pos

    def _send(self, sym: str, buy: bool, lots: float, sl: float = 0.0, position: int | None = None) -> str:
        mt5 = self.mt5
        info, tick = mt5.symbol_info(sym), mt5.symbol_info_tick(sym)
        fill = mt5.ORDER_FILLING_FOK if info.filling_mode & 1 else (mt5.ORDER_FILLING_IOC if info.filling_mode & 2 else mt5.ORDER_FILLING_RETURN)
        req = {"action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": float(lots), "magic": MAGIC, "deviation": 30,
               "type": mt5.ORDER_TYPE_BUY if buy else mt5.ORDER_TYPE_SELL, "price": tick.ask if buy else tick.bid,
               "type_filling": fill, "type_time": mt5.ORDER_TIME_GTC, "comment": "kenui-trend"}
        if sl > 0:
            req["sl"] = round(sl, info.digits)
        if position is not None:
            req["position"] = position
        res = mt5.order_send(req)
        if res is None:
            return f"ERRO {mt5.last_error()}"
        return "ok" if res.retcode == mt5.TRADE_RETCODE_DONE else f"ERRO {res.retcode} {res.comment}"

    def buy(self, sym: str, lots: float, sl: float) -> str:
        return self._send(sym, True, lots, sl)

    def reduce(self, sym: str, lots: float) -> str:
        """Closes `lots` of this robot's long positions, oldest first."""
        step = self.mt5.symbol_info(sym).volume_step
        out = "ok"
        for p in sorted(self.held(sym)[1], key=lambda p: p.time):
            if lots < step / 2:
                break
            cut = min(p.volume, lots)
            out = self._send(sym, p.type != 0, round(cut, 8), position=p.ticket)
            lots -= cut
        return out

    def flatten(self) -> None:
        for sym in SYMBOLS:
            cur, _ = self.held(sym)
            if cur:
                print(f"  fechando {sym} {abs(cur):.2f} lote: {self.reduce(sym, abs(cur))}")


def run_once(t: Terminal, st: State, rules: dict, pol: Policy, live: bool) -> None:
    now = datetime.now(timezone.utc)
    equity = t.equity()
    s = account_step(st, rules, equity, now) if live else {"phase": st.get("phase", 0), "x": 0.0, "day": 0.0, "locked": False, "flatten": False}
    budget = 0.0 if s["locked"] else pol.budget(s["phase"], s["x"], s["day"])
    print(f"{now:%Y-%m-%d %H:%M} UTC  saldo liquido {equity:.2f}  fase {['1', '2', 'financiada'][s['phase']]}  "
          f"resultado da fase {100 * s['x']:+.2f}%  dia {100 * s['day']:+.2f}%  orcamento de volatilidade {100 * budget:.2f}%/dia", flush=True)
    if s["flatten"]:
        t.flatten()
        return
    if live and (st.get("rebalanced") == st.get("day") or in_rollover(now)):
        return                                                # one rebalance per day, never in the rollover
    done = True
    for sym in SYMBOLS:
        d, info, tick = t.bars(sym), t.mt5.symbol_info(sym), t.mt5.symbol_info_tick(sym)
        if info is None or tick is None or d.empty or tick.ask <= 0:
            print(f"  {sym}: sem dados neste servidor")
            continue
        w = weight(d)
        tgt = target_lots(w, budget, pol.unit, len(SYMBOLS), equity, tick.ask, info.trade_contract_size, info.volume_step,
                          info.volume_min, info.volume_max)
        cur, _ = t.held(sym)
        spread_ok = info.spread <= 3 * max(1.0, float(d["spread"].iloc[-60:].median()))
        line = f"  {sym}: tendencia {'de alta' if w > 0 else 'ausente'}, alvo {tgt:.2f} lote, na conta {cur:.2f}"
        if not needs_trade(cur, tgt, info.volume_step):
            print(line + ", nada a fazer")
            continue
        if not live:
            print(line + f", ordem que seria enviada: {'comprar' if tgt > cur else 'vender'} {abs(tgt - cur):.2f}")
            continue
        if info.trade_mode != t.mt5.SYMBOL_TRADE_MODE_FULL or not spread_ok:
            print(line + (", spread anormal, tento de novo depois" if not spread_ok else ", negociacao fechada neste simbolo"))
            done = done and spread_ok
            continue
        if tgt > cur:
            res = t.buy(sym, round(tgt - cur, 8), tick.bid * (1 - STOP_SIGMAS * daily_vol(d)))
        else:
            res = t.reduce(sym, round(cur - tgt, 8))
        print(line + f", {'compra' if tgt > cur else 'venda'} de {abs(tgt - cur):.2f}: {res}")
        st.log(f"{sym} {'compra' if tgt > cur else 'venda'} {abs(tgt - cur):.2f}: {res}")
        done = done and res == "ok"
    if live and done:
        st.set(rebalanced=st.get("day"))


def main() -> None:
    ap = argparse.ArgumentParser(description="Robo de tendencia em ouro e prata para MetaTrader 5")
    ap.add_argument("--mesa", default="padrao", help="padrao, ftmo, the5ers ou fundednext")
    ap.add_argument("--solve", metavar="PASTA", help="monta a politica de tamanho com o historico antes de 2019")
    ap.add_argument("--live", action="store_true", help="envia ordens (sem isto so mostra o plano)")
    ap.add_argument("--conta-real", action="store_true", help="permite conta que nao e demo")
    ap.add_argument("--loop", action="store_true", help="continua rodando (freio a cada 30 s)")
    ap.add_argument("--flatten", action="store_true", help="fecha tudo deste robo")
    ap.add_argument("--reset", action="store_true", help="recomeca a Fase 1 a partir do saldo atual")
    a = ap.parse_args()
    if a.solve:
        return solve(Path(a.solve), a.mesa)
    rules, pol, t = load_rules(a.mesa), Policy.load(policy_file(a.mesa)), Terminal()
    print(f"{rules['nome']} | conta {'DEMO' if t.is_demo() else 'REAL'} em {t.acc.server} | "
          f"politica {'do historico' if pol.tables else 'fixa (rode --solve)'} | {'ORDENS LIGADAS' if a.live else 'so plano, nenhuma ordem'}")
    if a.live and not t.is_demo() and not a.conta_real:
        raise SystemExit("esta conta nao e demo. Nao envio ordens sem --conta-real.")
    st = State()
    if a.reset:
        st.set(phase=0, phase_start=t.equity(), rebalanced=None)
    if a.flatten:
        return t.flatten() if a.live else print("use --live --flatten para fechar de verdade")
    while True:
        run_once(t, st, rules, pol, a.live)
        if not (a.loop and a.live):
            break
        time.sleep(30)


if __name__ == "__main__":
    main()
