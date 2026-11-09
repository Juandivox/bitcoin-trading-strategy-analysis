"""Recuperación tras gate de presupuesto fallido (INTERRUMPIDA).

Caso: corte de luz con posición abierta -> reinicio con ledger vacío ->
`gate_de_arranque_fallido: presupuesto 4900 > disponible 3999` -> estado
INTERRUMPIDA (terminal). El bot ya no reintenta aunque se repongan fondos.

Uso en el servidor (volumen runs/ montado):
    python scripts/recover_interrupted.py --run-id e2a-demo-001
    python scripts/recover_interrupted.py --run-id e2a-demo-001 --set-budget 3999

Lo que hace:
1. Lee runs/<id>/state.json y audit.sqlite (fills, equity, incidentes).
2. Si el estado es INTERRUMPIDA con motivo gate de presupuesto, lo pasa a
   DETENIDO (reintentable: DETENIDO -> VALIDANDO está permitido).
3. Opcionalmente reescribe budget_usdt en config/bot.yaml (--set-budget).
4. Nunca toca fills ni balances del exchange: solo estado local + config.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recupera un run INTERRUMPIDO por gate de presupuesto")
    parser.add_argument("--run-id", default="e2a-demo-001")
    parser.add_argument("--runs-dir", default="runs")
    parser.add_argument("--config", default="config/bot.yaml")
    parser.add_argument("--set-budget", type=float, default=None,
                        help="reescribe budget_usdt en el YAML (p. ej. 3999)")
    parser.add_argument("--force", action="store_true",
                        help="resetea aunque el motivo no sea presupuesto")
    args = parser.parse_args(argv)

    run_dir = Path(args.runs_dir) / args.run_id
    state_path = run_dir / "state.json"
    db_path = run_dir / "audit.sqlite"
    if not state_path.exists():
        print(f"no existe {state_path}", file=sys.stderr)
        return 1
    state = _read_json(state_path)
    print(f"estado actual: {state.get('state')} pausa={state.get('entries_paused')} motivo={state.get('pause_reason')}")
    hist = state.get("history") or []
    if hist:
        print(f"última transición: {hist[-1].get('from')} -> {hist[-1].get('to')} ({hist[-1].get('reason')})")

    if db_path.exists():
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            fills = conn.execute("SELECT COUNT(*) FROM fills").fetchone()[0]
            last_eq = conn.execute("SELECT equity, base_qty FROM equity ORDER BY id DESC LIMIT 1").fetchone()
            last_inc = conn.execute("SELECT kind, detail_json FROM incidents ORDER BY id DESC LIMIT 1").fetchone()
            print(f"fills en auditoría: {fills}")
            if last_eq:
                print(f"último equity: {last_eq['equity']} base_qty={last_eq['base_qty']}")
            if last_inc:
                print(f"último incidente: {last_inc['kind']} {last_inc['detail_json'][:200]}")
        finally:
            conn.close()
    else:
        print("sin audit.sqlite (volumen perdido?)", file=sys.stderr)

    is_interrupted = state.get("state") == "INTERRUMPIDA"
    last_reason = (hist[-1].get("reason") if hist else "") or ""
    budget_gate = "presupuesto" in last_reason or "gate: presupuesto" in last_reason
    if not is_interrupted:
        print("nada que hacer: el estado no es INTERRUMPIDA")
        return 0
    if not budget_gate and not args.force:
        print("INTERRUMPIDA por motivo distinto a presupuesto; usa --force para resetear igual", file=sys.stderr)
        return 2

    if args.set_budget is not None:
        cfg_path = Path(args.config)
        text = cfg_path.read_text(encoding="utf-8")
        lines = []
        for line in text.splitlines():
            if line.strip().startswith("budget_usdt:"):
                lines.append(f"budget_usdt: {args.set_budget}")
            else:
                lines.append(line)
        cfg_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"budget_usdt -> {args.set_budget} en {cfg_path} (reconstruye: docker compose up -d --build)")

    # Reset a DETENIDO manteniendo el historial (el supervisor lo llevará a VALIDANDO).
    import time
    state["state"] = "DETENIDO"
    state["updated_at_ms"] = int(time.time() * 1000)
    state.setdefault("history", []).append({
        "ts_ms": state["updated_at_ms"],
        "from": "INTERRUMPIDA",
        "to": "DETENIDO",
        "reason": "recuperación manual tras gate de presupuesto (ver scripts/recover_interrupted.py)",
    })
    # Escritura atómica
    tmp = state_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(state_path)
    print("estado -> DETENIDO. Reinicia: docker compose up -d && docker logs -f e2a-demo-bot")
    print("Si el BTC del exchange era posición del bot, el arranque la re-atribuye solo (ledger_reconstruido_desde_auditoria).")
    print("Si era ajeno, el bot pausará entradas: vende el excedente manual o usa --set-budget con el libre real.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
