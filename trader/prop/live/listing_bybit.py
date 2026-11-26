"""Listing short on Bybit (the venue crypto prop firms such as Crypto Fund Trader use).

Rule, unchanged from the backtest: 24 hours after Binance lists a new USDT spot pair, short the
coin's USDT perpetual on Bybit, stop 30% above the entry (kept on Bybit's server), close after
7 days. Size comes from the account state (Phase 1, Phase 2, funded) through the Bellman policy.

Safety:
  - without --live nothing is sent, the bot only prints what it would do;
  - by default it talks to Bybit DEMO trading (api-demo.bybit.com); the real API needs --conta-real;
  - the API key is read from the environment (BYBIT_API_KEY, BYBIT_API_SECRET), never from a file
    in the repository; create it WITHOUT withdrawal permission;
  - at 60% of the firm's daily loss limit everything is closed and the day is locked.

    python -m prop.live.listing_bybit                    plan only
    python -m prop.live.listing_bybit --live --loop      demo account, runs forever (checks every 5 minutes)
    python -m prop.live.listing_bybit --report
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from prop.live.mt5_trend import BREAKER, State, account_step, load_rules

DEMO, REAL = "https://api-demo.bybit.com", "https://api.bybit.com"
BINANCE = "https://api.binance.com"
WAIT_H, HOLD_H, STOP = 24, 7 * 24, 0.30
ENTRY_GRACE_H = 6
MAX_OPEN_RISK = 0.04
DB = Path("data/listing_bybit.db")
SKIP = ("UP", "DOWN", "BULL", "BEAR")
STABLE = {"USDC", "FDUSD", "TUSD", "USDP", "DAI", "EUR", "USD1", "RLUSD", "AEUR", "EURI", "XUSD", "BFUSD", "USDE", "PYUSD", "U"}


def eligible(symbol: str) -> bool:
    base = symbol[:-4]
    return symbol.endswith("USDT") and base not in STABLE and not any(base.endswith(k) for k in SKIP)


def _http(req: urllib.request.Request) -> dict:
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def binance_spot_symbols() -> set[str]:
    info = _http(urllib.request.Request(f"{BINANCE}/api/v3/exchangeInfo?permissions=SPOT"))
    return {s["symbol"] for s in info["symbols"] if s["status"] == "TRADING" and s["quoteAsset"] == "USDT"}


class Bybit:
    """The few v5 calls the bot needs. Private calls are signed with HMAC-SHA256."""

    def __init__(self, base: str = DEMO, key: str | None = None, secret: str | None = None) -> None:
        self.base, self.key, self.secret = base, key or os.environ.get("BYBIT_API_KEY", ""), secret or os.environ.get("BYBIT_API_SECRET", "")

    def has_key(self) -> bool:
        return bool(self.key and self.secret)

    def _call(self, method: str, path: str, params: dict, private: bool) -> dict:
        query = urllib.parse.urlencode(params) if method == "GET" else ""
        body = json.dumps(params, separators=(",", ":")) if method == "POST" else ""
        headers = {"User-Agent": "kenui-listing", "Content-Type": "application/json"}
        if private:
            ts, window = str(int(time.time() * 1000)), "5000"
            sig = hmac.new(self.secret.encode(), (ts + self.key + window + (query or body)).encode(), hashlib.sha256).hexdigest()
            headers.update({"X-BAPI-API-KEY": self.key, "X-BAPI-TIMESTAMP": ts, "X-BAPI-RECV-WINDOW": window, "X-BAPI-SIGN": sig})
        url = f"{self.base if private else REAL}{path}" + (f"?{query}" if query else "")   # market data lives on the main host
        out = _http(urllib.request.Request(url, data=body.encode() if body else None, headers=headers, method=method))
        if out.get("retCode") != 0:
            raise RuntimeError(f"Bybit {path}: {out.get('retCode')} {out.get('retMsg')}")
        return out["result"]

    # public
    def instrument(self, symbol: str) -> dict | None:
        """Lot rules of the coin's USDT perpetual, trying the 1000x names too."""
        base = symbol.removesuffix("USDT")
        for name in (symbol, f"1000{base}USDT", f"10000{base}USDT", f"1000000{base}USDT"):
            try:
                rows = self._call("GET", "/v5/market/instruments-info", {"category": "linear", "symbol": name}, False).get("list", [])
            except RuntimeError:
                rows = []
            if rows and rows[0].get("status") == "Trading":
                lot = rows[0]["lotSizeFilter"]
                return {"symbol": name, "step": float(lot["qtyStep"]), "min": float(lot["minOrderQty"]),
                        "max": float(lot.get("maxMktOrderQty") or lot["maxOrderQty"]), "tick": float(rows[0]["priceFilter"]["tickSize"])}
        return None

    def price(self, symbol: str) -> float:
        return float(self._call("GET", "/v5/market/tickers", {"category": "linear", "symbol": symbol}, False)["list"][0]["lastPrice"])

    # private
    def equity(self) -> float:
        return float(self._call("GET", "/v5/account/wallet-balance", {"accountType": "UNIFIED"}, True)["list"][0]["totalEquity"])

    def positions(self) -> dict[str, float]:
        """symbol -> signed size (negative = short)."""
        rows = self._call("GET", "/v5/position/list", {"category": "linear", "settleCoin": "USDT"}, True).get("list", [])
        return {r["symbol"]: (-1 if r["side"] == "Sell" else 1) * float(r["size"]) for r in rows if float(r["size"]) > 0}

    def set_leverage(self, symbol: str, lev: int = 3) -> None:
        try:
            self._call("POST", "/v5/position/set-leverage", {"category": "linear", "symbol": symbol, "buyLeverage": str(lev), "sellLeverage": str(lev)}, True)
        except RuntimeError as err:                    # "leverage not modified" is fine
            if "110043" not in str(err):
                raise

    def short(self, symbol: str, qty: float, stop: float) -> str:
        return self._call("POST", "/v5/order/create", {"category": "linear", "symbol": symbol, "side": "Sell", "orderType": "Market",
                                                       "qty": f"{qty:.10g}", "stopLoss": f"{stop:.10g}", "slTriggerBy": "LastPrice",
                                                       "positionIdx": 0}, True)["orderId"]

    def cover(self, symbol: str, qty: float) -> str:
        return self._call("POST", "/v5/order/create", {"category": "linear", "symbol": symbol, "side": "Buy", "orderType": "Market",
                                                       "qty": f"{qty:.10g}", "reduceOnly": True, "positionIdx": 0}, True)["orderId"]


def order_qty(equity: float, risk: float, price: float, inst: dict) -> float:
    """Coins to short so that the 30% stop costs `risk` of the account."""
    qty = equity * risk / STOP / price
    qty = np.floor(qty / inst["step"] + 1e-9) * inst["step"]
    return 0.0 if qty < inst["min"] else float(min(round(qty, 10), inst["max"]))


def round_up(price: float, tick: float) -> float:
    return float(round(np.ceil(price / tick - 1e-9) * tick, 12))


class ListingBybit:
    def __init__(self, st: State, api: Bybit, rules: dict, barrier, harvest, live: bool, paper_equity: float = 10_000.0,
                 spot_symbols=binance_spot_symbols) -> None:
        self.st, self.api, self.rules, self.barrier, self.harvest, self.live = st, api, rules, barrier, harvest, live
        self.paper_equity, self.spot_symbols = paper_equity, spot_symbols

    def risk(self, s: dict, open_risk: float) -> float:
        if s["locked"]:
            return 0.0
        x, d = np.array([s["x"]]), np.array([s["day"]])
        f = float(self.harvest.lookup(x)[0]) if s["phase"] == 2 else float(self.barrier[s["phase"]].lookup(x, d)[0])
        room = BREAKER * self.rules["perda_diaria"] + s["day"]
        return float(max(0.0, min(f, room, MAX_OPEN_RISK - open_risk)))

    def step(self, now: datetime) -> list[str]:
        """One cycle. Returns what happened, in plain words."""
        out: list[str] = []
        say = lambda msg: (out.append(msg), self.st.log(msg) if self.live else print(f"  {msg}"))        # noqa: E731
        equity = self.api.equity() if self.api.has_key() else self.paper_equity
        s = account_step(self.st, self.rules, equity, now) if self.live else {"phase": self.st.get("phase", 0), "x": 0.0, "day": 0.0, "locked": False, "flatten": False}
        opened: list[dict] = self.st.get("open", [])
        held = self.api.positions() if self.api.has_key() else {}

        # new listings on Binance spot
        current, known = self.spot_symbols(), self.st.get("known")
        pending: dict[str, str] = self.st.get("pending", {})
        if known is None:
            say(f"primeira execucao: {len(current)} pares conhecidos; a contagem comeca na proxima listagem")
        else:
            for sym in sorted(current - set(known)):
                if eligible(sym):
                    pending[sym] = now.isoformat()
                    say(f"NOVA LISTAGEM {sym}: short em 24 horas se a Bybit tiver o contrato")
        known = sorted(set(known or []) | current)

        # positions: stopped on the server, 7 days over, or circuit breaker
        still = []
        for p in opened:
            age_h = (now - datetime.fromisoformat(p["entry_time"])).total_seconds() / 3600
            if self.live and abs(held.get(p["perp"], 0.0)) < p["qty"] * 0.5:
                say(f"{p['perp']} saiu no stop (ou foi fechada na Bybit)")
            elif age_h >= HOLD_H or s["flatten"]:
                why = "7 dias" if age_h >= HOLD_H else "freio do dia ou mudanca de fase"
                res = self.api.cover(p["perp"], p["qty"]) if self.live else "plano"
                say(f"FECHA {p['perp']} {p['qty']:g} ({why}): {res}")
            else:
                still.append(p)
        opened = still

        # entries that are due
        for sym, t in list(pending.items()):
            late_h = (now - datetime.fromisoformat(t)).total_seconds() / 3600 - WAIT_H
            if late_h < 0:
                continue
            del pending[sym]
            inst = self.api.instrument(sym)
            r = self.risk(s, sum(p["risk"] for p in opened))
            price = self.api.price(inst["symbol"]) if inst else 0.0
            qty = order_qty(equity, r, price, inst) if inst and r > 0 else 0.0
            why = ("a Bybit nao tem o contrato" if inst is None else "o robo estava desligado na hora da entrada" if late_h > ENTRY_GRACE_H else
                   "trava de risco do dia ou risco aberto no limite" if r <= 0 else "tamanho abaixo do minimo da Bybit" if qty <= 0 else
                   "ja existe posicao nessa moeda" if inst["symbol"] in held else None)
            if why:
                say(f"{sym} ignorada: {why}")
                continue
            stop = round_up(price * (1 + STOP), inst["tick"])
            if self.live:
                self.api.set_leverage(inst["symbol"])
                res = self.api.short(inst["symbol"], qty, stop)
                opened.append({"symbol": sym, "perp": inst["symbol"], "entry_time": now.isoformat(), "entry": price, "qty": qty,
                               "risk": r, "phase": s["phase"]})
            else:
                res = "plano"
            say(f"SHORT {inst['symbol']} {qty:g} a {price:g}, stop {stop:g}, risco {100 * r:.2f}% da conta: {res}")
        self.st.set(known=known, pending=pending, open=opened)
        return out


def report(st: State) -> str:
    rows = st.db.execute("SELECT t, event FROM log ORDER BY rowid DESC LIMIT 40").fetchall()
    head = (f"fase {['1', '2', 'financiada'][st.get('phase', 0)]} | abertas: {[p['perp'] for p in st.get('open', [])]} | "
            f"aguardando 24h: {list(st.get('pending', {}))} | reprovacoes: {st.get('failed', 0)} | saques simulados: US$ {st.get('payouts', 0.0):.0f}")
    return "\n".join([head] + [f"  {t[:16]} {e}" for t, e in reversed(rows)])


def main() -> None:
    ap = argparse.ArgumentParser(description="Short de listagens na Bybit, nas regras da mesa")
    ap.add_argument("--mesa", default="cryptofundtrader")
    ap.add_argument("--live", action="store_true", help="envia ordens (sem isto so mostra o plano)")
    ap.add_argument("--conta-real", action="store_true", help="usa a API real em vez da demo")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--every", type=int, default=300)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--check", action="store_true", help="testa as conexoes e sai, sem enviar nada")
    a = ap.parse_args()
    st = State(DB)
    if a.report:
        return print(report(st))
    from prop.live.listing_paper import policies
    barrier, harvest = policies()
    api = Bybit(REAL if a.conta_real else DEMO)
    if a.live and not api.has_key():
        raise SystemExit("faltam as variaveis BYBIT_API_KEY e BYBIT_API_SECRET (chave da conta DEMO, sem permissao de saque)")
    rules = load_rules(a.mesa)
    if a.check:
        print(f"Binance: {len(binance_spot_symbols())} pares USDT em negociacao")
        inst = api.instrument("BTCUSDT")
        print(f"Bybit, dados publicos: BTCUSDT {inst} preco {api.price('BTCUSDT')}")
        print(f"Bybit {'REAL' if a.conta_real else 'DEMO'}, chave: " + (f"ok, patrimonio US$ {api.equity():.2f}, posicoes {api.positions()}"
                                                                        if api.has_key() else "nao configurada (BYBIT_API_KEY / BYBIT_API_SECRET)"))
        return
    print(f"{rules['nome']} | Bybit {'REAL' if a.conta_real else 'DEMO'} | {'ORDENS LIGADAS' if a.live else 'so plano, nenhuma ordem'}")
    bot = ListingBybit(st, api, rules, barrier, harvest, a.live)
    while True:
        try:
            now = datetime.now(timezone.utc)
            bot.step(now)
            print(f"{now:%Y-%m-%d %H:%M} UTC ciclo ok: {len(st.get('pending', {}))} aguardando, {len(st.get('open', []))} abertas", flush=True)
        except Exception as err:                       # noqa: BLE001  a failed cycle must not stop the bot
            print(f"ciclo falhou ({err}); tenta de novo no proximo", flush=True)
        if not (a.loop and a.live):
            break
        time.sleep(a.every)


if __name__ == "__main__":
    main()
