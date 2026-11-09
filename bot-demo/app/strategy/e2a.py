"""Port a numpy de la estrategia de investigación E2-A para el bot en vivo.

Fuente de verdad replicada 1:1 (no se reinventa ninguna fórmula):

- ``src/features/technical.py::cci``    -> CCI con *doble* media móvil.
- ``src/features/technical.py::sma``    -> media móvil simple.
- ``src/strategies/e2a_composite.py``   -> ``volume_zscore`` y ``signal_e2a_long``.

Semántica polars -> numpy (ver ``tests/test_strategy_equivalence.py``):

- ``tp = (high + low + close) / 3``
- ``sma_tp = SMA(tp, cci_period)``
- ``md = SMA(|tp - sma_tp|, cci_period)``   (segunda media móvil de la desviación,
  NO la desviación media clásica de una sola pasada)
- ``cci = (tp - sma_tp) / (0.015 * md)``
- ``vol_z = (volume - SMA(volume, w)) / STD(volume, w)`` con ``ddof=1``, porque
  ``polars.rolling_std`` usa ``ddof=1`` por defecto (numpy usa ``ddof=0``).
- ``entry[t] = cci[t-1] < cci_entry and cci[t] > cci_entry and trend_vol[t]``
  con ``trend_vol[t] = sma_fast[t] > sma_slow[t] and vol_z[t] > vol_z_thr``.
- ``exit[t]  = cci[t] > cci_exit or sma_fast[t] < sma_slow[t]``
- Estado: ``entry -> 1``; si no ``exit -> 0``; si no, se conserva el anterior.
  La entrada tiene prioridad sobre la salida en la misma barra (``when/then``
  encadenado de polars) y el estado arranca en 0.
- Cualquier comparación con NaN es False, igual que ``null`` en polars: nunca se
  lanza excepción por NaN.

Nota numérica (no semántica): polars calcula los rolling con un kernel
incremental y este port usa ventanas explícitas; la diferencia observada en los
19.800 datos reales de BTCUSDT 4h es <= 5e-11 en valor absoluto (redondeo de
coma flotante). La señal 0/1 resultante es idéntica bar a bar.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike

from app.config import StrategyParams

__all__ = [
    "Indicators",
    "compute_indicators",
    "signal_events",
    "resolve_states",
    "target_position",
    "latest_diagnostics",
]


@dataclass(frozen=True)
class Indicators:
    """Indicadores alineados bar a bar con la serie de entrada.

    Todos son ``float64``; ``NaN`` significa "aún no disponible" (warmup), con
    la misma semántica que ``null`` en polars.
    """

    cci: np.ndarray
    sma_fast: np.ndarray
    sma_slow: np.ndarray
    vol_z: np.ndarray


def _as_float64(x: ArrayLike, name: str) -> np.ndarray:
    arr = np.asarray(x, dtype=np.float64).reshape(-1)
    if arr.size == 0:
        raise ValueError(f"{name} está vacío")
    return arr


def _check_same_length(**series: np.ndarray) -> int:
    sizes = {name: arr.size for name, arr in series.items()}
    if len(set(sizes.values())) != 1:
        raise ValueError(f"largo inconsistente entre series: {sizes}")
    return next(iter(sizes.values()))


def _rolling_mean(x: np.ndarray, window: int) -> np.ndarray:
    """SMA fiel a ``pl.Expr.rolling_mean(window_size=window, min_samples=window)``.

    Devuelve NaN si la ventana no está completa o si contiene algún NaN (en
    polars, un ``null`` dentro de la ventana también produce ``null``).
    """
    n = x.size
    out = np.full(n, np.nan, dtype=np.float64)
    if window < 1 or n < window:
        return out
    for i in range(window - 1, n):
        out[i] = x[i - window + 1 : i + 1].mean()
    return out


def _rolling_std(x: np.ndarray, window: int, ddof: int = 1) -> np.ndarray:
    """Desviación estándar rolling fiel a ``pl.Expr.rolling_std`` (``ddof=1``)."""
    n = x.size
    out = np.full(n, np.nan, dtype=np.float64)
    if window < 1 or n < window or window <= ddof:
        return out
    for i in range(window - 1, n):
        out[i] = x[i - window + 1 : i + 1].std(ddof=ddof)
    return out


def _volume_zscore(volume: np.ndarray, window: int) -> np.ndarray:
    mu = _rolling_mean(volume, window)
    sigma = _rolling_std(volume, window, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return (volume - mu) / sigma


def compute_indicators(
    high: ArrayLike,
    low: ArrayLike,
    close: ArrayLike,
    volume: ArrayLike,
    params: StrategyParams,
) -> Indicators:
    """Calcula CCI, SMAs y z-score de volumen replicando ``signal_e2a_long``."""
    high = _as_float64(high, "high")
    low = _as_float64(low, "low")
    close = _as_float64(close, "close")
    volume = _as_float64(volume, "volume")
    _check_same_length(high=high, low=low, close=close, volume=volume)

    tp = (high + low + close) / 3.0
    sma_tp = _rolling_mean(tp, params.cci_period)
    md = _rolling_mean(np.abs(tp - sma_tp), params.cci_period)
    with np.errstate(divide="ignore", invalid="ignore"):
        cci = (tp - sma_tp) / (0.015 * md)

    return Indicators(
        cci=cci,
        sma_fast=_rolling_mean(close, params.sma_fast),
        sma_slow=_rolling_mean(close, params.sma_slow),
        vol_z=_volume_zscore(volume, params.vol_window),
    )


def signal_events(
    ind: Indicators, params: StrategyParams
) -> tuple[np.ndarray, np.ndarray]:
    """Eventos de entrada/salida por barra (bool, NaN => False).

    ``entry[t]`` exige el cruce de CCI respecto a la barra anterior más
    tendencia y volumen confirmados; ``exit[t]`` es la condición de salida.
    """
    n = _check_same_length(
        cci=ind.cci, sma_fast=ind.sma_fast, sma_slow=ind.sma_slow, vol_z=ind.vol_z
    )
    cci = ind.cci

    cci_prev = np.full(n, np.nan, dtype=np.float64)
    if n > 1:
        cci_prev[1:] = cci[:-1]

    trend_vol = (ind.sma_fast > ind.sma_slow) & (ind.vol_z > params.vol_z_thr)
    entry = (cci_prev < params.cci_entry) & (cci > params.cci_entry) & trend_vol
    exit_ = (cci > params.cci_exit) | (ind.sma_fast < ind.sma_slow)
    return entry, exit_


def resolve_states(
    prev_state: int, entry_events: ArrayLike, exit_events: ArrayLike
) -> np.ndarray:
    """Resuelve el estado 0/1 barra a barra: entrada -> salida -> conserva.

    ``prev_state`` es el estado *antes* de la primera barra del array (0 en un
    arranque en frío). La entrada tiene prioridad sobre la salida en la misma
    barra, igual que el ``when/then`` encadenado de polars.
    """
    entry = np.asarray(entry_events)
    exit_ = np.asarray(exit_events)
    if entry.dtype != np.bool_ or exit_.dtype != np.bool_:
        raise TypeError("entry_events y exit_events deben ser arrays booleanos")
    entry = entry.reshape(-1)
    exit_ = exit_.reshape(-1)
    if entry.size != exit_.size:
        raise ValueError(
            f"entry_events y exit_events difieren en largo: {entry.size} != {exit_.size}"
        )
    if prev_state not in (0, 1):
        raise ValueError(f"prev_state debe ser 0 o 1, recibido {prev_state!r}")

    out = np.empty(entry.size, dtype=np.int8)
    state = int(prev_state)
    for i in range(entry.size):
        if entry[i]:
            state = 1
        elif exit_[i]:
            state = 0
        out[i] = state
    return out


def target_position(
    high: ArrayLike,
    low: ArrayLike,
    close: ArrayLike,
    volume: ArrayLike,
    params: StrategyParams,
    prev_state: int,
) -> int:
    """Posición objetivo 0/1 de la ÚLTIMA barra cerrada de la ventana.

    La ventana debe tener al menos ``params.warmup_bars`` filas para que todos
    los indicadores estén disponibles; con menos filas no hay entrada posible y
    el resultado es ``prev_state`` (las salidas tampoco pueden dispararse sin
    indicadores válidos).
    """
    ind = compute_indicators(high, low, close, volume, params)
    entry, exit_ = signal_events(ind, params)
    states = resolve_states(prev_state, entry, exit_)
    return int(states[-1])


def latest_diagnostics(
    high: ArrayLike,
    low: ArrayLike,
    close: ArrayLike,
    volume: ArrayLike,
    params: StrategyParams,
    prev_state: int,
) -> dict:
    """Diagnóstico de la última barra para logs/auditoría del bot.

    ``action`` refleja la transición efectiva del estado (lo que el bot debe
    hacer): ``ENTRY`` si pasa de 0 a 1, ``EXIT`` si pasa de 1 a 0 y ``HOLD`` si
    el objetivo coincide con ``prev_state`` (aunque haya eventos repetidos).
    """
    ind = compute_indicators(high, low, close, volume, params)
    entry, exit_ = signal_events(ind, params)
    states = resolve_states(prev_state, entry, exit_)
    i = states.size - 1

    entry_event = bool(entry[i])
    exit_event = bool(exit_[i])
    target = int(states[i])
    prev = int(prev_state)

    if target == 1 and prev == 0:
        action = "ENTRY"
        reason = (
            f"cci cruzo {params.cci_entry} al alza "
            f"({ind.cci[i - 1]:.4f} -> {ind.cci[i]:.4f}) con sma_fast > sma_slow "
            f"y vol_z({ind.vol_z[i]:.4f}) > {params.vol_z_thr}"
        )
    elif target == 0 and prev == 1:
        action = "EXIT"
        if ind.cci[i] > params.cci_exit:
            reason = f"cci({ind.cci[i]:.4f}) > cci_exit({params.cci_exit})"
        else:
            reason = (
                f"sma_fast({ind.sma_fast[i]:.4f}) < sma_slow({ind.sma_slow[i]:.4f})"
            )
    else:
        action = "HOLD"
        if entry_event:
            reason = "entrada repetida: se mantiene LONG"
        elif exit_event:
            reason = "salida sin posicion: se mantiene FLAT"
        else:
            reason = "sin cruce de cci ni cambio de tendencia"

    return {
        "cci": float(ind.cci[i]),
        "sma_fast": float(ind.sma_fast[i]),
        "sma_slow": float(ind.sma_slow[i]),
        "vol_z": float(ind.vol_z[i]),
        "entry_event": entry_event,
        "exit_event": exit_event,
        "target_position": target,
        "prev_state": prev,
        "action": action,
        "reason": reason,
    }
