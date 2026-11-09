"""Exportaciones reproducibles (RF-REP-01..04): CSV/JSON/Markdown con corte, esquema y hashes."""
from __future__ import annotations

import csv
import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from app.audit.db import AuditDB
from app.audit.logs import utc_iso
from app.config import BotConfig

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value) -> str:
    if value is None:
        return ""
    text = str(value)
    if text.startswith(FORMULA_PREFIXES):
        return "'" + text
    return text


def _to_iso(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return utc_iso(int(value))
    return value


def _rows_to_csv(path: Path, rows: list[dict], columns: list[str] | None = None) -> int:
    if not rows:
        path.write_text("", encoding="utf-8")
        return 0
    columns = columns or list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([csv_safe(_to_iso(row.get(col))) for col in columns])
    return len(rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_run(
    db: AuditDB,
    cfg: BotConfig,
    exports_dir: Path,
    metrics: dict | None = None,
    export_id: str | None = None,
    state: str = "DESCONOCIDO",
    health: str = "DESCONOCIDO",
) -> dict:
    exports_dir.mkdir(parents=True, exist_ok=True)
    export_id = export_id or uuid.uuid4().hex[:12]
    cut_ms = int(time.time() * 1000)
    files: list[dict] = []

    run_rows = db.fetch("run")
    run_info = run_rows[0] if run_rows else {}

    tables = {
        "orders.csv": ("orders", None),
        "fills.csv": ("fills", None),
        "trades.csv": ("trades", None),
        "balances.csv": ("balances", None),
        "equity.csv": ("equity", None),
        "signals.csv": ("signals", None),
    }
    for filename, (table, columns) in tables.items():
        rows = db.fetch(table)
        count = _rows_to_csv(exports_dir / filename, rows, columns)
        files.append({"name": filename, "table": table, "rows": count})

    events: list[dict] = []
    for row in db.fetch("state_history"):
        events.append({"type": "state", "ts_ms": row["ts_ms"], "detail": f"{row['from_state']}->{row['to_state']}: {row['reason']}"})
    for row in db.fetch("order_events"):
        events.append({"type": "order", "ts_ms": row["ts_ms"], "detail": f"{row['client_order_id']} {row['event']}"})
    for row in db.fetch("health"):
        events.append({"type": "health", "ts_ms": row["ts_ms"], "detail": f"{row['status']} {row['reasons_json']}"})
    for row in db.fetch("incidents"):
        events.append({"type": "incident", "ts_ms": row["ts_ms"], "detail": f"{row['kind']} {row['detail_json']}"})
    events.sort(key=lambda e: e["ts_ms"] or 0)
    count = _rows_to_csv(exports_dir / "events.csv", events, ["type", "ts_ms", "detail"])
    files.append({"name": "events.csv", "table": "events", "rows": count})

    metrics = metrics or {}
    (exports_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    files.append({"name": "metrics.json", "table": "metrics", "rows": 1})

    last_equity = db.last_equity()
    lines = [
        f"# Resumen de prueba — {cfg.run_id}",
        "",
        f"- **Export:** `{export_id}` — corte {utc_iso(cut_ms)}",
        f"- **Instrumento:** {cfg.instrument_id} · barras {cfg.bar_interval} · variante {cfg.strategy_variant}",
        f"- **Presupuesto asignado:** {cfg.budget_usdt} USDT · entrada objetivo {cfg.entry_notional_usdt} USDT",
        f"- **Estado operativo:** {state} · salud {health}",
        f"- **Config fingerprint:** `{cfg.fingerprint()}`",
        "",
        "## Conteos",
        "",
        f"- señales: {db.count('signals')}",
        f"- intenciones: {db.count('order_intents')}",
        f"- órdenes: {db.count('orders')}",
        f"- fills: {db.count('fills')}",
        f"- operaciones cerradas: {len([t for t in db.fetch('trades') if t.get('closed')])}",
        f"- incidentes: {db.count('incidents')}",
        "",
        "## Último patrimonio",
        "",
        f"- equity: {last_equity['equity'] if last_equity else 'sin datos'}",
        f"- efectivo libre: {last_equity['cash_free'] if last_equity else 'sin datos'}",
        f"- inventario: {last_equity['base_qty'] if last_equity else 'sin datos'} @ {last_equity['base_price'] if last_equity else 'sin datos'}",
        "",
        "## Métricas",
        "",
    ]
    for key in sorted(metrics):
        if key == "motivos":
            continue
        value = metrics[key]
        reason = metrics.get("motivos", {}).get(key)
        lines.append(f"- {key}: {value}" + (f"  _(no calculable: {reason})_" if reason else ""))
    if metrics.get("muestra_corta"):
        lines.append("- **muestra_corta: True** — menos de 30 retornos diarios válidos")
    (exports_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    files.append({"name": "summary.md", "table": "summary", "rows": len(lines)})

    manifest = {
        "export_id": export_id,
        "cut_ms": cut_ms,
        "cut_iso": utc_iso(cut_ms),
        "run_id": cfg.run_id,
        "config_fingerprint": cfg.fingerprint(),
        "run": run_info,
        "state": state,
        "health": health,
        "files": [],
    }
    for entry in files:
        path = exports_dir / entry["name"]
        manifest["files"].append({**entry, "sha256": _sha256(path), "bytes": path.stat().st_size})
    (exports_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    db.record_export(cut_ms, export_id, manifest["files"])
    return manifest
