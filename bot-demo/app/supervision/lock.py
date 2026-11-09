"""Escritor único por run (spec v2.0 §13, RF-SEG-06, CA-29).

Garantiza que **un solo proceso** escriba en ``runs/<run_id>/``. El lock es un
archivo JSON (``writer.lock``) creado con ``O_CREAT | O_EXCL``, que es atómico
tanto en Windows como en Linux/Docker.

Reglas:

* Si el archivo no existe -> se adquiere.
* Si existe y su heartbeat es reciente (<= ``heartbeat_timeout_s``) -> el lock
  está vivo: ``LockHeldError`` con ``.holder`` legible.
* Si existe y es rancio -> *takeover*: el proceso nuevo reescribe el lock y
  deja ``took_over = True``.
* Un archivo **corrupto** no permite saber quién lo tiene: solo se pisa si su
  ``mtime`` supera el timeout; si no, se asume vivo (``LockHeldError``).

El heartbeat se escribe siempre con ``temp + os.replace`` para que un lector
nunca vea un JSON a medias.
"""
from __future__ import annotations

import json
import os
import socket
import time
import uuid
from pathlib import Path
from typing import Any

__all__ = ["LockHeldError", "SingleWriterLock"]

LOCK_VERSION = 1


class LockHeldError(RuntimeError):
    """Otro proceso mantiene el lock de escritor del run."""

    def __init__(self, path: Path, holder: dict[str, Any] | None):
        self.path = Path(path)
        if isinstance(holder, dict) and holder:
            self.holder: dict[str, Any] = dict(holder)
        else:
            self.holder = {"path": str(self.path), "note": "contenido ilegible"}
        detail = json.dumps(self.holder, ensure_ascii=False, sort_keys=True, default=str)
        super().__init__(f"lock de escritor ocupado en {self.path}: {detail}")


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


def _host() -> str:
    try:
        return socket.gethostname()
    except OSError:  # pragma: no cover - hostname siempre disponible en la práctica
        return "desconocido"


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def _parse_json_dict(text: str | None) -> dict[str, Any] | None:
    if text is None:
        return None
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _mtime_ms(path: Path) -> int | None:
    try:
        return path.stat().st_mtime_ns // 1_000_000
    except OSError:
        return None


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def _holder_process_alive(holder: dict[str, Any] | None) -> bool:
    """True si el proceso dueño del lock parece vivo.

    Conservador: ante cualquier duda (otro host, PID ilegible, plataforma sin
    comprobación fiable) se considera vivo y se mantiene ``LockHeldError`` — nunca
    se permite un segundo escritor. Solo un PID POSIX inexistente en el mismo host
    autoriza el takeover con latido fresco (p.ej. tras un kill -9).
    """
    if not holder:
        return True
    if holder.get("host") != _host():
        return True
    pid = _as_int(holder.get("pid"))
    if pid is None or pid <= 0:
        return True
    if os.name != "posix":
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except (PermissionError, OSError):
        return True
    return True


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Escritura atómica (temp + ``os.replace``); compartida por copia local."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
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


class SingleWriterLock:
    """Lock de escritor único con heartbeat y detección de locks rancios."""

    def __init__(self, path: Path, run_id: str, heartbeat_timeout_s: int = 180):
        timeout = int(heartbeat_timeout_s)
        if timeout <= 0:
            raise ValueError("heartbeat_timeout_s debe ser > 0")
        self.path = Path(path)
        self.run_id = str(run_id)
        self.heartbeat_timeout_s = timeout
        self.took_over = False
        self._owned = False
        self._acquired_at_ms = 0
        self._last_heartbeat_ms = 0

    # ------------------------------------------------------------------ API
    def acquire(self) -> None:
        """Adquiere el lock o lanza ``LockHeldError`` si otro proceso lo tiene."""
        if self._owned:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._payload()
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            self._handle_existing()
            return
        except OSError:
            # Windows puede reportar PermissionError con el archivo ya creado.
            if self.path.exists():
                self._handle_existing()
                return
            raise
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
        except BaseException:
            try:
                self.path.unlink()
            except OSError:  # pragma: no cover - limpieza best-effort
                pass
            raise
        self._owned = True
        self._acquired_at_ms = int(payload["acquired_at_ms"])
        self._last_heartbeat_ms = int(payload["heartbeat_at_ms"])

    def heartbeat(self) -> None:
        """Reescribe el lock con marca de tiempo fresca (atómico)."""
        if not self._owned:
            raise RuntimeError("no se puede latir un lock que no se posee")
        payload = self._payload()
        _atomic_write_json(self.path, payload)
        self._last_heartbeat_ms = int(payload["heartbeat_at_ms"])

    def release(self) -> None:
        """Libera el lock si (y solo si) sigue siendo nuestro."""
        if not self._owned:
            return
        current = self.holder()
        if current is not None:
            same_run = str(current.get("run_id", "")) == self.run_id
            same_pid = current.get("pid") == os.getpid()
            if not (same_run and same_pid):
                # Un takeover ajeno ocurrió: no borrar el lock del otro.
                self._owned = False
                return
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass
        except OSError:  # pragma: no cover - best-effort
            pass
        self._owned = False

    def holder(self) -> dict[str, Any] | None:
        """Contenido del lock, o ``None`` si no existe o es ilegible."""
        return _parse_json_dict(_read_text(self.path))

    # ------------------------------------------------------------- helpers
    @property
    def owned(self) -> bool:
        return self._owned

    def age_ms(self) -> int | None:
        """Antigüedad del heartbeat del lock en ms (``None`` si no hay lock)."""
        reference = self._reference_ms(self.holder())
        if reference is None:
            return None
        return _now_ms() - reference

    def is_stale(self) -> bool:
        age = self.age_ms()
        return age is not None and age > self.heartbeat_timeout_s * 1000

    def __enter__(self) -> SingleWriterLock:
        self.acquire()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.release()

    def _payload(self) -> dict[str, Any]:
        now = _now_ms()
        return {
            "version": LOCK_VERSION,
            "pid": os.getpid(),
            "host": _host(),
            "run_id": self.run_id,
            "acquired_at_ms": self._acquired_at_ms or now,
            "heartbeat_at_ms": now,
        }

    def _reference_ms(self, holder: dict[str, Any] | None) -> int | None:
        """Instante de referencia para decidir si el lock está rancio."""
        if holder is not None:
            for key in ("heartbeat_at_ms", "acquired_at_ms"):
                value = _as_int(holder.get(key))
                if value is not None:
                    return value
        return _mtime_ms(self.path)

    def _handle_existing(self) -> None:
        holder = self.holder()
        reference = self._reference_ms(holder)
        age_ms = None if reference is None else _now_ms() - reference
        if age_ms is not None and age_ms <= self.heartbeat_timeout_s * 1000:
            # El latido está fresco; si además el proceso dueño sigue vivo, no se toca.
            if _holder_process_alive(holder):
                raise LockHeldError(self.path, holder)
            # Latido fresco pero PID muerto (p.ej. kill -9): takeover inmediato.
        # Rancio (o sin referencia temporal utilizable): takeover.
        payload = self._payload()
        try:
            _atomic_write_json(self.path, payload)
        except PermissionError:  # pragma: no cover - Windows con archivo abierto
            try:
                self.path.unlink()
            except OSError:
                pass
            _atomic_write_json(self.path, payload)
        self.took_over = True
        self._owned = True
        self._acquired_at_ms = int(payload["acquired_at_ms"])
        self._last_heartbeat_ms = int(payload["heartbeat_at_ms"])
