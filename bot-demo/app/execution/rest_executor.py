"""Ejecución por REST contra Binance DEMO (decisión documentada en docs/ACEPTACION.md).

Motivo: el entorno DEMO de Binance rechaza claves HMAC-SHA256 en su WebSocket API
privada (code=-2028), por lo que el cliente de ejecución de NautilusTrader rc5 no
puede autenticar el canal privado. NautilusTrader se mantiene para datos, barras y
señales; las órdenes y los fills confirmados se gestionan aquí con las garantías del
spec: intención persistida ANTES de despachar, sin reintentos ciegos, conciliación
explícita y contabilidad por fills confirmados.
"""
from __future__ import annotations

import threading
import time
from decimal import Decimal
from typing import Any

from app.accounting.ledger import Ledger
from app.audit.db import AuditDB
from app.audit.logs import Logger
from app.config import BotConfig
from app.contracts import FillRecord
from app.exchange.demo_rest import (
    AmbiguousResult,
    DemoRESTClient,
    DemoRESTError,
    floor_to_step,
)

TERMINAL = ("FILLED", "CANCELED", "EXPIRED", "REJECTED")
LIVE_INTENT = ("PENDING", "UNKNOWN", "ACCEPTED", "PARTIALLY_FILLED", "NEW")


class RestExecutor:
    def __init__(self, cfg: BotConfig, rest: DemoRESTClient, audit: AuditDB,
                 logger: Logger, ledger: Ledger) -> None:
        self.cfg = cfg
        self.rest = rest
        self.audit = audit
        self.logger = logger
        self.ledger = ledger
        self._lock = threading.Lock()
        self._order_index: dict[int, str] = {}
        self._intent_status: dict[str, str] = {}
        self._episode: dict | None = None
        self.last_poll_ms: int | None = None
        self.last_error: str | None = None
        self._seen_foreign_orders: set[int] = set()
        self._load_index()

    # ------------------------------------------------------------------ intenciones
    def intent_key(self, action: str, bar_close_ms: int) -> str:
        run_part = "".join(ch for ch in self.cfg.run_id if ch.isalnum() or ch == "-")[:10]
        return f"e2a-{run_part}-{action.lower()}-{bar_close_ms}"[:36]

    _intent_key = intent_key

    def _load_index(self) -> None:
        for row in self.audit.fetch("order_intents"):
            key = row.get("key")
            if not key:
                continue
            self._intent_status[key] = row.get("status") or "UNKNOWN"
            if row.get("order_id"):
                self._order_index[int(row["order_id"])] = key

    def intent_status(self, key: str) -> str | None:
        with self._lock:
            return self._intent_status.get(key)

    def open_intents(self) -> list[str]:
        with self._lock:
            return [k for k, s in self._intent_status.items() if s not in TERMINAL]

    # ------------------------------------------------------------------ envío
    def submit_market(self, *, action: str, side: str, bar_close_ms: int,
                      quantity: Decimal | None = None, quote_notional: Decimal | None = None,
                      price_estimate: Decimal | None = None) -> str:
        """Envía una orden de mercado con clave idempotente. Devuelve el estado."""
        key = self._intent_key(action, bar_close_ms)
        with self._lock:
            current = self._intent_status.get(key)
        if current is not None:
            self.logger.warning("intencion_duplicada", clave=key, estado=current)
            return "DUPLICADA"
        quantity = Decimal(quantity) if quantity is not None else None
        quote_notional = Decimal(quote_notional) if quote_notional is not None else None
        intent = {
            "key": key,
            "created_ms": int(time.time() * 1000),
            "symbol": self.cfg.symbol,
            "side": side.upper(),
            "quantity": quantity if quantity is not None else Decimal("0"),
            "quote_estimate": quote_notional if quote_notional is not None else (quantity or Decimal("0")) * (price_estimate or Decimal("0")),
            "bar_close_ms": bar_close_ms,
            "action": action,
            "status": "PENDING",
            "client_order_id": key,
        }
        self.audit.record_intent(intent)  # RF-ORD-03: persistir ANTES de despachar
        with self._lock:
            self._intent_status[key] = "PENDING"
        self.logger.info(
            "orden_intent", accion=action, lado=intent["side"],
            cantidad=str(quantity) if quantity is not None else None,
            quote=str(quote_notional) if quote_notional is not None else None, clave=key,
        )
        try:
            response = self.rest.place_market_order(
                self.cfg.symbol, intent["side"], quantity=quantity,
                quote_order_qty=quote_notional, client_order_id=key,
            )
        except AmbiguousResult as exc:
            self._update_intent(key, "UNKNOWN", message=str(exc)[:200])
            self.logger.warning("orden_resultado_incierto", clave=key, error=str(exc)[:200])
            return "UNKNOWN"
        except DemoRESTError as exc:
            self._update_intent(key, "REJECTED", message=f"code={exc.code}: {exc}"[:200])
            self.logger.error("orden_rechazada_por_exchange", clave=key, code=exc.code, detalle=str(exc)[:200])
            return "REJECTED"
        return self._handle_response(key, response)

    def _handle_response(self, key: str, response: dict[str, Any]) -> str:
        order_id = int(response.get("orderId", 0) or 0)
        status = str(response.get("status", "UNKNOWN")).upper()
        self.audit.record_order(
            {
                "client_order_id": key,
                "order_id": order_id,
                "ts_ms": int(response.get("transactTime", time.time() * 1000)),
                "symbol": self.cfg.symbol,
                "side": str(response.get("side", "")),
                "order_type": str(response.get("type", "MARKET")),
                "quantity": response.get("origQty", ""),
                "status": status,
                "filled_qty": response.get("executedQty", ""),
                "avg_price": response.get("cummulativeQuoteQty", ""),
                "raw": response,
            }
        )
        if order_id:
            with self._lock:
                self._order_index[order_id] = key
        adopted = self._adopt_fills_for_order(order_id, key)
        self._update_intent(key, status, order_id=order_id,
                            message=f"executed={response.get('executedQty')}")
        self.logger.info(
            "orden_respuesta", clave=key, estado=status, order_id=order_id,
            ejecutado=str(response.get("executedQty")), quote=str(response.get("cummulativeQuoteQty")),
            fills_adoptados=adopted,
        )
        return status

    def _update_intent(self, key: str, status: str, order_id: int | None = None,
                       message: str | None = None) -> None:
        with self._lock:
            self._intent_status[key] = status
        row = next((r for r in self.audit.fetch("order_intents") if r.get("key") == key), None)
        if row is None:
            return
        self.audit.record_intent(
            {
                **row,
                "status": status,
                "order_id": order_id if order_id is not None else row.get("order_id"),
                "client_order_id": key,
                "message": message,
            }
        )

    # ------------------------------------------------------------------ conciliación
    def _adopt_fills_for_order(self, order_id: int, client_order_id: str) -> int:
        if not order_id:
            return 0
        try:
            trades = self.rest.my_trades(self.cfg.symbol, limit=200)
        except (DemoRESTError, AmbiguousResult) as exc:
            self.last_error = f"my_trades: {exc}"
            return 0
        adopted = 0
        for trade in trades:
            if int(trade.get("orderId", 0)) != order_id:
                continue
            if self._apply_trade(trade, client_order_id):
                adopted += 1
        return adopted

    def _apply_trade(self, trade: dict, client_order_id: str) -> bool:
        fill = FillRecord(
            symbol=self.cfg.symbol,
            trade_id=int(trade["id"]),
            order_id=int(trade["orderId"]),
            client_order_id=client_order_id,
            side="BUY" if trade.get("isBuyer") else "SELL",
            price=Decimal(str(trade["price"])),
            qty=Decimal(str(trade["qty"])),
            quote_qty=Decimal(str(trade["quoteQty"])),
            commission=Decimal(str(trade["commission"])),
            commission_asset=str(trade["commissionAsset"]),
            time_ms=int(trade["time"]),
            is_maker=bool(trade.get("isMaker")),
            source="poll",
        )
        return self.apply_fill_record(fill)

    def apply_fill_record(self, fill: FillRecord) -> bool:
        """Aplica un fill confirmado: ledger + auditoría + episodio (idempotente)."""
        if not self.ledger.apply_fill(fill):
            return False
        self.audit.record_fill(
            {
                "symbol": fill.symbol, "trade_id": fill.trade_id, "order_id": fill.order_id,
                "client_order_id": fill.client_order_id, "time_ms": fill.time_ms,
                "side": fill.side, "price": fill.price, "qty": fill.qty,
                "quote_qty": fill.quote_qty, "commission": fill.commission,
                "commission_asset": fill.commission_asset, "is_maker": fill.is_maker,
                "source": fill.source,
            }
        )
        self.logger.info(
            "fill_confirmado", trade_id=fill.trade_id, lado=fill.side, qty=str(fill.qty),
            precio=str(fill.price), comision=str(fill.commission),
            activo_comision=fill.commission_asset, origen=fill.source,
        )
        self._track_episode(fill)
        self.last_poll_ms = int(time.time() * 1000)
        return True

    def poll_fills(self) -> int:
        """Recupera fills confirmados de NUESTRAS órdenes (idempotente por trade_id)."""
        try:
            trades = self.rest.my_trades(self.cfg.symbol, limit=200)
        except (DemoRESTError, AmbiguousResult) as exc:
            self.last_error = f"poll_fills: {exc}"
            self.logger.warning("poll_fills_fallido", error=str(exc)[:200])
            return 0
        adopted = 0
        with self._lock:
            index = dict(self._order_index)
        for trade in trades:
            order_id = int(trade.get("orderId", 0))
            key = index.get(order_id)
            if key is None:
                if order_id and order_id not in self._seen_foreign_orders:
                    self._seen_foreign_orders.add(order_id)
                    self.logger.warning("trade_ajeno_ignorado", order_id=order_id)
                continue
            if self._apply_trade(trade, key):
                adopted += 1
        self.last_poll_ms = int(time.time() * 1000)
        self.last_error = None
        return adopted

    def reconcile_open_intents(self) -> int:
        """Resuelve intenciones PENDING/UNKNOWN consultando el exchange (nunca reenvía)."""
        resolved = 0
        for key in self.open_intents():
            try:
                info = self.rest.query_order(self.cfg.symbol, client_order_id=key)
            except (DemoRESTError, AmbiguousResult) as exc:
                self.last_error = f"reconcile: {exc}"
                self.logger.warning("intencion_no_conciliable", clave=key, error=str(exc)[:200])
                continue
            status = str(info.get("status", "UNKNOWN")).upper()
            order_id = int(info.get("orderId", 0) or 0)
            if order_id:
                with self._lock:
                    self._order_index[order_id] = key
            adopted = self._adopt_fills_for_order(order_id, key)
            self._update_intent(key, status, order_id=order_id, message="reconciliado")
            self.audit.record_order_event(int(time.time() * 1000), key, f"RECONCILIADO_{status}", info)
            self.logger.info("intencion_conciliada", clave=key, estado=status, fills_adoptados=adopted)
            resolved += 1
        return resolved

    def recover_fills_on_start(self) -> int:
        """Recupera fills confirmados durante caídas (CA-22) sin inventar ejecuciones."""
        adopted = self.poll_fills()
        self.reconcile_open_intents()
        if adopted:
            self.logger.info("fills_recuperados_en_arranque", cantidad=adopted)
        return adopted

    # ------------------------------------------------------------------ episodios
    def _track_episode(self, fill: FillRecord) -> None:
        if self.ledger.base_qty() > 0 and self._episode is None:
            self._episode = {
                "entry_ts_ms": fill.time_ms,
                "entry_qty": Decimal("0"),
                "entry_cost": Decimal("0"),
                "pnl_start": self.ledger.realized_pnl(),
            }
        if self._episode is not None and fill.side == "BUY":
            net = fill.qty - (fill.commission if fill.commission_asset == "BTC" else Decimal("0"))
            self._episode["entry_qty"] += net
            self._episode["entry_cost"] += fill.quote_qty + (
                fill.commission if fill.commission_asset == "USDT" else Decimal("0")
            )
        if self._episode is not None and self.ledger.base_qty() <= 0:
            episode = self._episode
            pnl = self.ledger.realized_pnl() - episode["pnl_start"]
            duration_s = (fill.time_ms - episode["entry_ts_ms"]) / 1000
            entry_avg = episode["entry_cost"] / episode["entry_qty"] if episode["entry_qty"] > 0 else Decimal("0")
            self.audit.record_trade(
                {
                    "symbol": self.cfg.symbol,
                    "entry_ts_ms": episode["entry_ts_ms"],
                    "exit_ts_ms": fill.time_ms,
                    "entry_qty": episode["entry_qty"],
                    "entry_avg_px": entry_avg,
                    "exit_avg_px": fill.price,
                    "pnl": pnl,
                    "fees": {k: str(v) for k, v in self.ledger.fees_by_asset().items()},
                    "closed": True,
                    "duration_s": duration_s,
                    "exposure_s": duration_s,
                }
            )
            self.logger.info("operacion_cerrada", pnl=str(pnl), duracion_s=round(duration_s, 1))
            self._episode = None
