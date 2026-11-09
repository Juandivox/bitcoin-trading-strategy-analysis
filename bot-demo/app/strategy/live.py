"""Estrategia E2-A en vivo sobre NautilusTrader (barras 4H cerradas, órdenes de mercado, long-only).

Contrato de contexto (`ctx`) esperado — lo construye `app/main.py`:
  cfg: BotConfig, ledger: Ledger, audit: AuditDB, logger: Logger,
  status: RuntimeStatus, rest: DemoRESTClient,
  on_fill(fill: FillRecord) -> None, on_signal(decision: dict) -> None,
  control_action() -> str | None  (acción pendiente del operador, ya validada)
"""
from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from nautilus_trader.common import Environment  # noqa: F401  (API estable de rc5)
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model import Bar, BarType, InstrumentId
from nautilus_trader.trading import Strategy

from app.accounting.ledger import Ledger
from app.audit.db import AuditDB
from app.audit.logs import Logger
from app.contracts import FillRecord, SignalDecision
from app.exchange.demo_rest import AmbiguousResult, DemoRESTClient, DemoRESTError, floor_to_step
from app.strategy.e2a import latest_diagnostics
from app.supervision.status import RuntimeStatus

STRATEGY_STATE_FILE = "strategy_state.json"


class E2ALiveConfig(StrategyConfig):
    """Configuración serializable + contexto de runtime (no serializado, uso in-process)."""

    def __init__(
        self,
        *,
        instrument_id: InstrumentId,
        bar_type: BarType,
        symbol: str,
        params: dict,
        budget_usdt: float,
        entry_notional_usdt: float,
        max_positions: int,
        history_bars: int,
        signal_expiry_s: int,
        **_kwargs,
    ) -> None:
        super().__init__()
        self.instrument_id = instrument_id
        self.bar_type = bar_type
        self.symbol = symbol
        self.params = params
        self.budget_usdt = budget_usdt
        self.entry_notional_usdt = entry_notional_usdt
        self.max_positions = max_positions
        self.history_bars = history_bars
        self.signal_expiry_s = signal_expiry_s
        self.ctx = None  # inyectado tras construir


class E2ALiveStrategy(Strategy):
    def __init__(self, config: E2ALiveConfig) -> None:
        super().__init__(config)
        self.ctx = config.ctx
        cfg = self.ctx.cfg
        self._params = cfg.strategy_params
        self._window: deque[dict] = deque(maxlen=cfg.history_bars)
        self._seen_bar_ts: set[int] = set()
        self._signal_state = 0
        self._pending: dict | None = None
        self._state_file = Path(cfg.run_dir) / STRATEGY_STATE_FILE
        self._lock = threading.Lock()
        self._instrument = None
        self._filters = None
        self._last_control_poll_ms = 0
        self._entries_paused_reported = False

    # ------------------------------------------------------------------ ciclo de vida
    def on_start(self) -> None:
        cfg = self.ctx.cfg
        self._load_state()
        instrument = self.cache.instrument(self.config.instrument_id)
        if instrument is None:
            self.ctx.logger.critical("instrumento_no_encontrado", instrument=str(self.config.instrument_id))
            self.ctx.audit.record_incident(
                int(time.time() * 1000), "instrumento_no_encontrado",
                {"instrument": str(self.config.instrument_id)},
            )
            self.stop()
            return
        self._instrument = instrument
        try:
            self._filters = self.ctx.rest.get_filters(cfg.symbol)
        except Exception as exc:  # noqa: BLE001
            self.ctx.logger.error("filtros_no_disponibles", error=repr(exc))
            self.stop()
            return
        self.request_bars(self.config.bar_type, limit=cfg.history_bars)
        self.subscribe_bars(self.config.bar_type)
        self.subscribe_quotes(self.config.instrument_id)
        self.clock.set_timer(
            "e2a-control",
            interval=timedelta(seconds=5),
            callback=self._on_timer,
            fire_immediately=False,
        )
        self.ctx.logger.info(
            "estrategia_iniciada",
            instrument=cfg.instrument_id,
            bar_type=cfg.bar_type,
            variante=cfg.strategy_variant,
            history_bars=cfg.history_bars,
            signal_state=self._signal_state,
        )

    def on_stop(self) -> None:
        self._save_state()
        self.ctx.logger.info("estrategia_detenida", signal_state=self._signal_state, pendiente=self._pending)

    def on_resume(self) -> None:
        self.ctx.logger.info("estrategia_reanudada")

    # ------------------------------------------------------------------ datos
    def on_historical_bars(self, bars) -> None:
        added = 0
        for bar in bars:
            if self._append_bar(bar):
                added += 1
        self.ctx.status.mark_history_loaded(len(self._window))
        if self._window:
            self.ctx.status.mark_bar(int(self._window[-1]["ts_ms"]))
        self.ctx.logger.info("historico_cargado", velas=added, ventana=len(self._window))
        if len(self._window) >= self._params.warmup_bars:
            self._replay_missed_signals()
            self.ctx.status.mark_signal_state(self._signal_state)
            self._evaluate(int(self._window[-1]["ts_ms"]))

    def on_bar(self, bar: Bar) -> None:
        if not self._append_bar(bar):
            return
        ts_ms = int(bar.ts_event) // 1_000_000
        self.ctx.status.mark_bar(ts_ms)
        if len(self._window) < self._params.warmup_bars:
            self.ctx.logger.info("calentando", velas=len(self._window), requeridas=self._params.warmup_bars)
            return
        self._evaluate(ts_ms)

    def on_quote(self, tick) -> None:
        self.ctx.status.mark_quote(int(tick.ts_event) // 1_000_000)

    def _append_bar(self, bar: Bar) -> bool:
        ts = int(bar.ts_event)
        if ts in self._seen_bar_ts:
            return False
        if self._seen_bar_ts and ts < max(self._seen_bar_ts):
            return False
        self._seen_bar_ts.add(ts)
        self._window.append(
            {
                "ts_ms": ts // 1_000_000,
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": float(bar.volume),
            }
        )
        return True

    # ------------------------------------------------------------------ señales
    def _evaluate(self, ts_ms: int) -> None:
        import numpy as np

        highs = np.array([b["high"] for b in self._window], dtype=np.float64)
        lows = np.array([b["low"] for b in self._window], dtype=np.float64)
        closes = np.array([b["close"] for b in self._window], dtype=np.float64)
        volumes = np.array([b["volume"] for b in self._window], dtype=np.float64)

        prev_state = self._signal_state
        diag = latest_diagnostics(highs, lows, closes, volumes, self._params, prev_state)
        self._signal_state = int(diag["target_position"])
        self._save_state()
        self.ctx.status.mark_eval()
        self.ctx.status.mark_signal_state(self._signal_state)

        decision = SignalDecision(
            bar_close_ms=ts_ms,
            bar_close_price=float(closes[-1]),
            target_position=int(diag["target_position"]),
            prev_state=prev_state,
            action=diag["action"],
            reason=diag["reason"],
            cci=float(diag["cci"]),
            sma_fast=float(diag["sma_fast"]),
            sma_slow=float(diag["sma_slow"]),
            vol_z=float(diag["vol_z"]),
            entry_event=bool(diag["entry_event"]),
            exit_event=bool(diag["exit_event"]),
        )
        self.ctx.logger.info(
            "senal_evaluada",
            barra_cierre_ms=ts_ms,
            accion=decision.action,
            objetivo=decision.target_position,
            previo=prev_state,
            cci=round(decision.cci, 4),
            sma_f=round(decision.sma_fast, 2),
            sma_s=round(decision.sma_slow, 2),
            vol_z=round(decision.vol_z, 4),
            motivo=decision.reason,
        )
        self.ctx.on_signal(decision)

        if decision.target_position == prev_state:
            self.ctx.audit.record_signal(
                int(time.time() * 1000), self._decision_dict(decision), "SIN_CAMBIO", None
            )
            return

        self._act(decision)

    def _replay_missed_signals(self) -> None:
        """Al arrancar: reconstruye el estado de señal con las velas ya cargadas.

        - Nunca abre una entrada retroactiva (RF-DAT-06); si el evento de entrada ocurrió
          en la última vela cerrada y sigue vigente, se deja que `_evaluate` lo procese.
        - Si hay inventario y la señal quedó plana, la salida SÍ se ejecuta ahora
          (las salidas no se bloquean, RF-ORD-06).
        """
        import numpy as np

        highs = np.array([b["high"] for b in self._window], dtype=np.float64)
        lows = np.array([b["low"] for b in self._window], dtype=np.float64)
        closes = np.array([b["close"] for b in self._window], dtype=np.float64)
        volumes = np.array([b["volume"] for b in self._window], dtype=np.float64)
        diag = latest_diagnostics(highs, lows, closes, volumes, self._params, self._signal_state)
        new_state = int(diag["target_position"])
        prev = self._signal_state
        held = self.ctx.ledger.base_qty() > 0
        if new_state == prev:
            return
        last_ts = int(self._window[-1]["ts_ms"])
        last_close = float(self._window[-1]["close"])
        if new_state == 1 and not held:
            if bool(diag["entry_event"]) and self._is_recent(last_ts):
                self.ctx.logger.info("entrada_vigente_al_arranque", motivo="evento_en_ultima_vela")
                return
            self._signal_state = 1
            self._save_state()
            self.ctx.logger.warning("entrada_perdida_no_retroactiva", motivo="senal_larga_sin_posicion")
            self.ctx.audit.record_incident(
                int(time.time() * 1000), "entrada_perdida_no_retroactiva", {"bar_close_ms": last_ts}
            )
            return
        if new_state == 0 and held:
            self._signal_state = 0
            self._save_state()
            self.ctx.logger.warning("salida_pendiente_se_ejecuta_ahora", motivo="senal_plana_con_inventario")
            decision = SignalDecision(
                bar_close_ms=last_ts, bar_close_price=last_close, target_position=0, prev_state=1,
                action="EXIT", reason="salida_al_arranque",
                cci=float(diag["cci"]), sma_fast=float(diag["sma_fast"]),
                sma_slow=float(diag["sma_slow"]), vol_z=float(diag["vol_z"]),
                entry_event=False, exit_event=bool(diag["exit_event"]),
            )
            self._submit_exit(decision)
            return
        self.ctx.logger.info("estado_senal_reconstruido", previo=prev, nuevo=new_state)
        self._signal_state = new_state
        self._save_state()

    def _is_recent(self, bar_close_ms: int) -> bool:
        return (int(time.time() * 1000) - bar_close_ms) <= self.ctx.cfg.tolerances.signal_expiry_s * 1000

    # ------------------------------------------------------------------ acciones
    def _act(self, decision: SignalDecision) -> None:
        if self._pending is not None:
            self.ctx.logger.warning("accion_bloqueada_orden_pendiente", cid=self._pending.get("client_order_id"))
            self.ctx.audit.record_signal(
                int(time.time() * 1000), self._decision_dict(decision), "BLOQUEADA", "orden_pendiente"
            )
            return

        held = self.ctx.ledger.base_qty() > 0
        if decision.target_position == 1:
            if held:
                return
            if not self._is_recent(decision.bar_close_ms):
                self.ctx.audit.record_signal(
                    int(time.time() * 1000), self._decision_dict(decision), "EXPIRADA", "senal_fuera_de_ventana"
                )
                self.ctx.logger.warning("entrada_expirada", bar_close_ms=decision.bar_close_ms)
                return
            block = self._entry_block_reason()
            if block:
                self.ctx.audit.record_signal(
                    int(time.time() * 1000), self._decision_dict(decision), "BLOQUEADA", block
                )
                self.ctx.logger.warning("entrada_bloqueada", motivo=block)
                return
            self._submit_entry(decision)
        else:
            if not held:
                return
            self._submit_exit(decision)

    def _entry_block_reason(self) -> str | None:
        status = self.ctx.health_now()
        if status != "SALUDABLE":
            return f"salud_{status.lower()}"
        if self.ctx.state.entries_paused:
            return "entradas_pausadas"
        if self.ctx.state.state.value in ("CERRANDO", "DETENIDO", "INTERRUMPIDA", "FINALIZADA", "FINALIZADA_CON_RESIDUO"):
            return f"estado_{self.ctx.state.state.value.lower()}"
        open_positions = 1 if self.ctx.ledger.base_qty() > 0 else 0
        if open_positions >= self.ctx.cfg.max_positions:
            return "max_posiciones"
        free = self._free_quote()
        if free is None:
            return "saldo_no_verificable"
        needed = Decimal(str(self.ctx.cfg.entry_notional_usdt))
        if free < needed:
            return "saldo_insuficiente"
        return None

    def _free_quote(self) -> Decimal | None:
        try:
            return self.ctx.rest.free_balance("USDT")
        except Exception as exc:  # noqa: BLE001
            self.ctx.logger.warning("saldo_no_consultable", error=repr(exc))
            return None

    def _submit_entry(self, decision: SignalDecision) -> None:
        price = Decimal(str(decision.bar_close_price))
        notional = Decimal(str(self.ctx.cfg.entry_notional_usdt))
        if self._filters is not None and notional < self._filters.min_notional:
            self.ctx.logger.error(
                "entrada_no_ejecutable_por_filtros",
                notional=str(notional), min_notional=str(self._filters.min_notional),
            )
            self.ctx.audit.record_signal(
                int(time.time() * 1000), self._decision_dict(decision), "RECHAZADA_LOCAL", "filtros"
            )
            return
        self._submit("ENTRY", "BUY", None, price, decision.bar_close_ms, quote_notional=notional)

    def _submit_exit(self, decision: SignalDecision) -> None:
        assert self._filters is not None
        qty = floor_to_step(self.ctx.ledger.base_qty(), self._filters.step_size)
        price = Decimal(str(decision.bar_close_price))
        if qty <= 0:
            self.ctx.logger.warning("salida_sin_cantidad_negociable", base_qty=str(self.ctx.ledger.base_qty()))
            self.ctx.audit.record_signal(
                int(time.time() * 1000), self._decision_dict(decision), "RESIDUO", "cantidad_bajo_step"
            )
            return
        if qty * price < self._filters.min_notional:
            self.ctx.logger.warning(
                "salida_bajo_min_notional", qty=str(qty), notional=str(qty * price),
                min_notional=str(self._filters.min_notional),
            )
            self.ctx.audit.record_signal(
                int(time.time() * 1000), self._decision_dict(decision), "RESIDUO", "bajo_min_notional"
            )
            return
        self._submit("EXIT", "SELL", qty, price, decision.bar_close_ms)

    def _submit(self, action: str, side: str, qty: Decimal | None, price: Decimal,
                bar_close_ms: int, quote_notional: Decimal | None = None) -> None:
        key = self.ctx.executor.intent_key(action, bar_close_ms)
        self._pending = {
            "action": action, "client_order_id": key, "bar_close_ms": bar_close_ms,
            "submitted_ms": int(time.time() * 1000),
            "quantity": str(qty) if qty is not None else f"quote:{quote_notional}",
        }
        self.ctx.status.mark_order_submitted()
        status = self.ctx.executor.submit_market(
            action=action, side=side, bar_close_ms=bar_close_ms,
            quantity=qty, quote_notional=quote_notional, price_estimate=price,
        )
        if status in ("FILLED", "PARTIALLY_FILLED", "CANCELED", "EXPIRED", "REJECTED", "DUPLICADA"):
            self._pending = None
        self.ctx.logger.info("orden_despachada", accion=action, clave=key, resultado=status)

    # ------------------------------------------------------------------ control / salud
    def _on_timer(self, event) -> None:
        self._resolve_pending()
        self._handle_control()

    def _resolve_pending(self) -> None:
        """La conciliación real la hace el supervisor (RestExecutor); aquí solo se refleja."""
        pending = self._pending
        if pending is None:
            return
        status = self.ctx.executor.intent_status(pending["client_order_id"])
        if status is None:
            return
        if status in ("FILLED", "PARTIALLY_FILLED", "CANCELED", "EXPIRED", "REJECTED"):
            self.ctx.logger.info("pendiente_resuelto", cid=pending["client_order_id"], estado=status)
            self._pending = None
        elif status == "UNKNOWN" and (int(time.time() * 1000) - pending["submitted_ms"]) > 300_000:
            self.ctx.logger.warning("pendiente_sigue_incierto", cid=pending["client_order_id"])

    def _handle_control(self) -> None:
        action = self.ctx.control_action()
        if action is None:
            return
        self.ctx.logger.info("control_recibido", accion=action)
        if action == "close_position":
            if self.ctx.ledger.base_qty() > 0 and self._pending is None:
                decision = SignalDecision(
                    bar_close_ms=int(self._window[-1]["ts_ms"]) if self._window else 0,
                    bar_close_price=float(self._window[-1]["close"]) if self._window else 0.0,
                    target_position=0, prev_state=1, action="EXIT", reason="control_close_position",
                    cci=0.0, sma_fast=0.0, sma_slow=0.0, vol_z=0.0, entry_event=False, exit_event=False,
                )
                self._submit_exit(decision)
        elif action == "close_all":
            if self.ctx.ledger.base_qty() > 0 and self._pending is None:
                decision = SignalDecision(
                    bar_close_ms=int(self._window[-1]["ts_ms"]) if self._window else 0,
                    bar_close_price=float(self._window[-1]["close"]) if self._window else 0.0,
                    target_position=0, prev_state=1, action="EXIT", reason="control_close_all",
                    cci=0.0, sma_fast=0.0, sma_slow=0.0, vol_z=0.0, entry_event=False, exit_event=False,
                )
                self._submit_exit(decision)

    # ------------------------------------------------------------------ estado persistente
    def _decision_dict(self, decision: SignalDecision) -> dict:
        return {
            "bar_close_ms": decision.bar_close_ms,
            "bar_close_price": decision.bar_close_price,
            "target_position": decision.target_position,
            "prev_state": decision.prev_state,
            "action": decision.action,
            "reason": decision.reason,
            "cci": decision.cci,
            "sma_fast": decision.sma_fast,
            "sma_slow": decision.sma_slow,
            "vol_z": decision.vol_z,
            "entry_event": decision.entry_event,
            "exit_event": decision.exit_event,
        }

    def _load_state(self) -> None:
        try:
            if self._state_file.exists():
                data = json.loads(self._state_file.read_text(encoding="utf-8"))
                self._signal_state = int(data.get("signal_state", 0))
                self.ctx.logger.info("estado_estrategia_cargado", signal_state=self._signal_state)
        except Exception as exc:  # noqa: BLE001
            self.ctx.logger.warning("estado_estrategia_ilegible", error=repr(exc))
            self._signal_state = 0

    def _save_state(self) -> None:
        try:
            tmp = self._state_file.with_suffix(".tmp")
            tmp.write_text(json.dumps({"signal_state": self._signal_state,
                                       "updated_ms": int(time.time() * 1000)}), encoding="utf-8")
            os.replace(tmp, self._state_file)
        except Exception as exc:  # noqa: BLE001
            self.ctx.logger.error("estado_estrategia_no_guardado", error=repr(exc))

    # ------------------------------------------------------------------ utilidades de test
    def force_evaluate_now(self) -> None:
        """Solo tests: evalúa la ventana actual sin esperar una vela nueva."""
        if len(self._window) >= self._params.warmup_bars:
            self._evaluate(int(self._window[-1]["ts_ms"]))
