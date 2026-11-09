"""Auditoría SQLite del proyecto (RF-REP-02/03/04). Propiedad de la aplicación, no del framework."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS run (
    run_id TEXT PRIMARY KEY,
    started_ms INTEGER,
    config_fingerprint TEXT,
    config_json TEXT,
    strategy_variant TEXT,
    strategy_params_json TEXT,
    budget_usdt TEXT,
    instrument TEXT,
    bar_type TEXT,
    software_versions_json TEXT,
    git_commit TEXT
);
CREATE TABLE IF NOT EXISTS state_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_ms INTEGER, from_state TEXT, to_state TEXT, reason TEXT
);
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_ms INTEGER, bar_close_ms INTEGER, bar_close_price REAL,
    target_position INTEGER, prev_state INTEGER, action TEXT, reason TEXT,
    cci REAL, sma_fast REAL, sma_slow REAL, vol_z REAL,
    entry_event INTEGER, exit_event INTEGER,
    executed TEXT, block_reason TEXT
);
CREATE TABLE IF NOT EXISTS order_intents (
    key TEXT PRIMARY KEY,
    ts_ms INTEGER, symbol TEXT, side TEXT, quantity TEXT, quote_estimate TEXT,
    bar_close_ms INTEGER, action TEXT, status TEXT,
    order_id INTEGER, client_order_id TEXT, message TEXT
);
CREATE TABLE IF NOT EXISTS orders (
    client_order_id TEXT PRIMARY KEY,
    order_id INTEGER, ts_ms INTEGER, symbol TEXT, side TEXT, order_type TEXT,
    quantity TEXT, status TEXT, filled_qty TEXT, avg_price TEXT, raw_json TEXT
);
CREATE TABLE IF NOT EXISTS order_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_ms INTEGER, client_order_id TEXT, event TEXT, detail_json TEXT
);
CREATE TABLE IF NOT EXISTS fills (
    symbol TEXT, trade_id INTEGER,
    order_id INTEGER, client_order_id TEXT, ts_ms INTEGER, side TEXT,
    price TEXT, qty TEXT, quote_qty TEXT, commission TEXT, commission_asset TEXT,
    is_maker INTEGER, source TEXT,
    PRIMARY KEY (symbol, trade_id)
);
CREATE TABLE IF NOT EXISTS balances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_ms INTEGER, asset TEXT, free TEXT, locked TEXT, source TEXT
);
CREATE TABLE IF NOT EXISTS equity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_ms INTEGER, budget TEXT, cash_free TEXT, cash_reserved TEXT,
    base_qty TEXT, base_price TEXT, inventory_value TEXT, pending_costs TEXT,
    equity TEXT, complete INTEGER, notes_json TEXT, source TEXT
);
CREATE TABLE IF NOT EXISTS health (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_ms INTEGER, status TEXT, reasons_json TEXT
);
CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_ms INTEGER, kind TEXT, detail_json TEXT, resolved_ms INTEGER
);
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT, entry_ts_ms INTEGER, exit_ts_ms INTEGER,
    entry_qty TEXT, entry_avg_px TEXT, exit_avg_px TEXT,
    pnl TEXT, fees_json TEXT, closed INTEGER, duration_s REAL, exposure_s REAL
);
CREATE TABLE IF NOT EXISTS exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_ms INTEGER, export_id TEXT, files_json TEXT
);
"""


class AuditDB:
    """Escritor único (con lock) sobre SQLite en WAL. Nunca lanza por datos opcionales."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------------ escritura
    def record_run(self, info: dict[str, Any]) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO run (run_id, started_ms, config_fingerprint, config_json,
                   strategy_variant, strategy_params_json, budget_usdt, instrument, bar_type,
                   software_versions_json, git_commit)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    info.get("run_id"),
                    info.get("started_ms"),
                    info.get("config_fingerprint"),
                    json.dumps(info.get("config_json"), default=str),
                    info.get("strategy_variant"),
                    json.dumps(info.get("strategy_params_json"), default=str),
                    info.get("budget_usdt"),
                    info.get("instrument"),
                    info.get("bar_type"),
                    json.dumps(info.get("software_versions_json"), default=str),
                    info.get("git_commit"),
                ),
            )
            self._conn.commit()

    def record_state(self, ts_ms: int, from_state: str, to_state: str, reason: str) -> None:
        self._exec(
            "INSERT INTO state_history (ts_ms, from_state, to_state, reason) VALUES (?,?,?,?)",
            (ts_ms, from_state, to_state, reason),
        )

    def record_signal(self, ts_ms: int, decision: dict[str, Any], executed: str, block_reason: str | None) -> None:
        self._exec(
            """INSERT INTO signals (ts_ms, bar_close_ms, bar_close_price, target_position, prev_state,
               action, reason, cci, sma_fast, sma_slow, vol_z, entry_event, exit_event, executed, block_reason)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ts_ms, decision.get("bar_close_ms"), decision.get("bar_close_price"),
                decision.get("target_position"), decision.get("prev_state"),
                decision.get("action"), decision.get("reason"),
                decision.get("cci"), decision.get("sma_fast"), decision.get("sma_slow"),
                decision.get("vol_z"), int(bool(decision.get("entry_event"))),
                int(bool(decision.get("exit_event"))), executed, block_reason,
            ),
        )

    def record_intent(self, intent: dict[str, Any]) -> None:
        self._exec(
            """INSERT OR REPLACE INTO order_intents (key, ts_ms, symbol, side, quantity, quote_estimate,
               bar_close_ms, action, status, order_id, client_order_id, message)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                intent["key"], intent.get("created_ms", intent.get("ts_ms")), intent["symbol"], intent["side"],
                str(intent["quantity"]), str(intent["quote_estimate"]), intent["bar_close_ms"],
                intent["action"], intent.get("status", "PENDING"),
                intent.get("order_id"), intent.get("client_order_id"), intent.get("message"),
            ),
        )

    def record_order(self, order: dict[str, Any]) -> None:
        self._exec(
            """INSERT OR REPLACE INTO orders (client_order_id, order_id, ts_ms, symbol, side, order_type,
               quantity, status, filled_qty, avg_price, raw_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                order.get("client_order_id"), order.get("order_id"), order.get("ts_ms"),
                order.get("symbol"), order.get("side"), order.get("order_type"),
                str(order.get("quantity", "")), order.get("status"),
                str(order.get("filled_qty", "")), str(order.get("avg_price", "")),
                json.dumps(order.get("raw"), default=str),
            ),
        )

    def record_order_event(self, ts_ms: int, client_order_id: str, event: str, detail: dict | None = None) -> None:
        self._exec(
            "INSERT INTO order_events (ts_ms, client_order_id, event, detail_json) VALUES (?,?,?,?)",
            (ts_ms, client_order_id, event, json.dumps(detail or {}, default=str)),
        )

    def record_fill(self, fill: dict[str, Any]) -> None:
        self._exec(
            """INSERT OR IGNORE INTO fills (symbol, trade_id, order_id, client_order_id, ts_ms, side,
               price, qty, quote_qty, commission, commission_asset, is_maker, source)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                fill["symbol"], fill["trade_id"], fill["order_id"], fill["client_order_id"],
                fill["time_ms"], fill["side"], str(fill["price"]), str(fill["qty"]),
                str(fill["quote_qty"]), str(fill["commission"]), fill["commission_asset"],
                int(bool(fill["is_maker"])), fill.get("source", "stream"),
            ),
        )

    def record_balance(self, ts_ms: int, asset: str, free: str, locked: str, source: str) -> None:
        self._exec(
            "INSERT INTO balances (ts_ms, asset, free, locked, source) VALUES (?,?,?,?,?)",
            (ts_ms, asset, free, locked, source),
        )

    def record_equity(self, snapshot: dict[str, Any]) -> None:
        self._exec(
            """INSERT INTO equity (ts_ms, budget, cash_free, cash_reserved, base_qty, base_price,
               inventory_value, pending_costs, equity, complete, notes_json, source)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                snapshot["ts_ms"], str(snapshot["budget"]), str(snapshot["cash_free"]),
                str(snapshot["cash_reserved"]), str(snapshot["base_qty"]), str(snapshot["base_price"]),
                str(snapshot["inventory_value"]), str(snapshot["pending_costs"]),
                str(snapshot["equity"]), int(bool(snapshot["complete"])),
                json.dumps(snapshot.get("notes", [])), snapshot.get("source", "supervisor"),
            ),
        )

    def record_health(self, ts_ms: int, status: str, reasons: list[str]) -> None:
        self._exec(
            "INSERT INTO health (ts_ms, status, reasons_json) VALUES (?,?,?)",
            (ts_ms, status, json.dumps(reasons)),
        )

    def record_incident(self, ts_ms: int, kind: str, detail: dict | None = None, resolved_ms: int | None = None) -> None:
        self._exec(
            "INSERT INTO incidents (ts_ms, kind, detail_json, resolved_ms) VALUES (?,?,?,?)",
            (ts_ms, kind, json.dumps(detail or {}, default=str), resolved_ms),
        )

    def record_trade(self, trade: dict[str, Any]) -> None:
        self._exec(
            """INSERT INTO trades (symbol, entry_ts_ms, exit_ts_ms, entry_qty, entry_avg_px,
               exit_avg_px, pnl, fees_json, closed, duration_s, exposure_s)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                trade["symbol"], trade["entry_ts_ms"], trade["exit_ts_ms"],
                str(trade["entry_qty"]), str(trade["entry_avg_px"]), str(trade["exit_avg_px"]),
                str(trade["pnl"]), json.dumps(trade.get("fees", {}), default=str),
                int(bool(trade.get("closed"))), trade.get("duration_s"), trade.get("exposure_s"),
            ),
        )

    def record_export(self, ts_ms: int, export_id: str, files: list[dict]) -> None:
        self._exec(
            "INSERT INTO exports (ts_ms, export_id, files_json) VALUES (?,?,?)",
            (ts_ms, export_id, json.dumps(files, default=str)),
        )

    def _exec(self, sql: str, params: tuple) -> None:
        with self._lock:
            self._conn.execute(sql, params)
            self._conn.commit()

    # ------------------------------------------------------------------ lectura
    def fetch(self, table: str, order_by: str = "rowid") -> list[dict]:
        allowed = {
            "run", "state_history", "signals", "order_intents", "orders", "order_events",
            "fills", "balances", "equity", "health", "incidents", "trades", "exports",
        }
        if table not in allowed:
            raise ValueError(f"tabla no permitida: {table}")
        with self._lock:
            rows = self._conn.execute(f"SELECT * FROM {table} ORDER BY {order_by}").fetchall()
        return [dict(row) for row in rows]

    def count(self, table: str) -> int:
        with self._lock:
            row = self._conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
        return int(row["n"])

    def last_equity(self) -> dict | None:
        rows = self.fetch("equity", order_by="id DESC")
        return rows[0] if rows else None

    def write_probe(self) -> bool:
        """Verifica que la persistencia responde (RF-REC-06)."""
        try:
            self._exec("INSERT INTO health (ts_ms, status, reasons_json) VALUES (?,?,?)", (int(time.time() * 1000), "PROBE", "[]"))
            return True
        except Exception:
            return False
