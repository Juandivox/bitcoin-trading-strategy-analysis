"""CLI del operador: controla el proceso único mediante el archivo de control (RF-MON-04).

Ejemplos:
  python -m app.cli status
  python -m app.cli pause --reason "revisión manual"
  python -m app.cli resume
  python -m app.cli close-position
  python -m app.cli stop
  python -m app.cli export
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

from app.supervision.control import ControlFile


def _find_run_dir(runs_dir: Path, run_id: str | None) -> Path:
    if run_id:
        path = runs_dir / run_id
        if not path.exists():
            raise SystemExit(f"no existe la prueba {run_id} en {runs_dir}")
        return path
    candidates = [p for p in runs_dir.iterdir() if p.is_dir()] if runs_dir.exists() else []
    if not candidates:
        raise SystemExit(f"no hay pruebas en {runs_dir}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def cmd_status(args) -> int:
    run_dir = _find_run_dir(Path(args.runs_dir), args.run_id)
    state = _read_json(run_dir / "state.json")
    print(f"prueba: {run_dir.name}")
    print(f"estado: {state.get('state', 'DESCONOCIDO')}")
    print(f"entradas_pausadas: {state.get('entries_paused', False)}"
          + (f" ({state.get('pause_reason')})" if state.get("pause_reason") else ""))
    db_path = run_dir / "audit.sqlite"
    if db_path.exists():
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            def scalar(sql: str, default=None):
                row = conn.execute(sql).fetchone()
                return row[0] if row and row[0] is not None else default

            print(f"salud: {scalar('SELECT status FROM health ORDER BY id DESC LIMIT 1', 'n/a')}")
            print(f"equity: {scalar('SELECT equity FROM equity ORDER BY id DESC LIMIT 1', 'n/a')}")
            print(f"fills: {scalar('SELECT COUNT(*) FROM fills', 0)}")
            print(f"ordenes: {scalar('SELECT COUNT(*) FROM orders', 0)}")
            print(f"operaciones_cerradas: {scalar('SELECT COUNT(*) FROM trades WHERE closed=1', 0)}")
            print(f"incidentes: {scalar('SELECT COUNT(*) FROM incidents', 0)}")
            last_signal = conn.execute("SELECT action, target_position, cci, reason FROM signals ORDER BY id DESC LIMIT 1").fetchone()
            if last_signal:
                print(f"ultima_senal: {last_signal['action']} objetivo={last_signal['target_position']} "
                      f"cci={last_signal['cci']} motivo={last_signal['reason']}")
        finally:
            conn.close()
    return 0


def _send(args, action: str, params: dict | None = None, wait_s: int = 20) -> int:
    run_dir = _find_run_dir(Path(args.runs_dir), args.run_id)
    control = ControlFile(run_dir / "control.json")
    request_id = control.submit(action, params)
    deadline = time.time() + wait_s
    while time.time() < deadline:
        data = control.read() or {}
        if data.get("request_id") == request_id and data.get("status") in ("ack", "rejected"):
            status = data["status"]
            print(f"{status}: {data.get('message')}")
            return 0 if status == "ack" else 1
        time.sleep(0.5)
    print("sin_respuesta: el proceso no confirmó la solicitud (¿está corriendo?)")
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CLI del bot E2-A")
    parser.add_argument("--runs-dir", default="runs")
    parser.add_argument("--run-id", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    p_pause = sub.add_parser("pause")
    p_pause.add_argument("--reason", default="solicitud_del_operador")
    sub.add_parser("resume")
    sub.add_parser("close-position")
    sub.add_parser("close-all")
    sub.add_parser("stop")
    sub.add_parser("export")
    args = parser.parse_args(argv)

    if args.command == "status":
        return cmd_status(args)
    mapping = {
        "pause": ("pause", {"reason": getattr(args, "reason", "solicitud_del_operador")}),
        "resume": ("resume", None),
        "close-position": ("close_position", None),
        "close-all": ("close_all", None),
        "stop": ("stop", None),
        "export": ("export", None),
    }
    action, params = mapping[args.command]
    return _send(args, action, params)


if __name__ == "__main__":
    raise SystemExit(main())
