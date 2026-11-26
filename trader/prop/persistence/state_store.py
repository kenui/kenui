"""Transactional state for production: SQLite in WAL mode.

Everything the robot must remember across restarts is written atomically: the daily equity
high-water mark, the account phase, and the online learners (ACI, LinUCB bandit, CUSUM).
A crash in the middle of a save leaves the previous state intact.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from prop.config.quant import Q

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS equity_day (day TEXT PRIMARY KEY, start_equity REAL NOT NULL,
                                       high_watermark REAL NOT NULL, low_watermark REAL NOT NULL,
                                       locked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS trade_log (id TEXT PRIMARY KEY, opened_at TEXT, closed_at TEXT, symbol TEXT,
                                      side INTEGER, risk REAL, p_hat REAL, arm INTEGER, context TEXT,
                                      result_r REAL, mae_r REAL, outcome INTEGER);
"""


class StateStore:
    def __init__(self, path: Path = Q.state_db) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, isolation_level=None, timeout=10)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript(SCHEMA)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield self.db
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        self.db.execute("COMMIT")

    # key/value -----------------------------------------------------------------
    def save_many(self, items: dict[str, Any]) -> None:
        """All keys or none."""
        now = datetime.now(timezone.utc).isoformat()
        with self.transaction() as db:
            db.executemany("INSERT INTO kv(key, value, updated_at) VALUES(?,?,?) "
                           "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                           [(k, json.dumps(v), now) for k, v in items.items()])

    def load(self, key: str, default: Any = None) -> Any:
        row = self.db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    # online learners -----------------------------------------------------------
    def save_learners(self, aci=None, bandit=None, cusum=None, account: dict | None = None) -> None:
        items: dict[str, Any] = {}
        if aci is not None:
            items["aci"] = aci.to_dict()
        if bandit is not None:
            items["linucb"] = bandit.state()
        if cusum is not None:
            items["cusum"] = cusum.state()
        if account is not None:
            items["account"] = account
        if items:
            self.save_many(items)

    def restore_learners(self, aci_cls=None, bandit=None, cusum=None):
        """Returns (aci, bandit, cusum) with the saved state applied where it exists."""
        aci = None
        if aci_cls is not None:
            saved = self.load("aci")
            aci = aci_cls.from_dict(saved) if saved else aci_cls()
        if bandit is not None and (saved := self.load("linucb")):
            bandit.load(saved)
        if cusum is not None and (saved := self.load("cusum")):
            cusum.load(saved)
        return aci, bandit, cusum

    # daily equity --------------------------------------------------------------
    def mark_equity(self, day: str, equity: float) -> dict:
        """Update the day's watermarks; the first call of a day fixes its starting equity."""
        with self.transaction() as db:
            db.execute("INSERT OR IGNORE INTO equity_day(day, start_equity, high_watermark, low_watermark) "
                       "VALUES(?,?,?,?)", (day, equity, equity, equity))
            db.execute("UPDATE equity_day SET high_watermark=MAX(high_watermark, ?), "
                       "low_watermark=MIN(low_watermark, ?) WHERE day=?", (equity, equity, day))
        row = self.db.execute("SELECT start_equity, high_watermark, low_watermark, locked FROM equity_day "
                              "WHERE day=?", (day,)).fetchone()
        return {"start": row[0], "high": row[1], "low": row[2], "locked": bool(row[3])}

    def lock_day(self, day: str) -> None:
        with self.transaction() as db:
            db.execute("UPDATE equity_day SET locked=1 WHERE day=?", (day,))

    # trades --------------------------------------------------------------------
    def open_trade(self, trade_id: str, symbol: str, side: int, risk: float, p_hat: float, arm: int,
                   context: list[float]) -> None:
        with self.transaction() as db:
            db.execute("INSERT OR REPLACE INTO trade_log(id, opened_at, symbol, side, risk, p_hat, arm, context) "
                       "VALUES(?,?,?,?,?,?,?,?)", (trade_id, datetime.now(timezone.utc).isoformat(), symbol, side,
                                                   risk, p_hat, arm, json.dumps(context)))

    def get_trade(self, trade_id: str) -> dict | None:
        cur = self.db.execute("SELECT id, symbol, side, risk, p_hat, arm, context FROM trade_log WHERE id=?", (trade_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {"id": row[0], "symbol": row[1], "side": row[2], "risk": row[3], "p_hat": row[4], "arm": row[5],
                "context": json.loads(row[6])}

    def close_trade(self, trade_id: str, result_r: float, mae_r: float, outcome: int,
                    learners: dict[str, Any]) -> None:
        """Trade result and the updated learner states are committed together."""
        now = datetime.now(timezone.utc).isoformat()
        with self.transaction() as db:
            db.execute("UPDATE trade_log SET closed_at=?, result_r=?, mae_r=?, outcome=? WHERE id=?",
                       (now, result_r, mae_r, outcome, trade_id))
            db.executemany("INSERT INTO kv(key, value, updated_at) VALUES(?,?,?) "
                           "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                           [(k, json.dumps(v), now) for k, v in learners.items()])

    def close(self) -> None:
        self.db.close()
