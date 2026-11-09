"""Archivo de control local CLI -> proceso (spec v2.0 §13, RF-MON-04).

``control.json`` transporta una solicitud a la vez::

    {"request_id": str, "action": "pause"|"resume"|"close_position"|"close_all"
     |"stop"|"export"|"status", "params": {}, "created_ms": int,
     "status": "pending"|"ack"|"rejected", "ack_ms": int|None, "message": str|None}

Toda escritura es atómica (temp + ``os.replace``) y toda lectura es tolerante:
un archivo ausente, parcial o corrupto se traduce en ``None`` sin lanzar.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

__all__ = ["ACTIONS", "ControlFile", "ControlFileError"]

ACTIONS: tuple[str, ...] = (
    "pause",
    "resume",
    "close_position",
    "close_all",
    "stop",
    "export",
    "status",
)

STATUSES: tuple[str, ...] = ("pending", "ack", "rejected")


class ControlFileError(RuntimeError):
    """Error controlado al resolver una solicitud de control."""


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


def _coerce_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return int(value)


class ControlFile:
    """Canal local de solicitudes CLI -> proceso del bot."""

    def __init__(self, path: Path):
        self.path = Path(path)

    # ---------------------------------------------------------- lectura
    def read(self) -> dict[str, Any] | None:
        """Solicitud normalizada, o ``None`` si el archivo falta o es ilegible."""
        try:
            raw = self.path.read_text(encoding="utf-8")
        except OSError:
            return None
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return None
        if not isinstance(data, dict):
            return None
        request_id = data.get("request_id")
        action = data.get("action")
        status = data.get("status")
        if not isinstance(request_id, str) or not request_id:
            return None
        if action not in ACTIONS or status not in STATUSES:
            return None
        params = data.get("params")
        ack_ms = data.get("ack_ms")
        message = data.get("message")
        return {
            "request_id": request_id,
            "action": str(action),
            "params": dict(params) if isinstance(params, dict) else {},
            "created_ms": _coerce_int(data.get("created_ms"), 0),
            "status": str(status),
            "ack_ms": _coerce_int(ack_ms, 0) if ack_ms is not None else None,
            "message": str(message) if message is not None else None,
        }

    def pending(self) -> dict[str, Any] | None:
        """Solicitud en estado ``pending``, o ``None``."""
        current = self.read()
        if current is None or current["status"] != "pending":
            return None
        return current

    # --------------------------------------------------------- escritura
    def submit(self, action: str, params: dict[str, Any] | None = None) -> str:
        """Crea una solicitud pendiente y devuelve su ``request_id``.

        Si ya hay una pendiente sin resolver lanza ``RuntimeError``: el canal
        transporta una sola orden a la vez (RF-MON-04).
        """
        if action not in ACTIONS:
            raise ValueError(f"acción desconocida: {action!r} (válidas: {ACTIONS})")
        current = self.pending()
        if current is not None:
            raise RuntimeError(
                "ya existe una solicitud pendiente "
                f"{current['request_id']!r} ({current['action']}); "
                "ack/reject antes de enviar otra"
            )
        request = {
            "request_id": uuid.uuid4().hex,
            "action": str(action),
            "params": dict(params or {}),
            "created_ms": _now_ms(),
            "status": "pending",
            "ack_ms": None,
            "message": None,
        }
        _atomic_write_json(self.path, request)
        return request["request_id"]

    def ack(self, request_id: str, message: str | None = None) -> dict[str, Any]:
        """Marca como aceptada la solicitud pendiente."""
        return self._resolve(request_id, "ack", message)

    def reject(self, request_id: str, message: str) -> dict[str, Any]:
        """Marca como rechazada la solicitud pendiente (exige motivo)."""
        if not message:
            raise ValueError("reject requiere un message explicativo")
        return self._resolve(request_id, "rejected", message)

    def clear(self) -> None:
        """Elimina el archivo de control (best-effort)."""
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
        except OSError:  # pragma: no cover - best-effort
            pass

    # ---------------------------------------------------------- internos
    def _resolve(self, request_id: str, status: str, message: str | None) -> dict[str, Any]:
        current = self.read()
        if current is None:
            raise ControlFileError(
                "no hay una solicitud legible en el archivo de control; nada que resolver"
            )
        if str(current["request_id"]) != str(request_id):
            raise ControlFileError(
                f"request_id {request_id!r} no corresponde a la solicitud "
                f"{current['request_id']!r} ({current['action']}, {current['status']})"
            )
        if current["status"] != "pending":
            raise ControlFileError(
                f"la solicitud {request_id!r} ya está en estado {current['status']!r}"
            )
        current["status"] = str(status)
        current["ack_ms"] = _now_ms()
        current["message"] = message
        _atomic_write_json(self.path, current)
        return current
