"""Salud y frescura de datos (spec v2.0 §13, RF-DAT-05, RF-MON-03).

Funciones **puras** (sin reloj, sin I/O) para poder testearlas de forma
determinista. Regla crítica del spec: una vela de 4 h **no** es obsoleta solo
porque no hubo un cierre reciente. Se mide:

1. Si está presente la **última vela cerrada esperada** (tolerancia de
   publicación ``candle_publish_s`` = 60 s tras el cierre) -> si falta,
   ``DATOS_DEGRADADOS`` con motivo ``vela_esperada_ausente``.
2. La **frescura de la cotización** (``quote_max_age_s`` = 30 s) -> si se
   supera, ``DATOS_DEGRADADOS`` con motivo ``cotizacion_obsoleta``.
3. La **frescura del canal privado** (60 s, si ``private_required``) ->
   ``CANAL_PRIVADO_DEGRADADO`` con motivo ``canal_privado_obsoleto``.
4. Sin ningún dato público -> ``SIN_CONEXION`` con motivo ``sin_datos``.

``should_block_entries`` es ``True`` para cualquier estado distinto de
``SALUDABLE``.
"""
from __future__ import annotations

from typing import Any

from app.contracts import Health, HealthReport

__all__ = [
    "PRIVATE_EVENT_MAX_AGE_S",
    "REASON_BAR_MISSING",
    "REASON_NO_DATA",
    "REASON_PRIVATE_STALE",
    "REASON_QUOTE_STALE",
    "evaluate_freshness",
    "expected_last_closed_bar_close_ms",
    "should_block_entries",
]

REASON_BAR_MISSING = "vela_esperada_ausente"
REASON_QUOTE_STALE = "cotizacion_obsoleta"
REASON_PRIVATE_STALE = "canal_privado_obsoleto"
REASON_NO_DATA = "sin_datos"

PRIVATE_EVENT_MAX_AGE_S = 60

DEFAULT_CANDLE_PUBLISH_S = 60
DEFAULT_QUOTE_MAX_AGE_S = 30


def expected_last_closed_bar_close_ms(now_ms: int, interval_ms: int) -> int:
    """Cierre (ms) de la última vela que debería estar cerrada en ``now_ms``.

    Las velas están alineadas a UTC: ``floor(now / interval) * interval - 1``.
    """
    interval = int(interval_ms)
    if interval <= 0:
        raise ValueError("interval_ms debe ser > 0")
    now = int(now_ms)
    return (now // interval) * interval - 1


def _tolerance_s(tolerances: Any, name: str, default: int) -> int:
    value = getattr(tolerances, name, None)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):  # pragma: no cover - tolerancias no numéricas
        return default


def _resolve_interval_ms(interval_ms: int | None, tolerances: Any) -> int | None:
    candidate = interval_ms if interval_ms is not None else getattr(tolerances, "bar_interval_ms", None)
    if candidate is None:
        return None
    try:
        value = int(candidate)
    except (TypeError, ValueError):  # pragma: no cover - valor no numérico
        return None
    return value if value > 0 else None


def _is_stale(now_ms: int, ts_ms: int | None, max_age_s: int) -> bool:
    if ts_ms is None:
        return True
    return (int(now_ms) - int(ts_ms)) > max_age_s * 1000


def evaluate_freshness(
    now_ms: int,
    last_bar_close_ms: int | None,
    last_quote_ms: int | None,
    last_private_event_ms: int | None,
    tolerances: Any,
    private_required: bool = True,
    *,
    interval_ms: int | None = None,
) -> HealthReport:
    """Evalúa la frescura de los canales y devuelve un ``HealthReport``.

    ``last_bar_close_ms`` es el cierre de la última vela que el bot **tiene**.
    ``interval_ms`` es el intervalo de la vela en curso (4 h -> 14_400_000); si
    no se pasa, se intenta leer de ``tolerances.bar_interval_ms``. Sin intervalo
    no es posible saber cuál es la vela esperada y solo se evalúan cotización y
    canal privado.
    """
    now = int(now_ms)
    candle_publish_s = _tolerance_s(tolerances, "candle_publish_s", DEFAULT_CANDLE_PUBLISH_S)
    quote_max_age_s = _tolerance_s(tolerances, "quote_max_age_s", DEFAULT_QUOTE_MAX_AGE_S)
    private_max_age_s = _tolerance_s(
        tolerances, "private_event_max_age_s", PRIVATE_EVENT_MAX_AGE_S
    )

    has_public_data = last_bar_close_ms is not None or last_quote_ms is not None
    if not has_public_data:
        return HealthReport(status=Health.SIN_CONEXION, reasons=[REASON_NO_DATA], ts_ms=now)

    reasons: list[str] = []

    if _is_stale(now, last_quote_ms, quote_max_age_s):
        reasons.append(REASON_QUOTE_STALE)

    interval = _resolve_interval_ms(interval_ms, tolerances)
    if interval is not None:
        expected_close = expected_last_closed_bar_close_ms(now, interval)
        bar_missing = last_bar_close_ms is None or int(last_bar_close_ms) < expected_close
        if bar_missing and now > expected_close + candle_publish_s * 1000:
            reasons.append(REASON_BAR_MISSING)

    if private_required and _is_stale(now, last_private_event_ms, private_max_age_s):
        reasons.append(REASON_PRIVATE_STALE)

    if REASON_QUOTE_STALE in reasons or REASON_BAR_MISSING in reasons:
        status = Health.DATOS_DEGRADADOS
    elif REASON_PRIVATE_STALE in reasons:
        status = Health.CANAL_PRIVADO_DEGRADADO
    else:
        status = Health.SALUDABLE

    return HealthReport(status=status, reasons=reasons, ts_ms=now)


def should_block_entries(report: HealthReport) -> bool:
    """``True`` salvo que el reporte esté ``SALUDABLE`` (criterio conservador)."""
    if report is None:  # pragma: no cover - defensa ante None
        return True
    try:
        status = Health(report.status)
    except ValueError:  # pragma: no cover - estado desconocido
        return True
    return status is not Health.SALUDABLE
