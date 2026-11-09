"""Máquina de estados persistente del run (spec v2.0 §12, RF-REC-06).

Estados y transiciones permitidas::

    BORRADOR               -> VALIDANDO
    VALIDANDO              -> RECONCILIANDO | INTERRUMPIDA
    RECONCILIANDO          -> CALENTANDO | INTERRUMPIDA
    CALENTANDO             -> EJECUTANDO | INTERRUMPIDA
    EJECUTANDO            <-> ENTRADAS_PAUSADAS
    EJECUTANDO|PAUSADAS    -> CERRANDO | DETENIDO | INTERRUMPIDA
    CERRANDO               -> FINALIZADA | FINALIZADA_CON_RESIDUO | DETENIDO | INTERRUMPIDA
    DETENIDO               -> VALIDANDO (reinicio de la MISMA prueba) | INTERRUMPIDA

``FINALIZADA``, ``FINALIZADA_CON_RESIDUO`` e ``INTERRUMPIDA`` son terminales.

Persistencia atómica en ``state.json``::

    {run_id, state, entries_paused, pause_reason, close_request, stop_requested,
     updated_at_ms, history: [{ts_ms, from, to, reason}]}

Regla dura (RF-REC-06): una pausa persistida **sobrevive al reinicio**; ``load()``
restaura ``entries_paused`` aunque el supervisor reencauce el run por ``VALIDANDO``.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from app.contracts import RunState

__all__ = ["InvalidTransition", "StateMachine", "TERMINAL_STATES", "TRANSITIONS"]

TERMINAL_STATES: frozenset[RunState] = frozenset(
    {RunState.FINALIZADA, RunState.FINALIZADA_CON_RESIDUO, RunState.INTERRUMPIDA}
)

TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    RunState.BORRADOR: frozenset({RunState.VALIDANDO}),
    RunState.VALIDANDO: frozenset({RunState.RECONCILIANDO, RunState.DETENIDO, RunState.INTERRUMPIDA}),
    RunState.RECONCILIANDO: frozenset({RunState.CALENTANDO, RunState.DETENIDO, RunState.INTERRUMPIDA}),
    RunState.CALENTANDO: frozenset(
        {RunState.EJECUTANDO, RunState.ENTRADAS_PAUSADAS, RunState.DETENIDO, RunState.INTERRUMPIDA}
    ),
    RunState.EJECUTANDO: frozenset(
        {
            RunState.ENTRADAS_PAUSADAS,
            RunState.CERRANDO,
            RunState.DETENIDO,
            RunState.INTERRUMPIDA,
        }
    ),
    RunState.ENTRADAS_PAUSADAS: frozenset(
        {
            RunState.EJECUTANDO,
            RunState.CERRANDO,
            RunState.DETENIDO,
            RunState.INTERRUMPIDA,
        }
    ),
    RunState.CERRANDO: frozenset(
        {
            RunState.FINALIZADA,
            RunState.FINALIZADA_CON_RESIDUO,
            RunState.DETENIDO,
            RunState.INTERRUMPIDA,
        }
    ),
    RunState.DETENIDO: frozenset({RunState.VALIDANDO, RunState.INTERRUMPIDA}),
    RunState.FINALIZADA: frozenset(),
    RunState.FINALIZADA_CON_RESIDUO: frozenset(),
    RunState.INTERRUMPIDA: frozenset(),
}

CLOSE_KINDS = ("position", "all")

CLOSE_ACTIONS = {"position": "close_position", "all": "close_all"}


class InvalidTransition(RuntimeError):
    """Transición no permitida por la máquina de estados."""

    def __init__(
        self,
        current: RunState,
        target: RunState,
        allowed: frozenset[RunState] | tuple[RunState, ...] = (),
    ):
        self.current = current
        self.target = target
        self.allowed = tuple(sorted(allowed, key=lambda s: s.value))
        detail = ", ".join(s.value for s in self.allowed) or "ninguna"
        super().__init__(
            f"transición inválida {current.value} -> {target.value} (permitidas: {detail})"
        )


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Escritura atómica (temp + ``os.replace``); compartida por copia local."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:  # pragma: no cover - limpieza best-effort
            pass


def _read_json_dict(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _coerce_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return int(value)


class StateMachine:
    """Máquina de estados con persistencia JSON atómica y flag de pausa durable."""

    def __init__(self, path: Path, run_id: str, *, state: RunState | None = None):
        self.path = Path(path)
        self.run_id = str(run_id)
        self._state = RunState(state) if state is not None else RunState.BORRADOR
        self._entries_paused = False
        self._pause_reason: str | None = None
        self._close_request: str | None = None
        self._stop_requested = False
        self._updated_at_ms = 0
        self._history: list[dict[str, Any]] = []
        self._loaded = False

    # ---------------------------------------------------------- lectura
    def load(self) -> RunState:
        """Restaura el estado desde disco. Tolera archivo ausente o corrupto."""
        data = _read_json_dict(self.path)
        self._loaded = True
        if data is None:
            return self._state
        try:
            self._state = RunState(str(data.get("state", self._state.value)))
        except ValueError:
            pass  # estado desconocido: conservar el actual
        self._entries_paused = bool(data.get("entries_paused", False))
        reason = data.get("pause_reason")
        self._pause_reason = str(reason) if reason else None
        close_request = data.get("close_request")
        self._close_request = str(close_request) if close_request else None
        self._stop_requested = bool(data.get("stop_requested", False))
        self._updated_at_ms = _coerce_int(data.get("updated_at_ms"), 0)
        history = data.get("history")
        self._history = [dict(h) for h in history if isinstance(h, dict)] if isinstance(history, list) else []
        return self._state

    @property
    def state(self) -> RunState:
        return self._state

    @property
    def entries_paused(self) -> bool:
        return self._entries_paused

    @property
    def pause_reason(self) -> str | None:
        return self._pause_reason

    @property
    def close_request(self) -> str | None:
        """``"position"``, ``"all"`` o ``None``."""
        return self._close_request

    @property
    def close_request_action(self) -> str | None:
        """Nombre canónico de la acción de control asociada (``close_position``/``close_all``)."""
        if self._close_request is None:
            return None
        return CLOSE_ACTIONS.get(self._close_request, self._close_request)

    @property
    def stop_requested(self) -> bool:
        return self._stop_requested

    @property
    def history(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(h) for h in self._history)

    @property
    def is_terminal(self) -> bool:
        return self._state in TERMINAL_STATES

    # --------------------------------------------------------- escritura
    def transition(self, to: RunState, reason: str = "") -> RunState:
        """Aplica una transición válida (o lanza ``InvalidTransition``)."""
        target = RunState(to)
        if target is self._state:
            # Idempotente: los supervisores reejecutan "asegurar estado X" al reiniciar.
            return self._state
        allowed = TRANSITIONS.get(self._state, frozenset())
        if target not in allowed:
            raise InvalidTransition(self._state, target, allowed)
        self._apply(target, reason)
        return target

    def pause_entries(self, reason: str = "") -> RunState:
        """Pausa la evaluación de entradas (persistente, RF-REC-06).

        La bandera de pausa SIEMPRE queda activa (sobrevive al reinicio); el estado
        solo cambia a ENTRADAS_PAUSADAS cuando la transición es válida. Durante el
        arranque (VALIDANDO/RECONCILIANDO/CALENTANDO) la pausa se conserva como
        bandera y el estado avanza a ENTRADAS_PAUSADAS al terminar el calentamiento.
        """
        if self._state is RunState.ENTRADAS_PAUSADAS:
            if reason:
                self._pause_reason = reason
                self._touch()
            return self._state
        try:
            return self.transition(RunState.ENTRADAS_PAUSADAS, reason)
        except InvalidTransition:
            self._entries_paused = True
            self._pause_reason = reason
            self._touch()
            return self._state

    def resume_entries(self) -> RunState:
        """Reanuda las entradas (solo desde ``ENTRADAS_PAUSADAS``)."""
        if self._state is not RunState.ENTRADAS_PAUSADAS:
            raise InvalidTransition(
                self._state, RunState.EJECUTANDO, TRANSITIONS.get(self._state, frozenset())
            )
        self._entries_paused = False
        self._pause_reason = None
        self._apply(RunState.EJECUTANDO, "entradas_reanudadas")
        return self._state

    def request_close(self, kind: str = "position") -> str:
        """Registra la solicitud de cierre (``"position"`` o ``"all"``)."""
        if kind not in CLOSE_KINDS:
            raise ValueError(f"kind inválido: {kind!r} (esperado {CLOSE_KINDS})")
        self._close_request = kind
        self._touch()
        return kind

    def clear_close_request(self) -> None:
        if self._close_request is not None:
            self._close_request = None
            self._touch()

    def request_stop(self) -> None:
        if not self._stop_requested:
            self._stop_requested = True
            self._touch()

    def clear_stop_request(self) -> None:
        if self._stop_requested:
            self._stop_requested = False
            self._touch()

    def snapshot(self) -> dict[str, Any]:
        """Vista serializable y persistible del estado completo."""
        return {
            "run_id": self.run_id,
            "state": self._state.value,
            "entries_paused": bool(self._entries_paused),
            "pause_reason": self._pause_reason,
            "close_request": self._close_request,
            "stop_requested": bool(self._stop_requested),
            "updated_at_ms": int(self._updated_at_ms),
            "history": [dict(h) for h in self._history],
        }

    def save(self) -> None:
        """Fuerza la persistencia del snapshot actual."""
        self._persist()

    # ---------------------------------------------------------- internos
    def _apply(self, target: RunState, reason: str) -> None:
        previous = self._state
        self._state = target
        if target is RunState.ENTRADAS_PAUSADAS:
            self._entries_paused = True
            if reason:
                self._pause_reason = reason
        ts = _now_ms()
        self._updated_at_ms = ts
        self._history.append(
            {"ts_ms": ts, "from": previous.value, "to": target.value, "reason": str(reason)}
        )
        self._persist()

    def _touch(self) -> None:
        self._updated_at_ms = _now_ms()
        self._persist()

    def _persist(self) -> None:
        _atomic_write_json(self.path, self.snapshot())
