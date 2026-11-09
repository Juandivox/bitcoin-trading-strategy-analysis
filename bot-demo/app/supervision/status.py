"""Estado de salud compartido entre el hilo del nodo Nautilus y el supervisor."""
from __future__ import annotations

import threading
import time


class RuntimeStatus:
    """Marcas de tiempo y contadores que el nodo actualiza y el supervisor evalúa."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.last_bar_close_ms: int | None = None
        self.last_bar_seen_wall_ms: int | None = None
        self.last_quote_ms: int | None = None
        self.last_private_event_ms: int | None = None
        self.last_eval_ms: int | None = None
        self.last_reconcile_ms: int | None = None
        self.bars_seen: int = 0
        self.signals_evaluated: int = 0
        self.orders_submitted: int = 0
        self.fills_applied: int = 0
        self.node_connected: bool = False
        self.exec_connected: bool = False
        self.last_error: str | None = None
        self.signal_state: int | None = None
        self.extra: dict = {}

    def _set(self, **fields) -> None:
        with self._lock:
            for key, value in fields.items():
                setattr(self, key, value)

    def mark_bar(self, close_ms: int, seen_wall_ms: int | None = None) -> None:
        with self._lock:
            self.last_bar_close_ms = close_ms
            self.last_bar_seen_wall_ms = seen_wall_ms or int(time.time() * 1000)
            self.bars_seen += 1

    def mark_quote(self, ts_ms: int) -> None:
        with self._lock:
            if self.last_quote_ms is None or ts_ms > self.last_quote_ms:
                self.last_quote_ms = ts_ms

    def mark_private_event(self, ts_ms: int | None = None) -> None:
        self._set(last_private_event_ms=ts_ms or int(time.time() * 1000))

    def mark_eval(self) -> None:
        with self._lock:
            self.last_eval_ms = int(time.time() * 1000)
            self.signals_evaluated += 1

    def mark_signal_state(self, state: int) -> None:
        self._set(signal_state=int(state))

    def mark_history_loaded(self, count: int) -> None:
        with self._lock:
            self.bars_seen = max(self.bars_seen, int(count))

    def mark_order_submitted(self) -> None:
        with self._lock:
            self.orders_submitted += 1

    def mark_fill(self) -> None:
        with self._lock:
            self.fills_applied += 1

    def mark_reconcile(self) -> None:
        self._set(last_reconcile_ms=int(time.time() * 1000))

    def set_connections(self, *, node: bool | None = None, exec_client: bool | None = None) -> None:
        with self._lock:
            if node is not None:
                self.node_connected = node
            if exec_client is not None:
                self.exec_connected = exec_client

    def set_error(self, message: str | None) -> None:
        self._set(last_error=message)

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "last_bar_close_ms": self.last_bar_close_ms,
                "last_bar_seen_wall_ms": self.last_bar_seen_wall_ms,
                "last_quote_ms": self.last_quote_ms,
                "last_private_event_ms": self.last_private_event_ms,
                "last_eval_ms": self.last_eval_ms,
                "last_reconcile_ms": self.last_reconcile_ms,
                "bars_seen": self.bars_seen,
                "signals_evaluated": self.signals_evaluated,
                "orders_submitted": self.orders_submitted,
                "fills_applied": self.fills_applied,
                "node_connected": self.node_connected,
                "exec_connected": self.exec_connected,
                "last_error": self.last_error,
                "signal_state": self.signal_state,
                **self.extra,
            }
