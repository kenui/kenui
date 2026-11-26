"""Bridge between the Python brain and the MetaTrader 5 executor (mql5/PropGuardV5_Executor.mq5).

MetaTrader 5 only runs on Windows. The EA connects as a TCP client to this server on
127.0.0.1 (same machine, or a Linux/WSL brain reached through a local port forward) and the two
sides exchange one JSON object per line. Orders carry an HMAC-SHA256 signature made with a
shared secret, so the EA ignores anything that did not come from this process. If the socket
is down, orders fall back to an atomically written file in the terminal's Common\\Files folder.

Python sends:  {"type":"order","id","symbol","side","risk_pct","sl","tp","partial_r","arm","sig"}
EA sends:      {"type":"hello"} | {"type":"tick","equity","balance","spread_pts":{...}}
               {"type":"closed","id","result_r","mae_r"} | {"type":"guard","reason"}

The risk gates run on both sides: the EA has its own tick-by-tick daily kill, spread cap and
rollover block, so a dead Python process can never leave the account unprotected.
No "micro-jitter" is added to prices: the strategy is the trader's own, and disguising
executions is exactly what prop firms' duplicate-trade rules are written against.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import socket
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from prop.config.quant import Q
from prop.execution.contextual_bandit import LinUCB
from prop.persistence.state_store import StateStore


def canonical(payload: dict) -> str:
    return json.dumps({k: payload[k] for k in sorted(payload) if k != "sig"}, separators=(",", ":"))


def sign(payload: dict, secret: str) -> str:
    return hmac.new(secret.encode(), canonical(payload).encode(), hashlib.sha256).hexdigest()


def signed_line(payload: dict, secret: str) -> bytes:
    """Canonical JSON with the signature appended as the last field: the EA removes
    `,"sig":"..."` and verifies the HMAC of exactly what is left."""
    body = canonical(payload)
    return (body[:-1] + ',"sig":"' + sign(payload, secret) + '"}\n').encode()


def in_rollover(now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    h = now.hour + now.minute / 60
    return Q.rollover_block[0] <= h < Q.rollover_block[1]


class Mt5SocketBridge:
    def __init__(self, store: StateStore, secret: str, host: str = "127.0.0.1", port: int = 18777,
                 fallback_dir: Path | None = None, max_spread_pts: dict[str, float] | None = None,
                 calendar_hook: Callable[[datetime], bool] | None = None) -> None:
        """`calendar_hook(now) -> True` blocks entries (plug an economic-calendar feed here)."""
        self.store, self.secret, self.addr = store, secret, (host, port)
        self.fallback_dir = fallback_dir
        self.max_spread_pts = max_spread_pts or {}
        self.calendar_hook = calendar_hook
        self.equity = self.balance = float("nan")
        self.spread_pts: dict[str, float] = {}
        self.conn: socket.socket | None = None
        self.lock = threading.Lock()
        self.on_close: list[Callable[[dict, dict], None]] = []
        self.learners: dict = {}          # {"ensemble": ..., "bandit": ..., "cusum": ...}
        self._server: socket.socket | None = None

    # connection ----------------------------------------------------------------
    def serve(self) -> None:
        """Accept the EA and read its messages until the process stops."""
        self._server = socket.create_server(self.addr)
        while True:
            conn, _ = self._server.accept()
            conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            with self.lock:
                self.conn = conn
            try:
                self._read_loop(conn)
            finally:
                with self.lock:
                    self.conn = None
                conn.close()

    def start(self) -> threading.Thread:
        th = threading.Thread(target=self.serve, daemon=True, name="mt5-bridge")
        th.start()
        return th

    def connected(self) -> bool:
        return self.conn is not None

    def _read_loop(self, conn: socket.socket) -> None:
        buf = b""
        while chunk := conn.recv(65536):
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if line.strip():
                    self.handle(json.loads(line))

    # inbound -------------------------------------------------------------------
    def handle(self, msg: dict) -> None:
        kind = msg.get("type")
        if kind == "tick":
            self.equity, self.balance = float(msg["equity"]), float(msg["balance"])
            self.spread_pts.update(msg.get("spread_pts", {}))
            day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            self.store.mark_equity(day, self.equity)
        elif kind == "closed":
            self._on_closed(msg)
        elif kind == "guard":
            self.store.lock_day(datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    def _on_closed(self, msg: dict) -> None:
        """A position was closed in MetaTrader: update every online learner and persist
        their state together with the trade result, in one transaction."""
        trade = self.store.get_trade(msg["id"])
        if trade is None:
            return
        result_r, mae_r = float(msg["result_r"]), float(msg.get("mae_r", 0.0))
        outcome = int(result_r > 0 and mae_r >= -Q.mae_limit)
        saved: dict = {}
        ens, bandit, cusum = (self.learners.get(k) for k in ("ensemble", "bandit", "cusum"))
        if ens is not None:
            ens.notify_trade_outcome(trade["p_hat"], outcome)
            saved["aci"] = ens.aci.to_dict()
        if bandit is not None and trade["arm"] >= 1:
            import numpy as np
            bandit.update(trade["arm"] - 1, np.array(trade["context"], float), LinUCB.reward(result_r, mae_r))
            saved["linucb"] = bandit.state()
        if cusum is not None:
            cusum.update(trade["p_hat"], outcome)
            saved["cusum"] = cusum.state()
        self.store.close_trade(msg["id"], result_r, mae_r, outcome, saved)
        for fn in self.on_close:
            fn(trade, msg)

    # outbound ------------------------------------------------------------------
    def entry_blocked(self, symbol: str, now: datetime | None = None) -> str | None:
        """Reason why no order may be sent right now, or None."""
        now = now or datetime.now(timezone.utc)
        if in_rollover(now):
            return "rollover"
        if self.calendar_hook is not None and self.calendar_hook(now):
            return "news"
        cap = self.max_spread_pts.get(symbol)
        if cap is not None and self.spread_pts.get(symbol, 0.0) > cap:
            return "spread"
        day = self.store.mark_equity(now.strftime("%Y-%m-%d"), self.equity) if self.equity == self.equity else None
        if day and (day["locked"] or self.equity <= day["start"] * (1 - Q.hard_daily_kill)):
            return "daily_kill"
        return None

    def send_order(self, symbol: str, side: int, risk_pct: float, sl: float, tp: float, p_hat: float,
                   arm: int, context: list[float], partial_r: float = 0.8) -> str | None:
        """Returns the order id, or None when a gate blocked it. The EA sizes the lot itself
        from `risk_pct` of the balance and the stop distance, with the broker's tick value."""
        if self.entry_blocked(symbol):
            return None
        oid = uuid.uuid4().hex[:16]
        msg = {"type": "order", "id": oid, "symbol": symbol, "side": side, "risk_pct": round(risk_pct * 100, 4),
               "sl": sl, "tp": tp, "partial_r": partial_r, "arm": arm}
        self.store.open_trade(oid, symbol, side, risk_pct, p_hat, arm, context)
        line = signed_line(msg, self.secret)
        with self.lock:
            if self.conn is not None:
                try:
                    self.conn.sendall(line)
                    return oid
                except OSError:
                    self.conn = None
        if self.fallback_dir is None:
            return None
        tmp = self.fallback_dir / f".{oid}.tmp"
        tmp.write_bytes(line)
        os.replace(tmp, self.fallback_dir / f"propguard_order_{oid}.json")   # atomic on the same volume
        return oid
