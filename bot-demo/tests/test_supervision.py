"""Tests de las primitivas de supervisión (spec v2.0 §12/§13).

Cubre: SingleWriterLock (RF-SEG-06/CA-29), StateMachine (spec §12/RF-REC-06),
ControlFile (RF-MON-04) y frescura de datos (RF-DAT-05/RF-MON-03).
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config import Tolerances
from app.contracts import Health, HealthReport, RunState
from app.supervision.control import ACTIONS, ControlFile, ControlFileError
from app.supervision.health import (
    evaluate_freshness,
    expected_last_closed_bar_close_ms,
    should_block_entries,
)
from app.supervision.lock import LockHeldError, SingleWriterLock
from app.supervision.state import InvalidTransition, StateMachine

HOUR_MS = 3_600_000
BAR_4H_MS = 4 * HOUR_MS


def ms_at(hour: int, minute: int = 0, second: int = 0, milli: int = 0) -> int:
    """Epoch ms de una hora UTC fija de 2026-03-10."""
    dt = datetime(2026, 3, 10, hour, minute, second, milli * 1000, tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


HAPPY_PATH: dict[RunState, tuple[RunState, ...]] = {
    RunState.VALIDANDO: (RunState.VALIDANDO,),
    RunState.RECONCILIANDO: (RunState.VALIDANDO, RunState.RECONCILIANDO),
    RunState.CALENTANDO: (RunState.VALIDANDO, RunState.RECONCILIANDO, RunState.CALENTANDO),
    RunState.EJECUTANDO: (
        RunState.VALIDANDO,
        RunState.RECONCILIANDO,
        RunState.CALENTANDO,
        RunState.EJECUTANDO,
    ),
    RunState.DETENIDO: (
        RunState.VALIDANDO,
        RunState.RECONCILIANDO,
        RunState.CALENTANDO,
        RunState.EJECUTANDO,
        RunState.DETENIDO,
    ),
    RunState.CERRANDO: (
        RunState.VALIDANDO,
        RunState.RECONCILIANDO,
        RunState.CALENTANDO,
        RunState.EJECUTANDO,
        RunState.CERRANDO,
    ),
    RunState.FINALIZADA: (
        RunState.VALIDANDO,
        RunState.RECONCILIANDO,
        RunState.CALENTANDO,
        RunState.EJECUTANDO,
        RunState.CERRANDO,
        RunState.FINALIZADA,
    ),
    RunState.FINALIZADA_CON_RESIDUO: (
        RunState.VALIDANDO,
        RunState.RECONCILIANDO,
        RunState.CALENTANDO,
        RunState.EJECUTANDO,
        RunState.CERRANDO,
        RunState.FINALIZADA_CON_RESIDUO,
    ),
    RunState.INTERRUMPIDA: (RunState.VALIDANDO, RunState.INTERRUMPIDA),
}


def drive_to(sm: StateMachine, target: RunState) -> StateMachine:
    """Lleva la máquina hasta ``target`` por la ruta feliz (sin pausas)."""
    for step in HAPPY_PATH[target]:
        if sm.state is step:
            continue
        sm.transition(step, "test")
    assert sm.state is target
    return sm


# --------------------------------------------------------------------------- lock
def test_lock_acquire_heartbeat_release(tmp_path: Path) -> None:
    path = tmp_path / "writer.lock"
    lock = SingleWriterLock(path, run_id="run-1", heartbeat_timeout_s=180)
    assert lock.holder() is None

    lock.acquire()
    assert path.exists()
    assert lock.owned is True
    first = lock.holder()
    assert first is not None
    assert first["run_id"] == "run-1"
    assert first["pid"] == os.getpid()
    assert first["host"]
    assert first["heartbeat_at_ms"] >= first["acquired_at_ms"] > 0

    time.sleep(0.01)
    lock.heartbeat()
    second = lock.holder()
    assert second is not None
    assert second["heartbeat_at_ms"] >= first["heartbeat_at_ms"]
    assert second["acquired_at_ms"] == first["acquired_at_ms"]
    assert not list(tmp_path.glob("*.tmp")), "el heartbeat no debe dejar temporales"

    lock.release()
    assert not path.exists()
    assert lock.holder() is None


def test_lock_second_writer_is_rejected_with_readable_holder(tmp_path: Path) -> None:
    path = tmp_path / "writer.lock"
    first = SingleWriterLock(path, run_id="run-1")
    first.acquire()
    try:
        second = SingleWriterLock(path, run_id="run-2")
        with pytest.raises(LockHeldError) as excinfo:
            second.acquire()
        holder = excinfo.value.holder
        assert isinstance(holder, dict)
        assert holder["run_id"] == "run-1"
        assert holder["pid"] == os.getpid()
        assert "run-1" in str(excinfo.value)
        assert second.took_over is False
        assert second.owned is False
    finally:
        first.release()


def test_lock_stale_heartbeat_allows_takeover(tmp_path: Path) -> None:
    path = tmp_path / "writer.lock"
    old = SingleWriterLock(path, run_id="run-old", heartbeat_timeout_s=1)
    old.acquire()
    stale = json.loads(path.read_text(encoding="utf-8"))
    stale["heartbeat_at_ms"] = int(time.time() * 1000) - 60_000
    stale["acquired_at_ms"] = stale["heartbeat_at_ms"]
    path.write_text(json.dumps(stale), encoding="utf-8")

    new = SingleWriterLock(path, run_id="run-new", heartbeat_timeout_s=1)
    assert new.is_stale() is True
    new.acquire()
    assert new.took_over is True
    assert new.owned is True
    assert new.holder()["run_id"] == "run-new"
    new.release()
    assert not path.exists()


def test_lock_stale_by_mtime_allows_takeover(tmp_path: Path) -> None:
    path = tmp_path / "writer.lock"
    path.write_text("{}", encoding="utf-8")
    old_ts = time.time() - 3600
    os.utime(path, (old_ts, old_ts))

    lock = SingleWriterLock(path, run_id="run-new", heartbeat_timeout_s=180)
    lock.acquire()
    assert lock.took_over is True
    assert lock.holder()["run_id"] == "run-new"


def test_lock_corrupt_recent_file_is_held(tmp_path: Path) -> None:
    path = tmp_path / "writer.lock"
    path.write_text('{"pid": 1234, "run_id": "run-1"', encoding="utf-8")  # JSON truncado

    lock = SingleWriterLock(path, run_id="run-2", heartbeat_timeout_s=180)
    with pytest.raises(LockHeldError) as excinfo:
        lock.acquire()
    assert isinstance(excinfo.value.holder, dict)
    assert excinfo.value.holder["note"] == "contenido ilegible"
    assert lock.took_over is False


def test_lock_corrupt_old_file_allows_takeover(tmp_path: Path) -> None:
    path = tmp_path / "writer.lock"
    path.write_text("no soy json", encoding="utf-8")
    old_ts = time.time() - 7200
    os.utime(path, (old_ts, old_ts))

    lock = SingleWriterLock(path, run_id="run-2", heartbeat_timeout_s=180)
    lock.acquire()
    assert lock.took_over is True
    assert lock.holder()["run_id"] == "run-2"


def test_lock_release_does_not_delete_foreign_lock(tmp_path: Path) -> None:
    path = tmp_path / "writer.lock"
    lock = SingleWriterLock(path, run_id="run-1")
    lock.acquire()
    foreign = json.loads(path.read_text(encoding="utf-8"))
    foreign["run_id"] = "run-2"
    foreign["pid"] = 999_999
    path.write_text(json.dumps(foreign), encoding="utf-8")

    lock.release()
    assert path.exists()
    assert lock.owned is False


def test_lock_rejects_invalid_timeout(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        SingleWriterLock(tmp_path / "writer.lock", run_id="run-1", heartbeat_timeout_s=0)


def test_lock_context_manager(tmp_path: Path) -> None:
    path = tmp_path / "writer.lock"
    with SingleWriterLock(path, run_id="run-1") as lock:
        assert lock.owned is True
        assert path.exists()
    assert not path.exists()


# -------------------------------------------------------------------- state machine
def test_state_happy_path_pause_and_resume(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    sm = StateMachine(path, run_id="run-1")
    assert sm.state is RunState.BORRADOR

    sm.transition(RunState.VALIDANDO, "inicio")
    sm.transition(RunState.RECONCILIANDO, "reconciliando")
    sm.transition(RunState.CALENTANDO, "warmup")
    sm.transition(RunState.EJECUTANDO, "listo")
    assert sm.state is RunState.EJECUTANDO
    assert sm.entries_paused is False

    sm.pause_entries("mantenimiento manual")
    assert sm.state is RunState.ENTRADAS_PAUSADAS
    assert sm.entries_paused is True
    assert sm.pause_reason == "mantenimiento manual"

    sm.resume_entries()
    assert sm.state is RunState.EJECUTANDO
    assert sm.entries_paused is False
    assert sm.pause_reason is None

    sm.request_close("position")
    assert sm.close_request == "position"
    assert sm.close_request_action == "close_position"
    sm.transition(RunState.CERRANDO, "cerrando")
    sm.clear_close_request()
    assert sm.close_request is None

    sm.transition(RunState.FINALIZADA, "ok")
    assert sm.is_terminal is True
    assert path.exists()


def test_invalid_transition_raises_and_keeps_state(tmp_path: Path) -> None:
    sm = StateMachine(tmp_path / "state.json", run_id="run-1")
    with pytest.raises(InvalidTransition):
        sm.transition(RunState.EJECUTANDO, "imposible desde BORRADOR")

    drive_to(sm, RunState.EJECUTANDO)
    assert sm.state is RunState.EJECUTANDO
    with pytest.raises(InvalidTransition) as excinfo:
        sm.transition(RunState.FINALIZADA, "salto ilegal")
    assert excinfo.value.current is RunState.EJECUTANDO
    assert excinfo.value.target is RunState.FINALIZADA
    assert sm.state is RunState.EJECUTANDO
    assert sm.is_terminal is False


@pytest.mark.parametrize(
    "terminal",
    [RunState.FINALIZADA, RunState.FINALIZADA_CON_RESIDUO, RunState.INTERRUMPIDA],
)
def test_terminal_states_are_final(tmp_path: Path, terminal: RunState) -> None:
    sm = StateMachine(tmp_path / "state.json", run_id="run-1")
    drive_to(sm, terminal)
    assert sm.state is terminal
    assert sm.is_terminal is True
    for target in RunState:
        if target is terminal:
            assert sm.transition(target, "idempotente") is terminal
            continue
        with pytest.raises(InvalidTransition):
            sm.transition(target, "terminal")


def test_detenido_can_restart_same_run(tmp_path: Path) -> None:
    sm = StateMachine(tmp_path / "state.json", run_id="run-1")
    drive_to(sm, RunState.EJECUTANDO)
    sm.transition(RunState.DETENIDO, "stop solicitado")
    sm.transition(RunState.VALIDANDO, "reinicio de la misma prueba")
    assert sm.state is RunState.VALIDANDO


def test_pause_survives_reload_in_new_object(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    sm = StateMachine(path, run_id="run-1")
    drive_to(sm, RunState.EJECUTANDO)
    sm.pause_entries("reconciliacion pendiente")
    sm.transition(RunState.DETENIDO, "proceso detenido")

    reloaded = StateMachine(path, run_id="run-1")
    assert reloaded.load() is RunState.DETENIDO
    assert reloaded.entries_paused is True
    assert reloaded.pause_reason == "reconciliacion pendiente"

    reloaded.transition(RunState.VALIDANDO, "reinicio de la MISMA prueba")
    assert reloaded.state is RunState.VALIDANDO
    assert reloaded.entries_paused is True, "la pausa persistida sobrevive al reinicio"
    assert reloaded.pause_reason == "reconciliacion pendiente"

    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["entries_paused"] is True
    assert on_disk["pause_reason"] == "reconciliacion pendiente"


def test_close_and_stop_requests_persist(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    sm = StateMachine(path, run_id="run-1")
    drive_to(sm, RunState.EJECUTANDO)
    sm.request_close("all")
    sm.request_stop()

    reloaded = StateMachine(path, run_id="run-1")
    reloaded.load()
    assert reloaded.close_request == "all"
    assert reloaded.close_request_action == "close_all"
    assert reloaded.stop_requested is True

    reloaded.clear_close_request()
    reloaded.clear_stop_request()
    final = StateMachine(path, run_id="run-1")
    final.load()
    assert final.close_request is None
    assert final.stop_requested is False


def test_request_close_validates_kind(tmp_path: Path) -> None:
    sm = StateMachine(tmp_path / "state.json", run_id="run-1")
    with pytest.raises(ValueError):
        sm.request_close("banana")


def test_resume_without_pause_raises(tmp_path: Path) -> None:
    sm = StateMachine(tmp_path / "state.json", run_id="run-1")
    drive_to(sm, RunState.EJECUTANDO)
    with pytest.raises(InvalidTransition):
        sm.resume_entries()


def test_history_accumulates_and_persists(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    sm = StateMachine(path, run_id="run-1")
    sm.transition(RunState.VALIDANDO, "a")
    sm.transition(RunState.RECONCILIANDO, "b")
    sm.transition(RunState.CALENTANDO, "c")
    sm.transition(RunState.EJECUTANDO, "d")
    sm.pause_entries("e")

    history = sm.history
    assert [h["to"] for h in history] == [
        "VALIDANDO",
        "RECONCILIANDO",
        "CALENTANDO",
        "EJECUTANDO",
        "ENTRADAS_PAUSADAS",
    ]
    assert [h["from"] for h in history] == [
        "BORRADOR",
        "VALIDANDO",
        "RECONCILIANDO",
        "CALENTANDO",
        "EJECUTANDO",
    ]
    assert [h["reason"] for h in history] == ["a", "b", "c", "d", "e"]
    assert all(h["ts_ms"] > 0 for h in history)

    reloaded = StateMachine(path, run_id="run-1")
    reloaded.load()
    assert len(reloaded.history) == 5
    reloaded.resume_entries()
    assert len(reloaded.history) == 6
    assert reloaded.history[-1]["reason"] == "entradas_reanudadas"


def test_state_file_shape_and_atomic_write(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    sm = StateMachine(path, run_id="run-1")
    sm.transition(RunState.VALIDANDO, "inicio")

    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data) == {
        "run_id",
        "state",
        "entries_paused",
        "pause_reason",
        "close_request",
        "stop_requested",
        "updated_at_ms",
        "history",
    }
    assert data["run_id"] == "run-1"
    assert data["state"] == "VALIDANDO"
    assert data["updated_at_ms"] > 0
    assert set(data["history"][0]) == {"ts_ms", "from", "to", "reason"}
    assert not list(tmp_path.glob("*.tmp"))


def test_state_load_tolerates_missing_and_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    sm = StateMachine(path, run_id="run-1")
    assert sm.load() is RunState.BORRADOR  # archivo ausente: no lanza

    path.write_text('{"run_id": "run-1", "state": "VALI', encoding="utf-8")
    assert sm.load() is RunState.BORRADOR  # JSON parcial: no lanza


# --------------------------------------------------------------------- control file
def test_control_submit_pending_ack(tmp_path: Path) -> None:
    path = tmp_path / "control.json"
    cf = ControlFile(path)
    assert cf.read() is None
    assert cf.pending() is None

    request_id = cf.submit("pause", {"motivo": "manual"})
    pending = cf.pending()
    assert pending is not None
    assert pending["request_id"] == request_id
    assert pending["action"] == "pause"
    assert pending["params"] == {"motivo": "manual"}
    assert pending["status"] == "pending"
    assert pending["ack_ms"] is None
    assert pending["message"] is None

    cf.ack(request_id, "pausa aplicada")
    assert cf.pending() is None
    resolved = cf.read()
    assert resolved is not None
    assert resolved["status"] == "ack"
    assert resolved["message"] == "pausa aplicada"
    assert resolved["ack_ms"] is not None


def test_control_second_pending_is_rejected(tmp_path: Path) -> None:
    cf = ControlFile(tmp_path / "control.json")
    cf.submit("pause")
    with pytest.raises(RuntimeError):
        cf.submit("stop")
    assert cf.pending()["action"] == "pause"

    cf.ack(cf.pending()["request_id"])
    new_id = cf.submit("stop")  # tras resolver, el canal vuelve a estar libre
    assert cf.pending()["request_id"] == new_id


def test_control_reject(tmp_path: Path) -> None:
    cf = ControlFile(tmp_path / "control.json")
    request_id = cf.submit("close_all")
    with pytest.raises(ValueError):
        cf.reject(request_id, "")
    cf.reject(request_id, "sin posición abierta")
    resolved = cf.read()
    assert resolved["status"] == "rejected"
    assert resolved["message"] == "sin posición abierta"
    assert cf.pending() is None


def test_control_corrupt_or_partial_file_reads_none(tmp_path: Path) -> None:
    path = tmp_path / "control.json"
    cf = ControlFile(path)

    path.write_text('{"request_id": "abc", "action": "pau', encoding="utf-8")
    assert cf.read() is None
    assert cf.pending() is None

    path.write_text("", encoding="utf-8")
    assert cf.read() is None

    path.write_text('{"algo": 1}', encoding="utf-8")
    assert cf.read() is None

    request_id = cf.submit("status")  # se recupera sobreescribiendo lo corrupto
    assert cf.pending()["request_id"] == request_id


def test_control_resolution_errors_are_controlled(tmp_path: Path) -> None:
    cf = ControlFile(tmp_path / "control.json")
    with pytest.raises(ControlFileError):
        cf.ack("no-existe")  # sin archivo

    request_id = cf.submit("status")
    with pytest.raises(ControlFileError):
        cf.ack("otro-id")
    cf.ack(request_id)
    with pytest.raises(ControlFileError):
        cf.ack(request_id)  # ya resuelta
    with pytest.raises(ControlFileError):
        cf.reject(request_id, "tarde")


def test_control_submit_validates_action(tmp_path: Path) -> None:
    cf = ControlFile(tmp_path / "control.json")
    with pytest.raises(ValueError):
        cf.submit("autodestruir")
    assert "close_position" in ACTIONS and "status" in ACTIONS


def test_control_file_shape_and_atomic_write(tmp_path: Path) -> None:
    path = tmp_path / "control.json"
    cf = ControlFile(path)
    request_id = cf.submit("export", {"what": "fills"})

    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data) == {
        "request_id",
        "action",
        "params",
        "created_ms",
        "status",
        "ack_ms",
        "message",
    }
    assert data["request_id"] == request_id
    assert data["created_ms"] > 0
    assert not list(tmp_path.glob("*.tmp"))


# ------------------------------------------------------------------------- frescura
NOW_4H = ms_at(12, 0, 30)  # 12:00:30 UTC
LAST_CLOSE_4H = ms_at(11, 59, 59, 999)  # cierre de la vela 08:00-11:59:59.999
PREV_CLOSE_4H = ms_at(7, 59, 59, 999)


def test_expected_last_closed_bar_close_ms_4h_boundaries() -> None:
    assert expected_last_closed_bar_close_ms(ms_at(15, 59, 59, 999), BAR_4H_MS) == LAST_CLOSE_4H
    assert expected_last_closed_bar_close_ms(ms_at(16, 0, 0, 0), BAR_4H_MS) == ms_at(15, 59, 59, 999)
    assert expected_last_closed_bar_close_ms(ms_at(16, 0, 0, 1), BAR_4H_MS) == ms_at(15, 59, 59, 999)
    assert expected_last_closed_bar_close_ms(ms_at(15, 59, 59, 998), BAR_4H_MS) == LAST_CLOSE_4H
    assert expected_last_closed_bar_close_ms(ms_at(11, 59, 59, 999), BAR_4H_MS) == PREV_CLOSE_4H
    assert expected_last_closed_bar_close_ms(ms_at(12, 0, 0, 0), BAR_4H_MS) == LAST_CLOSE_4H


def test_expected_last_closed_bar_close_ms_1h_boundaries() -> None:
    assert expected_last_closed_bar_close_ms(ms_at(12, 0, 0, 0), HOUR_MS) == ms_at(11, 59, 59, 999)
    assert expected_last_closed_bar_close_ms(ms_at(12, 0, 0, 1), HOUR_MS) == ms_at(11, 59, 59, 999)
    assert expected_last_closed_bar_close_ms(ms_at(11, 59, 59, 999), HOUR_MS) == ms_at(10, 59, 59, 999)
    assert expected_last_closed_bar_close_ms(ms_at(11, 59, 59, 998), HOUR_MS) == ms_at(10, 59, 59, 999)
    assert expected_last_closed_bar_close_ms(ms_at(0, 0, 0, 0), HOUR_MS) == ms_at(23, 59, 59, 999) - 24 * HOUR_MS


def test_expected_last_closed_bar_invariants() -> None:
    for interval in (HOUR_MS, BAR_4H_MS):
        for offset_min in range(0, 4 * 60, 7):
            now = ms_at(12, 0, 0) + offset_min * 60_000
            close = expected_last_closed_bar_close_ms(now, interval)
            assert close < now
            assert now - close <= interval
            assert close % interval == interval - 1
            assert expected_last_closed_bar_close_ms(close, interval) == close - interval
            assert expected_last_closed_bar_close_ms(close + 1, interval) == close


def test_expected_last_closed_bar_rejects_bad_interval() -> None:
    with pytest.raises(ValueError):
        expected_last_closed_bar_close_ms(NOW_4H, 0)


def test_freshness_4h_bar_is_not_stale_between_closes() -> None:
    """Caso exacto del spec: 12:00:30, vela 4h cerrada 11:59:59.999, quote 5 s."""
    report = evaluate_freshness(
        now_ms=NOW_4H,
        last_bar_close_ms=LAST_CLOSE_4H,
        last_quote_ms=NOW_4H - 5_000,
        last_private_event_ms=NOW_4H - 5_000,
        tolerances=Tolerances(),
        private_required=True,
        interval_ms=BAR_4H_MS,
    )
    assert report.status is Health.SALUDABLE
    assert report.reasons == []
    assert report.ts_ms == NOW_4H
    assert should_block_entries(report) is False


def test_freshness_quote_stale_degrades() -> None:
    tolerances = Tolerances()
    fresh = evaluate_freshness(
        NOW_4H, LAST_CLOSE_4H, NOW_4H - 30_000, NOW_4H - 1_000, tolerances, interval_ms=BAR_4H_MS
    )
    assert fresh.status is Health.SALUDABLE, "30 s exactos siguen dentro de tolerancia"

    stale = evaluate_freshness(
        NOW_4H, LAST_CLOSE_4H, NOW_4H - 31_000, NOW_4H - 1_000, tolerances, interval_ms=BAR_4H_MS
    )
    assert stale.status is Health.DATOS_DEGRADADOS
    assert stale.reasons == ["cotizacion_obsoleta"]
    assert should_block_entries(stale) is True


def test_freshness_missing_expected_bar_degrades_after_publish_tolerance() -> None:
    now = LAST_CLOSE_4H + 61_000  # 61 s después del cierre esperado
    report = evaluate_freshness(
        now, PREV_CLOSE_4H, now - 1_000, now - 1_000, Tolerances(), interval_ms=BAR_4H_MS
    )
    assert report.status is Health.DATOS_DEGRADADOS
    assert report.reasons == ["vela_esperada_ausente"]
    assert should_block_entries(report) is True


def test_freshness_missing_expected_bar_within_publish_tolerance_is_ok() -> None:
    """La vela acaba de cerrar y aún no se publica: 60 s de gracia, no es obsoleta."""
    now = LAST_CLOSE_4H + 60_000
    report = evaluate_freshness(
        now, PREV_CLOSE_4H, now - 1_000, now - 1_000, Tolerances(), interval_ms=BAR_4H_MS
    )
    assert report.status is Health.SALUDABLE
    assert should_block_entries(report) is False


def test_freshness_missing_bar_without_any_bar_ever() -> None:
    now = LAST_CLOSE_4H + 61_000
    report = evaluate_freshness(
        now, None, now - 1_000, now - 1_000, Tolerances(), interval_ms=BAR_4H_MS
    )
    assert report.status is Health.DATOS_DEGRADADOS
    assert report.reasons == ["vela_esperada_ausente"]


def test_freshness_private_channel_degraded() -> None:
    report = evaluate_freshness(
        NOW_4H,
        LAST_CLOSE_4H,
        NOW_4H - 5_000,
        NOW_4H - 61_000,
        Tolerances(),
        private_required=True,
        interval_ms=BAR_4H_MS,
    )
    assert report.status is Health.CANAL_PRIVADO_DEGRADADO
    assert report.reasons == ["canal_privado_obsoleto"]
    assert should_block_entries(report) is True

    ignored = evaluate_freshness(
        NOW_4H,
        LAST_CLOSE_4H,
        NOW_4H - 5_000,
        None,
        Tolerances(),
        private_required=False,
        interval_ms=BAR_4H_MS,
    )
    assert ignored.status is Health.SALUDABLE


def test_freshness_public_degradation_dominates_private() -> None:
    now = LAST_CLOSE_4H + 61_000
    report = evaluate_freshness(
        now,
        PREV_CLOSE_4H,
        now - 31_000,
        now - 61_000,
        Tolerances(),
        interval_ms=BAR_4H_MS,
    )
    assert report.status is Health.DATOS_DEGRADADOS
    assert set(report.reasons) == {
        "vela_esperada_ausente",
        "cotizacion_obsoleta",
        "canal_privado_obsoleto",
    }


def test_freshness_no_data_at_all_is_sin_conexion() -> None:
    report = evaluate_freshness(NOW_4H, None, None, None, Tolerances(), interval_ms=BAR_4H_MS)
    assert report.status is Health.SIN_CONEXION
    assert report.reasons == ["sin_datos"]
    assert should_block_entries(report) is True


def test_freshness_without_interval_skips_bar_presence_check() -> None:
    """Sin intervalo no se puede conocer la vela esperada; cotización y privado sí se miden."""
    report = evaluate_freshness(NOW_4H, PREV_CLOSE_4H, NOW_4H - 1_000, NOW_4H - 1_000, Tolerances())
    assert report.status is Health.SALUDABLE

    stale_quote = evaluate_freshness(NOW_4H, PREV_CLOSE_4H, NOW_4H - 31_000, NOW_4H - 1_000, Tolerances())
    assert stale_quote.status is Health.DATOS_DEGRADADOS


def test_freshness_interval_can_come_from_tolerances() -> None:
    tolerances = SimpleNamespace(candle_publish_s=60, quote_max_age_s=30, bar_interval_ms=BAR_4H_MS)
    now = LAST_CLOSE_4H + 61_000
    report = evaluate_freshness(now, PREV_CLOSE_4H, now - 1_000, now - 1_000, tolerances)
    assert report.status is Health.DATOS_DEGRADADOS
    assert "vela_esperada_ausente" in report.reasons


@pytest.mark.parametrize("status", list(Health))
def test_should_block_entries_blocks_everything_not_healthy(status: Health) -> None:
    report = HealthReport(status=status, reasons=[], ts_ms=NOW_4H)
    assert should_block_entries(report) is (status is not Health.SALUDABLE)


def test_should_block_entries_without_report_blocks() -> None:
    assert should_block_entries(None) is True
