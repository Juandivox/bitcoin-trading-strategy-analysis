"""Primitivas de supervisión del bot (spec v2.0 §12/§13).

* ``lock``    -> ``SingleWriterLock``: escritor único por run (RF-SEG-06, CA-29).
* ``state``   -> ``StateMachine``: estados persistidos del run (spec §12, RF-REC-06).
* ``control`` -> ``ControlFile``: canal local CLI -> proceso (RF-MON-04).
* ``health``  -> frescura de datos y bloqueo de entradas (RF-DAT-05, RF-MON-03).
"""
from __future__ import annotations

from app.supervision.control import ACTIONS, ControlFile, ControlFileError
from app.supervision.health import (
    evaluate_freshness,
    expected_last_closed_bar_close_ms,
    should_block_entries,
)
from app.supervision.lock import LockHeldError, SingleWriterLock
from app.supervision.state import (
    TERMINAL_STATES,
    TRANSITIONS,
    InvalidTransition,
    StateMachine,
)

__all__ = [
    "ACTIONS",
    "ControlFile",
    "ControlFileError",
    "InvalidTransition",
    "LockHeldError",
    "SingleWriterLock",
    "StateMachine",
    "TERMINAL_STATES",
    "TRANSITIONS",
    "evaluate_freshness",
    "expected_last_closed_bar_close_ms",
    "should_block_entries",
]
