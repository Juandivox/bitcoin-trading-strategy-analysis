"""Tipos compartidos entre módulos del bot (contratos internos)."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class RunState(str, Enum):
    BORRADOR = "BORRADOR"
    VALIDANDO = "VALIDANDO"
    RECONCILIANDO = "RECONCILIANDO"
    CALENTANDO = "CALENTANDO"
    EJECUTANDO = "EJECUTANDO"
    ENTRADAS_PAUSADAS = "ENTRADAS_PAUSADAS"
    CERRANDO = "CERRANDO"
    DETENIDO = "DETENIDO"
    FINALIZADA = "FINALIZADA"
    FINALIZADA_CON_RESIDUO = "FINALIZADA_CON_RESIDUO"
    INTERRUMPIDA = "INTERRUMPIDA"


class Health(str, Enum):
    SALUDABLE = "SALUDABLE"
    DATOS_DEGRADADOS = "DATOS_DEGRADADOS"
    SIN_CONEXION = "SIN_CONEXION"
    CANAL_PRIVADO_DEGRADADO = "CANAL_PRIVADO_DEGRADADO"
    ESTADO_INCIERTO = "ESTADO_INCIERTO"
    ERROR_PERSISTENCIA = "ERROR_PERSISTENCIA"
    ERROR_CONFIGURACION = "ERROR_CONFIGURACION"
    PROCESO_CAIDO = "PROCESO_CAIDO"


@dataclass(frozen=True)
class FillRecord:
    """Un fill confirmado, tal como lo reporta el exchange o la conciliación."""

    symbol: str
    trade_id: int
    order_id: int
    client_order_id: str
    side: str
    price: Decimal
    qty: Decimal
    quote_qty: Decimal
    commission: Decimal
    commission_asset: str
    time_ms: int
    is_maker: bool
    source: str


@dataclass(frozen=True)
class SignalDecision:
    """Resultado de evaluar una vela cerrada."""

    bar_close_ms: int
    bar_close_price: float
    target_position: int
    prev_state: int
    action: str
    reason: str
    cci: float
    sma_fast: float
    sma_slow: float
    vol_z: float
    entry_event: bool
    exit_event: bool


@dataclass(frozen=True)
class OrderIntent:
    """Intención de orden persistida ANTES de despachar (RF-ORD-03)."""

    key: str
    symbol: str
    side: str
    quantity: Decimal
    quote_estimate: Decimal
    bar_close_ms: int
    action: str
    created_ms: int


@dataclass(frozen=True)
class HealthReport:
    status: Health
    reasons: list[str] = field(default_factory=list)
    ts_ms: int = 0


@dataclass(frozen=True)
class EquityBreakdown:
    """Patrimonio de la prueba (spec §15.2), en USDT."""

    budget_usdt: Decimal
    cash_free_usdt: Decimal
    cash_reserved_usdt: Decimal
    base_qty: Decimal
    base_price_usdt: Decimal
    inventory_value_usdt: Decimal
    pending_costs_usdt: Decimal
    equity_usdt: Decimal
    complete: bool
    notes: list[str] = field(default_factory=list)
