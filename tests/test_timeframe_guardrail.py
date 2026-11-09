"""
tests/test_timeframe_guardrail.py

Verifica el guardrail que impide mezclar temporalidades en el generador v3.
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import polars as pl
import pytest

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc


def _load_run_resultados():
    spec = importlib.util.spec_from_file_location(
        "run_resultados", ROOT / "scripts" / "run_resultados.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _frame(step_hours: float, n: int = 20) -> pl.DataFrame:
    start = datetime(2020, 1, 1, tzinfo=UTC)
    ts = [start + timedelta(hours=step_hours * i) for i in range(n)]
    return pl.DataFrame({"timestamp": pl.Series(ts), "close": [1.0] * n})


def test_guardrail_acepta_4h():
    mod = _load_run_resultados()
    assert mod.validate_timeframe(_frame(4.0), "4h") == 2190


def test_guardrail_aborta_si_los_datos_son_1m_y_el_config_4h():
    mod = _load_run_resultados()
    with pytest.raises(SystemExit, match="GUARDRAIL"):
        mod.validate_timeframe(_frame(1.0 / 60.0), "4h")


def test_guardrail_aborta_si_los_datos_son_4h_y_el_config_1m():
    mod = _load_run_resultados()
    with pytest.raises(SystemExit, match="GUARDRAIL"):
        mod.validate_timeframe(_frame(4.0), "1m")
