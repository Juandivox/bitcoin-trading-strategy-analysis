"""Equivalencia exacta entre el port numpy del bot y la investigación E2-A (polars).

Verifica, sobre los 19.800 datos reales de ``data/processed/btcusdt_4h.parquet``
(BTCUSDT 4h), que:

1. ``signal_e2a_long`` (polars, investigación) y
   ``compute_indicators`` + ``signal_events`` + ``resolve_states`` (numpy, bot)
   producen la MISMA posición 0/1 en cada una de las 19.800 barras.
2. Las primeras ``sma_slow - 1`` posiciones son 0 (warmup sin tendencia).
3. ``target_position`` con ventanas móviles reproduce la señal de investigación
   barra a barra (prueba incremental, ~300 índices con bordes de warmup fijos y
   aleatorios con semilla fija).
4. Una ventana corta (250 filas) no lanza excepción y coincide con la
   investigación calculada sobre esa misma ventana.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import numpy as np
import pytest

pl = pytest.importorskip("polars", reason="test de desarrollo: requiere el venv de investigación")
pytest.importorskip("src.strategies.e2a_composite", reason="requiere el repo de investigación")

from app.config import E2A_PSO, STRATEGY_VARIANTS
from app.strategy.e2a import (
    Indicators,
    compute_indicators,
    latest_diagnostics,
    resolve_states,
    signal_events,
    target_position,
)
from src.features.technical import cci as research_cci
from src.features.technical import sma as research_sma
from src.strategies.e2a_composite import signal_e2a_long, volume_zscore

REPO = Path(__file__).resolve().parents[2]
DATASET = REPO / "data" / "processed" / "btcusdt_4h.parquet"

if not DATASET.exists():  # pragma: no cover - entorno de imagen sin dataset
    pytest.skip(f"dataset de investigación ausente: {DATASET}", allow_module_level=True)

N_BARS = 19_800
VARIANTS = sorted(STRATEGY_VARIANTS)
INCREMENTAL_WINDOW = 500
INCREMENTAL_BARS = 300
SHORT_WINDOW_START = 200
SHORT_WINDOW_BARS = 250
RANDOM_SEED = 20260923


@pytest.fixture(scope="module")
def df4h() -> pl.DataFrame:
    assert DATASET.exists(), f"falta el dataset {DATASET}"
    df = pl.read_parquet(DATASET).sort("timestamp")
    assert df.height == N_BARS, f"se esperaban {N_BARS} filas, hay {df.height}"
    ts = df["timestamp"].to_numpy()
    assert np.all(np.diff(ts) > np.timedelta64(0, "ns")), "timestamp no es estrictamente creciente"
    return df


def _ohlcv(df: pl.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    return (
        df["high"].to_numpy(),
        df["low"].to_numpy(),
        df["close"].to_numpy(),
        df["volume"].to_numpy(),
    )


def _research_signal(df: pl.DataFrame, params) -> np.ndarray:
    return signal_e2a_long(df, **asdict(params))["signal_e2a"].to_numpy()


def _numpy_signal(df: pl.DataFrame, params, prev_state: int = 0):
    high, low, close, volume = _ohlcv(df)
    ind = compute_indicators(high, low, close, volume, params)
    entry, exit_ = signal_events(ind, params)
    return ind, resolve_states(prev_state, entry, exit_)


def _mismatch_report(
    mismatch_idx: np.ndarray, research: np.ndarray, numpy_signal: np.ndarray, ind: Indicators
) -> str:
    return "\n".join(
        f"  bar {int(i)}: research={int(research[i])} numpy={int(numpy_signal[i])} "
        f"cci={ind.cci[i]!r} sma_fast={ind.sma_fast[i]!r} "
        f"sma_slow={ind.sma_slow[i]!r} vol_z={ind.vol_z[i]!r}"
        for i in mismatch_idx[:5]
    )


@pytest.mark.parametrize("variant", VARIANTS)
def test_signal_matches_research_exactly(df4h: pl.DataFrame, variant: str) -> None:
    params = STRATEGY_VARIANTS[variant]
    research = _research_signal(df4h, params)
    ind, numpy_signal = _numpy_signal(df4h, params)

    mismatches = np.flatnonzero(research != numpy_signal)
    assert mismatches.size == 0, (
        f"{variant}: {mismatches.size} discrepancias polars vs numpy "
        f"(primeras {min(5, mismatches.size)}):\n"
        + _mismatch_report(mismatches, research, numpy_signal, ind)
    )
    assert np.array_equal(research, numpy_signal)
    assert numpy_signal.shape == (N_BARS,)
    assert numpy_signal.dtype == np.int8
    assert set(np.unique(numpy_signal)).issubset({0, 1})
    assert 0 < int(research.sum()) < N_BARS, "señal trivial (todo 0 o todo 1)"

    warmup = params.sma_slow - 1
    assert np.all(numpy_signal[:warmup] == 0), f"{variant}: hay posición antes del warmup"


@pytest.mark.parametrize("variant", VARIANTS)
def test_indicators_match_research_within_float_rounding(
    df4h: pl.DataFrame, variant: str
) -> None:
    params = STRATEGY_VARIANTS[variant]
    ind, _ = _numpy_signal(df4h, params)
    reference = df4h.select(
        [
            research_cci(
                pl.col("high"), pl.col("low"), pl.col("close"), params.cci_period
            ).alias("cci"),
            research_sma(pl.col("close"), params.sma_fast).alias("sma_fast"),
            research_sma(pl.col("close"), params.sma_slow).alias("sma_slow"),
            volume_zscore(pl.col("volume"), params.vol_window).alias("vol_z"),
        ]
    )
    for name in ("cci", "sma_fast", "sma_slow", "vol_z"):
        got = getattr(ind, name)
        expected = reference[name].to_numpy()
        assert np.array_equal(np.isnan(got), np.isnan(expected)), (
            f"{variant}/{name}: patrón de NaN distinto entre polars y numpy"
        )
        max_diff = float(np.nanmax(np.abs(got - expected)))
        assert np.allclose(got, expected, rtol=1e-9, atol=1e-6, equal_nan=True), (
            f"{variant}/{name}: diferencia máxima {max_diff!r} excede el redondeo "
            "de coma flotante esperado (<1e-6 absoluto)"
        )


@pytest.mark.parametrize("variant", VARIANTS)
def test_target_position_incremental_matches_research(
    df4h: pl.DataFrame, variant: str
) -> None:
    params = STRATEGY_VARIANTS[variant]
    research = _research_signal(df4h, params)
    n = research.size

    rng = np.random.default_rng(RANDOM_SEED)
    edge_idx = {
        0,
        1,
        2,
        params.warmup_bars - 2,
        params.warmup_bars - 1,
        params.warmup_bars,
        params.warmup_bars + 1,
    }
    idx = sorted(
        {i for i in edge_idx if 0 <= i < n}
        | {int(i) for i in rng.integers(0, n, size=INCREMENTAL_BARS)}
    )
    assert len(idx) >= INCREMENTAL_BARS

    high, low, close, volume = _ohlcv(df4h)
    failures: list[tuple[int, int, int, int]] = []
    for i in idx:
        lo = max(0, i - INCREMENTAL_WINDOW)
        prev_state = int(research[i - 1]) if i > 0 else 0
        got = target_position(
            high[lo : i + 1],
            low[lo : i + 1],
            close[lo : i + 1],
            volume[lo : i + 1],
            params,
            prev_state,
        )
        if got != int(research[i]):
            failures.append((i, got, int(research[i]), prev_state))

    assert not failures, (
        f"{variant}: target_position discrepa en {len(failures)}/{len(idx)} índices "
        f"(bar, numpy, research, prev_state): {failures[:10]}"
    )


@pytest.mark.parametrize("variant", VARIANTS)
def test_short_window_matches_research_on_same_window(
    df4h: pl.DataFrame, variant: str
) -> None:
    params = STRATEGY_VARIANTS[variant]
    warmup = params.warmup_bars

    window = df4h.slice(SHORT_WINDOW_START, SHORT_WINDOW_BARS)
    research = _research_signal(window, params)
    _, numpy_signal = _numpy_signal(window, params)
    assert numpy_signal.size == SHORT_WINDOW_BARS
    assert np.array_equal(research[warmup - 1 :], numpy_signal[warmup - 1 :]), (
        f"{variant}: la ventana corta de {SHORT_WINDOW_BARS} filas no reproduce "
        "la investigación calculada sobre esa misma ventana"
    )
    assert research[warmup - 1 :].sum() > 0, "ventana de prueba sin actividad"

    exact = df4h.slice(SHORT_WINDOW_START, warmup)
    high, low, close, volume = _ohlcv(exact)
    got = target_position(high, low, close, volume, params, prev_state=0)
    expected = int(_research_signal(exact, params)[-1])
    assert got == expected, (
        f"{variant}: frontera warmup_bars={warmup} filas -> numpy={got} research={expected}"
    )


@pytest.mark.parametrize("variant", VARIANTS)
def test_latest_diagnostics_is_consistent(df4h: pl.DataFrame, variant: str) -> None:
    params = STRATEGY_VARIANTS[variant]
    research = _research_signal(df4h, params)
    high, low, close, volume = _ohlcv(df4h)
    prev_state = int(research[-2])

    diag = latest_diagnostics(high, low, close, volume, params, prev_state)
    assert set(diag) == {
        "cci",
        "sma_fast",
        "sma_slow",
        "vol_z",
        "entry_event",
        "exit_event",
        "target_position",
        "prev_state",
        "action",
        "reason",
    }
    assert diag["target_position"] == int(research[-1])
    assert diag["target_position"] == target_position(
        high, low, close, volume, params, prev_state
    )
    assert diag["prev_state"] == prev_state
    assert diag["action"] in {"ENTRY", "EXIT", "HOLD"}
    expected_action = (
        "ENTRY"
        if (diag["target_position"], prev_state) == (1, 0)
        else "EXIT"
        if (diag["target_position"], prev_state) == (0, 1)
        else "HOLD"
    )
    assert diag["action"] == expected_action
    assert isinstance(diag["reason"], str) and diag["reason"]
    for key in ("cci", "sma_fast", "sma_slow", "vol_z"):
        assert isinstance(diag[key], float)


def test_resolve_states_semantics() -> None:
    entry = np.array([False, True, False, False, True], dtype=bool)
    exit_ = np.array([False, False, True, False, True], dtype=bool)
    states = resolve_states(0, entry, exit_)
    assert states.tolist() == [0, 1, 0, 0, 1], "la entrada debe ganar sobre la salida"
    assert states.dtype == np.int8

    hold = np.zeros(3, dtype=bool)
    assert resolve_states(1, hold, hold).tolist() == [1, 1, 1]
    assert resolve_states(1, hold, np.array([True, False, False])).tolist() == [0, 0, 0]

    with pytest.raises(TypeError):
        resolve_states(0, np.array([np.nan]), np.array([False]))
    with pytest.raises(ValueError):
        resolve_states(2, hold, hold)
    with pytest.raises(ValueError):
        resolve_states(0, hold, np.zeros(4, dtype=bool))


def test_nan_comparisons_are_false_and_do_not_raise() -> None:
    nan = np.full(5, np.nan, dtype=np.float64)
    ind = Indicators(cci=nan.copy(), sma_fast=nan.copy(), sma_slow=nan.copy(), vol_z=nan.copy())
    entry, exit_ = signal_events(ind, E2A_PSO)
    assert not entry.any()
    assert not exit_.any()
    assert resolve_states(1, entry, exit_).tolist() == [1, 1, 1, 1, 1]
    assert resolve_states(0, entry, exit_).tolist() == [0, 0, 0, 0, 0]
