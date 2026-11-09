"""Supervisor del bot: gates de arranque (RF-SEG-05), estados, salud, patrimonio y control.

Ejecuta el nodo NautilusTrader en un hilo y mantiene en este proceso la autoridad
operativa: escritor único, auditoría, contabilidad, salud, snapshots y exportaciones.
"""
from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
import time
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from app.accounting.ledger import Ledger
from app.accounting.metrics import compute_metrics
from app.audit.db import AuditDB
from app.audit.logs import Logger, utc_iso
from app.config import BotConfig, Secrets
from app.contracts import FillRecord, RunState, SignalDecision
from app.exchange.demo_rest import AmbiguousResult, DemoRESTClient, DemoRESTError
from app.execution.rest_executor import RestExecutor
from app.reports.export import export_run
from app.runner import build_node
from app.supervision.control import ControlFile
from app.supervision.health import evaluate_freshness
from app.supervision.lock import LockHeldError, SingleWriterLock
from app.supervision.state import InvalidTransition, StateMachine
from app.supervision.status import RuntimeStatus

try:
    from nautilus_trader.live import NodeState
except Exception:  # pragma: no cover - permite tests sin nautilus instalado
    NodeState = None

SOFTWARE_VERSIONS = {"python": sys.version.split()[0]}


class StartupError(RuntimeError):
    """Fallo de un gate de arranque: no se habilita la ejecución."""


class LiveContext:
    """Contrato que consume E2ALiveStrategy (ver docstring de app/strategy/live.py)."""

    def __init__(self, supervisor: "Supervisor") -> None:
        self._sup = supervisor
        self.cfg = supervisor.cfg
        self.ledger = supervisor.ledger
        self.audit = supervisor.audit
        self.logger = supervisor.logger
        self.status = supervisor.status
        self.rest = supervisor.rest
        self.state = supervisor.state
        self.executor = supervisor.executor

    def health_now(self) -> str:
        return self._sup.health_status

    def control_action(self) -> str | None:
        action = self._sup.control_action
        self._sup.control_action = None
        return action

    def on_fill(self, fill: FillRecord) -> None:
        self._sup.handle_fill(fill)

    def on_signal(self, decision: SignalDecision) -> None:
        self._sup.handle_signal(decision)


class Supervisor:
    def __init__(self, cfg: BotConfig, secrets: Secrets, echo_logs: bool = True) -> None:
        self.cfg = cfg
        self.secrets = secrets
        cfg.ensure_dirs()
        self.logger = Logger(
            "bot",
            jsonl_path=cfg.logs_dir / "bot.jsonl",
            level="INFO",
            secrets=[secrets.api_key, secrets.api_secret],
            echo=echo_logs,
        )
        self.audit = AuditDB(cfg.db_path)
        self.state = StateMachine(cfg.state_path, cfg.run_id)
        self.control = ControlFile(cfg.control_path)
        self.ledger = Ledger(cfg.symbol)
        self.status = RuntimeStatus()
        self.rest = DemoRESTClient(
            base_url=cfg.demo_rest_base,
            api_key=secrets.api_key,
            api_secret=secrets.api_secret,
        )
        self.executor = RestExecutor(cfg, self.rest, self.audit, self.logger, self.ledger)
        self.lock = SingleWriterLock(
            cfg.lock_path, cfg.run_id, heartbeat_timeout_s=cfg.tolerances.stale_lock_heartbeat_s
        )
        self.health_status = "SALUDABLE"
        self.control_action: str | None = None
        self._stop_event = threading.Event()
        self._node = None
        self._handle = None
        self._node_seen_running = False
        self._supervisor_thread: threading.Thread | None = None
        self._declared_residual_qty = Decimal("0")
        self._last_equity_ms = 0
        self._last_health: str | None = None
        self._episode: dict | None = None
        self._close_request_ms: int | None = None
        self._close_ack_sent = False
        self._exit_code = 0
        self._tolerances = cfg.tolerances
        self._interval_ms = cfg.bar_minutes * 60_000
        self._ctx = LiveContext(self)

    # ------------------------------------------------------------------ arranque
    def run(self) -> int:
        try:
            self.lock.acquire()
        except LockHeldError as exc:
            self.logger.critical("escritor_unico_ocupado", holder=exc.holder)
            print(f"ERROR: ya hay un proceso escribiendo esta prueba: {exc.holder}", file=sys.stderr)
            return 75
        try:
            self.logger.info(
                "proceso_iniciado",
                run_id=self.cfg.run_id,
                variante=self.cfg.strategy_variant,
                instrumento=self.cfg.instrument_id,
                presupuesto=str(self.cfg.budget_usdt),
                fingerprint=self.cfg.fingerprint(),
                lock_takeover=self.lock.took_over,
            )
            self._record_run()
            self.state.load()
            if self.state.state in (RunState.BORRADOR, RunState.DETENIDO):
                self._transition(RunState.VALIDANDO, "arranque")
            elif self.state.state not in (RunState.VALIDANDO,):
                # Caída sin parada ordenada (p. ej. corte de luz): el estado quedó en
                # EJECUTANDO/ENTRADAS_PAUSADAS/CALENTANDO/etc. Reencauzar por
                # DETENIDO -> VALIDANDO para que las transiciones sigan siendo válidas.
                # Los terminales (INTERRUMPIDA/FINALIZADA*) no se tocan: requieren
                # intervención del operador (ver scripts/recover_interrupted.py).
                try:
                    if self.state.state in (
                        RunState.EJECUTANDO,
                        RunState.ENTRADAS_PAUSADAS,
                        RunState.CALENTANDO,
                        RunState.RECONCILIANDO,
                        RunState.CERRANDO,
                    ):
                        self._transition(RunState.DETENIDO, "reinicio tras caída")
                        self._transition(RunState.VALIDANDO, "arranque")
                except Exception:  # noqa: BLE001
                    pass
            self._startup_gates()
            self._startup_reconciliation()
            self._start_node()
            self._supervisor_thread = threading.Thread(
                target=self._main_loop, name="supervisor", daemon=True
            )
            self._supervisor_thread.start()
            self.logger.info("supervisor_activo")
            try:
                self._node.run()  # LiveNode es unsendable: debe correr en el hilo principal
            except Exception as exc:  # noqa: BLE001
                self.logger.critical("nodo_termino_con_error", error=repr(exc))
                self.audit.record_incident(int(time.time() * 1000), "nodo_error", {"error": repr(exc)})
                self._exit_code = 1
            self._stop_event.set()
            if self._supervisor_thread.is_alive():
                self._supervisor_thread.join(timeout=20)
        except StartupError as exc:
            self.health_status = "ERROR_CONFIGURACION"
            self.logger.critical("gate_de_arranque_fallido", motivo=str(exc))
            self.audit.record_incident(int(time.time() * 1000), "gate_de_arranque_fallido", {"motivo": str(exc)})
            # El gate de presupuesto (p. ej. tras corte de luz con posición abierta)
            # es reintentable: ir a DETENIDO (DETENIDO -> VALIDANDO está permitido)
            # en vez de INTERRUMPIDA (terminal, sin salida). Los demás gates
            # conservan INTERRUMPIDA.
            target = RunState.DETENIDO if str(exc).startswith("presupuesto") else RunState.INTERRUMPIDA
            try:
                self._transition(target, f"gate: {exc}")
            except Exception:  # noqa: BLE001
                pass
            self._exit_code = 78
        except Exception as exc:  # noqa: BLE001
            self.logger.critical("fallo_no_controlado", error=repr(exc))
            self.audit.record_incident(int(time.time() * 1000), "fallo_no_controlado", {"error": repr(exc)})
            self._exit_code = 1
        finally:
            self._shutdown()
        return self._exit_code

    def _record_run(self) -> None:
        existing = self.audit.fetch("run")
        if existing:
            self.logger.info(
                "prueba_existente_reanudada",
                run_id=self.cfg.run_id,
                iniciada_ms=existing[0].get("started_ms"),
            )
            return
        info = {
            "run_id": self.cfg.run_id,
            "started_ms": int(time.time() * 1000),
            "config_fingerprint": self.cfg.fingerprint(),
            "config_json": self.cfg.to_public_dict(),
            "strategy_variant": self.cfg.strategy_variant,
            "strategy_params_json": asdict(self.cfg.strategy_params),
            "budget_usdt": str(self.cfg.budget_usdt),
            "instrument": self.cfg.instrument_id,
            "bar_type": self.cfg.bar_type,
            "software_versions_json": SOFTWARE_VERSIONS,
            "git_commit": _git_commit(),
        }
        self.audit.record_run(info)
        manifest = {
            **info,
            "created_ms": int(time.time() * 1000),
            "destinos": {
                "rest": self.cfg.demo_rest_base,
                "ws_stream": self.cfg.demo_ws_stream_base,
                "ws_api": self.cfg.demo_ws_api_base,
                "binance_environment": "DEMO",
                "nautilus_node_environment": "LIVE",
            },
        }
        self.cfg.manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )

    # ------------------------------------------------------------------ gates
    def _startup_gates(self) -> None:
        self.logger.info("gate_inicio", paso="reloj")
        offset = self.rest.sync_time()
        if abs(offset) > 5000:
            raise StartupError(f"reloj desviado {offset} ms respecto a Binance DEMO")
        self.logger.info("gate_ok", paso="reloj", offset_ms=offset)

        account = self.rest.account()
        if not account.get("canTrade"):
            raise StartupError("la cuenta DEMO no tiene canTrade habilitado")
        permissions = account.get("permissions") or []
        if permissions and "SPOT" not in permissions:
            raise StartupError(f"la API key no tiene permiso SPOT: {permissions}")
        self.logger.info("gate_ok", paso="cuenta", canTrade=True, permisos=permissions)

        filters = self.rest.get_filters(self.cfg.symbol)
        if filters.min_notional > Decimal(str(self.cfg.entry_notional_usdt)):
            raise StartupError(
                f"min_notional {filters.min_notional} > entrada objetivo {self.cfg.entry_notional_usdt}"
            )
        self.logger.info(
            "gate_ok", paso="filtros", step=str(filters.step_size), min_notional=str(filters.min_notional)
        )

        bars = self.rest.klines(self.cfg.symbol, self.cfg.bar_interval, limit=5)
        if len(bars) < 5:
            raise StartupError("no hay suficientes velas 4h en DEMO para operar")
        last_close_ms = int(bars[-1][6])
        age_s = (int(time.time() * 1000) - last_close_ms) / 1000
        if age_s > 2 * self.cfg.bar_minutes * 60:
            raise StartupError(f"última vela 4h demasiado antigua: {age_s:.0f}s")
        self.logger.info("gate_ok", paso="datos", ultima_vela=utc_iso(last_close_ms))

        if not self.audit.write_probe():
            raise StartupError("la base de auditoría no acepta escrituras")
        self.logger.info("gate_ok", paso="persistencia")

        open_orders = self.rest.open_orders(self.cfg.symbol)
        ours = {row["client_order_id"] for row in self.audit.fetch("order_intents") if row.get("client_order_id")}
        foreign = [o for o in open_orders if o.get("clientOrderId") not in ours]
        if foreign:
            self.logger.error("ordenes_ajenas_detectadas", cantidad=len(foreign))
            self.audit.record_incident(
                int(time.time() * 1000), "ordenes_ajenas", {"orders": [o.get("orderId") for o in foreign]}
            )
            self.state.pause_entries("ordenes_ajenas_en_la_cuenta")
        self.logger.info("gate_ok", paso="ordenes_abiertas", abiertas=len(open_orders), ajenas=len(foreign))

        # Reconstruir el ledger desde la auditoría ANTES de los gates de
        # inventario/presupuesto. Sin esto, un reinicio tras corte de luz ve
        # ledger vacío (inventario 0), marca su propia posición como "ajena"
        # y falla el gate de presupuesto aunque el equity total lo cubra.
        # Caso visto: libre 3999.54 + inventario 0 < 4900, con 0.0118 BTC
        # (~1018 USDT) en el exchange que sí era posición del bot.
        self._rebuild_ledger_from_audit()
        # Best-effort: adoptar fills que llegaron justo antes de la caída y aún
        # no están en la auditoría (no bloquea el arranque si falla la red).
        try:
            self.executor.poll_fills()
        except Exception:  # noqa: BLE001
            pass
        self._declare_residual(account)
        self._check_balance(account)

    def _rebuild_ledger_from_audit(self) -> int:
        """Restaura el ledger desde los fills persistidos (idempotente).

        El ledger vive solo en memoria; tras un reinicio arranca vacío aunque
        `audit.sqlite` (volumen `runs/`) conserve los fills. Sin esta
        reconstrucción, el gate de presupuesto calcula `disponible = libre + 0`
        y el inventario propio se declara "ajeno". Devuelve nº de fills
        (re)aplicados al ledger en este arranque.
        """
        try:
            rows = self.audit.fetch("fills", order_by="ts_ms, trade_id")
        except Exception:  # noqa: BLE001
            return 0
        adopted = 0
        for row in rows:
            try:
                fill = FillRecord(
                    symbol=str(row.get("symbol") or self.cfg.symbol),
                    trade_id=int(row["trade_id"]),
                    order_id=int(row.get("order_id") or 0),
                    client_order_id=str(row.get("client_order_id") or ""),
                    side=str(row.get("side") or ""),
                    price=Decimal(str(row.get("price") or "0")),
                    qty=Decimal(str(row.get("qty") or "0")),
                    quote_qty=Decimal(str(row.get("quote_qty") or "0")),
                    commission=Decimal(str(row.get("commission") or "0")),
                    commission_asset=str(row.get("commission_asset") or ""),
                    time_ms=int(row.get("ts_ms") or row.get("time_ms") or 0),
                    is_maker=bool(row.get("is_maker")),
                    source=str(row.get("source") or "audit"),
                )
            except Exception:  # noqa: BLE001
                continue
            try:
                if self.ledger.apply_fill(fill):
                    adopted += 1
            except Exception:  # noqa: BLE001
                # Fill corrupto o venta sin lote: no inventar contabilidad;
                # la conciliación posterior lo reportará como descuadre.
                continue
        if adopted:
            self.logger.info("ledger_reconstruido_desde_auditoria", fills=adopted,
                             inventario_btc=str(self.ledger.base_qty()))
        return adopted

    def _declare_residual(self, account: dict) -> None:
        balances = {b["asset"]: b for b in account.get("balances", [])}
        btc_free = Decimal(str(balances.get("BTC", {}).get("free", "0")))
        if btc_free <= 0:
            return
        # Descontar lo atribuible al bot (ledger ya reconstruido): solo el
        # excedente no explicado es residuo/ajeno. Antes se comparaba el total
        # contra 0 porque el ledger aún estaba vacío en el arranque.
        owned = self.ledger.base_qty()
        if owned < 0:
            owned = Decimal("0")
        unaccounted = btc_free - owned - self._declared_residual_qty
        if unaccounted <= 0:
            return
        try:
            bid = self.rest.bid_price(self.cfg.symbol)
            value = unaccounted * bid
        except Exception:  # noqa: BLE001
            value = Decimal("999999")
        if value < Decimal("5"):
            self._declared_residual_qty = self._declared_residual_qty + unaccounted
            self.logger.warning("residuo_declarado", asset="BTC", qty=str(unaccounted), valor_usdt=str(value))
            self.audit.record_incident(
                int(time.time() * 1000), "residuo_declarado_excluido", {"qty": str(unaccounted), "valor": str(value)}
            )
        else:
            self.logger.error("inventario_ajeno_al_iniciar", qty=str(unaccounted), valor_usdt=str(value),
                              inventario_propio=str(owned), btc_exchange=str(btc_free))
            self.audit.record_incident(
                int(time.time() * 1000), "inventario_ajeno",
                {"qty": str(unaccounted), "valor": str(value), "propio": str(owned)},
            )
            self.state.pause_entries("inventario_ajeno_al_iniciar")

    def _check_balance(self, account: dict) -> None:
        balances = {b["asset"]: b for b in account.get("balances", [])}
        free = Decimal(str(balances.get("USDT", {}).get("free", "0")))
        btc_free = Decimal(str(balances.get("BTC", {}).get("free", "0")))
        bid = Decimal("0")
        inventory_value = Decimal("0")
        if self.ledger.base_qty() > 0:
            bid = self.rest.bid_price(self.cfg.symbol)
            inventory_value = self.ledger.base_qty() * bid
        available = free + inventory_value
        if available < Decimal(str(self.cfg.budget_usdt)):
            # Diagnóstico: si el total del exchange sí cubre el presupuesto,
            # la diferencia es inventario no atribuido (ledger perdido o BTC
            # ajeno). Decirlo explícito evita el "no se ejecuta" sin contexto.
            total_hint = ""
            try:
                if bid <= 0:
                    bid = self.rest.bid_price(self.cfg.symbol)
                total_exchange = free + btc_free * bid
                total_hint = f" (total_exchange {total_exchange} con BTC {btc_free})"
            except Exception:  # noqa: BLE001
                pass
            raise StartupError(
                f"presupuesto {self.cfg.budget_usdt} > disponible {available} "
                f"(libre {free} + inventario {inventory_value}){total_hint}"
            )
        self.logger.info("gate_ok", paso="presupuesto", libre=str(free), inventario=str(inventory_value))

    def _startup_reconciliation(self) -> None:
        self._transition(RunState.RECONCILIANDO, "conciliación de arranque")
        adopted = self.executor.recover_fills_on_start()
        self._reconcile_inventory()
        self.status.mark_reconcile()
        self.logger.info(
            "conciliacion_arranque_ok",
            intenciones_pendientes=len(self.executor.open_intents()),
            fills=adopted,
        )

    def _reconcile_inventory(self) -> None:
        try:
            account = self.rest.account()
            balances = {b["asset"]: b for b in account.get("balances", [])}
            btc_free = Decimal(str(balances.get("BTC", {}).get("free", "0")))
        except (DemoRESTError, AmbiguousResult) as exc:
            self.logger.warning("inventario_no_conciliable", error=str(exc))
            return
        expected = self._declared_residual_qty + self.ledger.base_qty()
        diff = btc_free - expected
        tolerance = self.rest.get_filters(self.cfg.symbol).step_size
        if abs(diff) > tolerance:
            self.logger.error("descuadre_de_inventario", esperado=str(expected), observado=str(btc_free), diff=str(diff))
            self.audit.record_incident(
                int(time.time() * 1000), "descuadre_inventario",
                {"esperado": str(expected), "observado": str(btc_free), "diff": str(diff)},
            )
            self.state.pause_entries("descuadre_de_inventario")
        else:
            self.logger.info("inventario_conciliado", qty=str(btc_free), residuo=str(self._declared_residual_qty))

    # ------------------------------------------------------------------ nodo
    def _start_node(self) -> None:
        self._transition(RunState.CALENTANDO, "nodo iniciado")
        self._node = build_node(self.cfg, self.secrets, self._ctx)
        self._handle = self._node.handle()
        self.logger.info("nodo_nautilus_lanzado", bar_type=self.cfg.bar_type)

    def _request_node_stop(self) -> None:
        try:
            if self._handle is not None:
                self.logger.info("deteniendo_nodo")
                self._handle.stop()
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("parada_de_nodo_con_error", error=repr(exc))

    def _node_running(self) -> bool:
        if self._handle is None:
            return False
        try:
            state = self._handle.state
        except Exception:  # noqa: BLE001
            return True
        if NodeState is None:
            return True
        return state == NodeState.RUNNING

    # ------------------------------------------------------------------ bucle principal
    def _main_loop(self) -> None:
        last_heartbeat = 0.0
        self._last_heartbeat_log = 0.0
        self._last_poll_ms = 0.0
        self._last_reconcile_ms = 0.0
        started_wall = time.time()
        node_start_grace_s = 90
        while not self._stop_event.is_set():
            now = time.time()
            running = self._node_running()
            if running:
                self._node_seen_running = True
            if now - last_heartbeat >= 5:
                last_heartbeat = now
                self.lock.heartbeat()
                self._poll_control()
                self._maybe_promote_to_executing()
                self._check_stale_pending()
            if now - self._last_poll_ms >= 10:
                self._last_poll_ms = now
                self._poll_fills()
            if now - self._last_reconcile_ms >= 30:
                self._last_reconcile_ms = now
                self._reconcile_intents()
            if now * 1000 - self._last_equity_ms >= self._tolerances.equity_interval_s * 1000:
                self._equity_snapshot()
            if now - self._last_heartbeat_log >= self._tolerances.heartbeat_log_s:
                self._heartbeat_log()
            if self._node_seen_running or (now - started_wall) > node_start_grace_s:
                self._health_cycle()
            if not running and not self._stop_event.is_set():
                if self._node_seen_running or (now - started_wall) > node_start_grace_s:
                    self.logger.critical(
                        "nodo_detenido_inesperadamente", vio_correr=self._node_seen_running
                    )
                    self.audit.record_incident(int(time.time() * 1000), "nodo_detenido_inesperadamente", {})
                    self._exit_code = 1
                    self._stop_event.set()
            self._stop_event.wait(2)
        self._request_node_stop()
        if self._close_request_ms is not None and not self._close_ack_sent:
            self._finalize_close_request()

    def _poll_fills(self) -> None:
        adopted = self.executor.poll_fills()
        if adopted:
            self.status.mark_private_event()
            self.logger.info("fills_nuevos", cantidad=adopted)
        if self.executor.last_error:
            self.logger.warning("poll_fills_degradado", error=self.executor.last_error[:200])

    def _reconcile_intents(self) -> None:
        if not self.executor.open_intents():
            return
        resolved = self.executor.reconcile_open_intents()
        if resolved:
            self.status.mark_reconcile()
            self.logger.info("intenciones_conciliadas", cantidad=resolved)

    def _heartbeat_log(self) -> None:
        """Latido periódico: deja claro en el log que el bot está vivo y qué espera."""
        self._last_heartbeat_log = time.time()
        snapshot = self.status.snapshot()
        last_equity = self.audit.last_equity()
        next_close = None
        if snapshot["last_bar_close_ms"]:
            next_close = snapshot["last_bar_close_ms"] + self._interval_ms
        self.logger.info(
            "latido",
            estado=self.state.state.value,
            salud=self.health_status,
            barras=snapshot["bars_seen"],
            senales=snapshot["signals_evaluated"],
            senal_objetivo=snapshot["signal_state"],
            ordenes=snapshot["orders_submitted"],
            fills=snapshot["fills_applied"],
            ultima_vela=utc_iso(snapshot["last_bar_close_ms"]) if snapshot["last_bar_close_ms"] else "n/a",
            proxima_vela=utc_iso(next_close) if next_close else "n/a",
            equity=str(last_equity["equity"]) if last_equity else "n/a",
            inventario_btc=str(last_equity["base_qty"]) if last_equity else "n/a",
            pendiente=self._pending_summary(),
        )

    def _pending_summary(self) -> str:
        return "si" if self.status.snapshot()["orders_submitted"] else "no"

    def _maybe_promote_to_executing(self) -> None:
        if self.state.state != RunState.CALENTANDO:
            return
        if self.status.bars_seen < self.cfg.strategy_params.warmup_bars:
            return
        if self.state.entries_paused:
            self._transition(RunState.ENTRADAS_PAUSADAS, "arranque con pausa persistida")
        else:
            self._transition(RunState.EJECUTANDO, "calentamiento completado")
        self.logger.info("listo_para_operar", barras=self.status.bars_seen, salud=self.health_status)

    def _health_cycle(self) -> None:
        snapshot = self.status.snapshot()
        now_ms = int(time.time() * 1000)
        node_running = self._node_running()
        self.status.set_connections(node=node_running)
        if not node_running:
            report_status, reasons = "SIN_CONEXION", ["nodo_no_conectado"]
        else:
            report = evaluate_freshness(
                now_ms=now_ms,
                last_bar_close_ms=snapshot["last_bar_close_ms"],
                last_quote_ms=snapshot["last_quote_ms"],
                last_private_event_ms=snapshot["last_private_event_ms"],
                tolerances=self._tolerances,
                private_required=False,
                interval_ms=self._interval_ms,
            )
            report_status = report.status.value
            reasons = list(report.reasons)
        if self.executor.last_error:
            report_status, reasons = "ESTADO_INCIERTO", reasons + ["conciliacion_degradada"]
        if snapshot["last_error"]:
            report_status, reasons = "ESTADO_INCIERTO", reasons + ["error_de_nodo"]
        if report_status != self._last_health:
            self._last_health = report_status
            self.health_status = report_status
            self.audit.record_health(now_ms, report_status, reasons)
            self.audit.record_state(now_ms, self.state.state.value, self.state.state.value, f"salud={report_status}")
            log = self.logger.warning if report_status != "SALUDABLE" else self.logger.info
            log("salud", estado=report_status, motivos=",".join(reasons), barras=snapshot["bars_seen"])

    def _check_stale_pending(self) -> None:
        if self.status.orders_submitted == 0:
            return
        if self.status.last_private_event_ms is None:
            return
        age_s = (int(time.time() * 1000) - self.status.last_private_event_ms) / 1000
        if age_s > 600:
            self.audit.record_incident(int(time.time() * 1000), "canal_privado_silencioso", {"age_s": age_s})
            self.status.mark_private_event()

    def _equity_snapshot(self) -> None:
        self._last_equity_ms = int(time.time() * 1000)
        try:
            account = self.rest.account()
            balances = {b["asset"]: b for b in account.get("balances", [])}
            usdt = balances.get("USDT", {"free": "0", "locked": "0"})
            btc = balances.get("BTC", {"free": "0", "locked": "0"})
            bid = self.rest.bid_price(self.cfg.symbol) if self.ledger.base_qty() > 0 else None
            self.audit.record_balance(self._last_equity_ms, "USDT", str(usdt["free"]), str(usdt["locked"]), "exchange")
            self.audit.record_balance(self._last_equity_ms, "BTC", str(btc["free"]), str(btc["locked"]), "exchange")
        except (DemoRESTError, AmbiguousResult) as exc:
            self.logger.warning("snapshot_sin_exchange", error=str(exc))
            bid = None
        budget = Decimal(str(self.cfg.budget_usdt))
        cash_assigned = budget + self.ledger.quote_cash()
        eq = self.ledger.equity(
            budget_usdt=budget,
            cash_free_usdt=cash_assigned,
            cash_reserved_usdt=Decimal("0"),
            base_price_usdt=bid,
        )
        snapshot = {
            "ts_ms": self._last_equity_ms,
            "budget": budget,
            "cash_free": eq.cash_free_usdt,
            "cash_reserved": eq.cash_reserved_usdt,
            "base_qty": eq.base_qty,
            "base_price": eq.base_price_usdt,
            "inventory_value": eq.inventory_value_usdt,
            "pending_costs": eq.pending_costs_usdt,
            "equity": eq.equity_usdt,
            "complete": eq.complete,
            "notes": eq.notes,
            "source": "supervisor",
        }
        self.audit.record_equity(snapshot)
        self.logger.info(
            "patrimonio",
            equity=str(eq.equity_usdt),
            efectivo_asignado=str(eq.cash_free_usdt),
            inventario_btc=str(eq.base_qty),
            valor_inventario=str(eq.inventory_value_usdt),
            completo=eq.complete,
        )

    # ------------------------------------------------------------------ control
    def _poll_control(self) -> None:
        request = self.control.pending()
        if request is None:
            return
        action = request["action"]
        self.logger.info("control_recibido", accion=action, request_id=request["request_id"])
        try:
            if action == "pause":
                self.state.pause_entries(request.get("params", {}).get("reason", "solicitud_del_operador"))
                if self.state.state == RunState.EJECUTANDO:
                    self._transition(RunState.ENTRADAS_PAUSADAS, "pausa solicitada")
                self.logger.info("control_aplicado", accion=action, estado=self.state.state.value)
                self.control.ack(request["request_id"], "entradas pausadas")
            elif action == "resume":
                self.state.resume_entries()
                if self.state.state == RunState.ENTRADAS_PAUSADAS and self.health_status == "SALUDABLE":
                    self._transition(RunState.EJECUTANDO, "reanudación solicitada")
                self.logger.info("control_aplicado", accion=action, estado=self.state.state.value)
                self.control.ack(request["request_id"], "entradas reanudadas")
            elif action in ("close_position", "close_all"):
                self.control_action = action
                self._close_request_ms = int(time.time() * 1000)
                self._close_ack_sent = False
                if self.state.state in (RunState.EJECUTANDO, RunState.ENTRADAS_PAUSADAS):
                    self._transition(RunState.CERRANDO, f"solicitud {action}")
                self.control.ack(request["request_id"], "cierre solicitado; se confirmará al liquidar")
            elif action == "stop":
                self.control.ack(request["request_id"], "parada solicitada")
                self._stop_event.set()
            elif action == "export":
                manifest = self._export()
                self.control.ack(request["request_id"], f"export {manifest['export_id']}")
            elif action == "status":
                snapshot = self.status.snapshot()
                message = (
                    f"estado={self.state.state.value} salud={self.health_status} "
                    f"barras={snapshot['bars_seen']} fills={snapshot['fills_applied']} "
                    f"equity={self.audit.last_equity()['equity'] if self.audit.last_equity() else 'n/a'}"
                )
                self.control.ack(request["request_id"], message)
            else:
                self.control.reject(request["request_id"], f"acción desconocida: {action}")
        except Exception as exc:  # noqa: BLE001
            self.logger.error("control_fallido", accion=action, error=repr(exc))
            self.control.reject(request["request_id"], repr(exc))
        if self._close_request_ms is not None and not self._close_ack_sent:
            self._finalize_close_request()

    def _finalize_close_request(self) -> None:
        if self.ledger.base_qty() <= 0:
            self._close_ack_sent = True
            self._close_request_ms = None
            residual = self._declared_residual_qty
            target = RunState.FINALIZADA if residual <= 0 else RunState.FINALIZADA_CON_RESIDUO
            if self.state.state in (RunState.CERRANDO, RunState.EJECUTANDO, RunState.ENTRADAS_PAUSADAS):
                self._transition(target, "cierre confirmado sin inventario atribuible")
            self.logger.info("cierre_confirmado", estado=target.value)
        elif self._close_request_ms and (int(time.time() * 1000) - self._close_request_ms) > 600_000:
            self.logger.error("cierre_no_confirmado_en_10min")
            self.audit.record_incident(int(time.time() * 1000), "cierre_no_confirmado", {})

    # ------------------------------------------------------------------ fills / señales
    def handle_fill(self, fill: FillRecord) -> None:
        """Compatibilidad (tests): aplica un fill confirmado vía el ejecutor."""
        self.executor.apply_fill_record(fill)

    def handle_signal(self, decision: SignalDecision) -> None:
        pass

    # ------------------------------------------------------------------ cierre
    def _transition(self, to: RunState, reason: str) -> None:
        try:
            self.state.transition(to, reason)
        except InvalidTransition as exc:
            self.logger.warning("transicion_invalida", destino=to.value, error=str(exc))
            return
        self.audit.record_state(int(time.time() * 1000), self.state.state.value, to.value, reason)
        self.logger.info("estado", estado=to.value, motivo=reason)

    def _export(self) -> dict:
        metrics = compute_metrics(
            snapshots=[{"ts_ms": int(r["ts_ms"]), "equity": Decimal(str(r["equity"]))} for r in self.audit.fetch("equity")],
            trades=[
                {"closed": bool(r["closed"]), "pnl": r["pnl"], "duration_s": r["duration_s"], "exposure_s": r["exposure_s"]}
                for r in self.audit.fetch("trades")
            ],
            initial_equity=Decimal(str(self.cfg.budget_usdt)),
        )
        return export_run(
            self.audit,
            self.cfg,
            self.cfg.exports_dir,
            metrics=metrics,
            state=self.state.state.value,
            health=self.health_status,
        )

    def _shutdown(self) -> None:
        try:
            if self._node is not None and self._node_running():
                self._request_node_stop()
            if self.state.state not in (RunState.FINALIZADA, RunState.FINALIZADA_CON_RESIDUO, RunState.INTERRUMPIDA):
                self._transition(RunState.DETENIDO, "proceso finalizado")
            manifest = self._export()
            self.logger.info("export_final", export_id=manifest["export_id"], archivos=len(manifest["files"]))
        except Exception as exc:  # noqa: BLE001
            self.logger.error("export_final_fallido", error=repr(exc))
        finally:
            self.lock.release()
            self.audit.close()
            self.logger.close()

    def request_stop(self) -> None:
        self._stop_event.set()


def _fill_to_row(fill: FillRecord) -> dict:
    return {
        "symbol": fill.symbol, "trade_id": fill.trade_id, "order_id": fill.order_id,
        "client_order_id": fill.client_order_id, "time_ms": fill.time_ms, "side": fill.side,
        "price": fill.price, "qty": fill.qty, "quote_qty": fill.quote_qty,
        "commission": fill.commission, "commission_asset": fill.commission_asset,
        "is_maker": fill.is_maker, "source": fill.source,
    }


def _git_commit() -> str | None:
    try:
        import subprocess

        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=Path(__file__).resolve().parents[2],
        )
        return out.stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def load_env_file(path: Path) -> None:
    """Carga un .env local (baked en la imagen) sin sobrescribir variables ya definidas."""
    import os

    if not path.exists():
        return
    # utf-8-sig: tolera archivos guardados con BOM (Notepad Windows). Sin esto,
    # el BOM se pega a la primera clave ('\ufeffBINANCE_DEMO_API_KEY') y nunca
    # coincide con os.environ.get('BINANCE_DEMO_API_KEY'). Ver auditoría 2.0.1.
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip().lstrip("\ufeff")
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip().lstrip("\ufeff"), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1].strip()
        if key and key not in os.environ:
            os.environ[key] = value


def main(argv: list[str] | None = None) -> int:
    import os

    parser = argparse.ArgumentParser(description="Bot E2-A en Binance DEMO")
    parser.add_argument("--config", default=os.environ.get("BOT_CONFIG"), help="ruta a YAML de configuración")
    parser.add_argument("--run-id", default=None, help="identificador de la prueba")
    parser.add_argument("--variant", default=None, choices=["PSO", "A2"])
    parser.add_argument("--budget", type=float, default=None)
    parser.add_argument("--quiet", action="store_true", help="sin eco a consola (solo JSONL)")
    parser.add_argument("--run-for-seconds", type=int, default=None, help="detención ordenada tras N segundos (pruebas)")
    args = parser.parse_args(argv)

    load_env_file(Path(__file__).resolve().parents[1] / ".env")
    run_id = args.run_id or os.environ.get("BOT_RUN_ID") or f"run-{time.strftime('%Y%m%d-%H%M%S')}"
    cfg = BotConfig.load(args.config, run_id=run_id, strategy_variant=args.variant, budget_usdt=args.budget)
    secrets = Secrets.from_env()
    supervisor = Supervisor(cfg, secrets, echo_logs=not args.quiet)

    def _handler(signum, _frame):
        supervisor.logger.warning("senal_recibida", senal=signum)
        supervisor.request_stop()

    signal.signal(signal.SIGINT, _handler)
    try:
        signal.signal(signal.SIGTERM, _handler)
    except Exception:  # noqa: BLE001
        pass
    if args.run_for_seconds:
        timer = threading.Timer(args.run_for_seconds, supervisor.request_stop)
        timer.daemon = True
        timer.start()
    return supervisor.run()


if __name__ == "__main__":
    raise SystemExit(main())
