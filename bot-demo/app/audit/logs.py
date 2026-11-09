"""Logs del bot: JSONL estructurado + consola legible, con redacción de secretos (RF-SEG-03)."""
from __future__ import annotations

import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}


def utc_iso(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class Logger:
    """Escribe a consola y a JSONL. Redacta cualquier secreto que se colara en un mensaje."""

    def __init__(self, name: str, jsonl_path: str | Path | None = None, level: str = "INFO",
                 secrets: list[str] | None = None, echo: bool = True) -> None:
        self.name = name
        self.level = LEVELS.get(level.upper(), 20)
        self.echo = echo
        self._secrets = [s for s in (secrets or []) if s and len(s) >= 8]
        self._lock = threading.Lock()
        self._fh = None
        if jsonl_path is not None:
            path = Path(jsonl_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = open(path, "a", encoding="utf-8")

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def _redact(self, text: str) -> str:
        for secret in self._secrets:
            if secret in text:
                text = text.replace(secret, "***REDACTED***")
        return text

    def log(self, level: str, event: str, **fields: Any) -> None:
        if LEVELS.get(level, 20) < self.level:
            return
        ts_ms = int(time.time() * 1000)
        safe_fields = {
            k: (self._redact(str(v)) if isinstance(v, str) else v) for k, v in fields.items()
        }
        record = {"ts": utc_iso(ts_ms), "ts_ms": ts_ms, "level": level, "logger": self.name,
                  "event": event, **safe_fields}
        line = json.dumps(record, ensure_ascii=False, default=str)
        with self._lock:
            if self._fh is not None:
                self._fh.write(line + "\n")
                self._fh.flush()
            if self.echo:
                parts = " ".join(f"{k}={v}" for k, v in safe_fields.items())
                sys.stdout.write(f"[{record['ts']}] {level:<7} {event} {parts}\n")
                sys.stdout.flush()

    def debug(self, event: str, **fields: Any) -> None:
        self.log("DEBUG", event, **fields)

    def info(self, event: str, **fields: Any) -> None:
        self.log("INFO", event, **fields)

    def warning(self, event: str, **fields: Any) -> None:
        self.log("WARNING", event, **fields)

    def error(self, event: str, **fields: Any) -> None:
        self.log("ERROR", event, **fields)

    def critical(self, event: str, **fields: Any) -> None:
        self.log("CRITICAL", event, **fields)
