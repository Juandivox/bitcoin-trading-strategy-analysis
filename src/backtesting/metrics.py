"""
src/backtesting/metrics.py

Fuente única de verdad para las metricas de performance del proyecto.

Convencion (ver docs/03_backtesting_y_validacion.md):

    r_t      = close_t / close_{t-1} - 1        (retorno simple por vela)
    rf_vela  = rf_annual / P                    (tasa libre de riesgo por vela)
    exceso_t = r_t - rf_annual / P
    Sharpe   = mean(exceso) / std(exceso, ddof=1) * sqrt(P)

donde P es el numero de velas por anio de la serie que se esta midiendo.
P NO se escribe a mano: se deduce del espaciado mediano entre timestamps
(``periods_per_year``), de modo que 1m -> 525.600 y 4h -> 2.190 sin riesgo
de mezclar temporalidades.

Reglas del proyecto:
- Todo el analisis se hace en 4H (timeframe canonico en configs/strategies.yaml).
- ``rf_annual`` es obligatorio: no existe un rf=0 implicito. Para reproducir
  resultados historicos hay que pasarlo explicitamente.
- Las metricas de acierto (win rate, profit factor) son POR OPERACION, no por
  vela. Una operacion va desde la entrada (0->1) hasta la salida (1->0),
  incluyendo el costo de salida.
- Sortino se elimino del proyecto (no se reporta).
"""
from __future__ import annotations

from datetime import timezone

import numpy as np
import polars as pl

DAYS_PER_YEAR = 365.0
SECONDS_PER_DAY = 86_400.0

# Velas por anio para las temporalidades que usa el proyecto (crypto 24/7).
TIMEFRAME_PERIODS: dict[str, int] = {
    "1m": 525_600,
    "3m": 175_200,
    "5m": 105_120,
    "15m": 35_040,
    "30m": 17_520,
    "1h": 8_760,
    "2h": 4_380,
    "4h": 2_190,
    "6h": 1_460,
    "8h": 1_095,
    "12h": 730,
    "1d": 365,
}


# --------------------------------------------------------------------------- #
# Resolucion del numero de periodos por anio (P)
# --------------------------------------------------------------------------- #
def _datetime_to_ns(value) -> int:
    """Convierte un datetime de Python a nanosegundos desde epoch (UTC)."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.timestamp() * 1_000_000_000)


def _timestamps_to_ns(timestamps) -> np.ndarray:
    if isinstance(timestamps, pl.Series):
        arr = timestamps.to_numpy()
    else:
        arr = np.asarray(timestamps)

    if arr.dtype.kind == "M":  # datetime64
        return arr.astype("datetime64[ns]").astype(np.int64)

    if arr.dtype == object:
        return np.array([_datetime_to_ns(t) for t in arr], dtype=np.int64)

    # Si ya vienen numeros, se asume nanosegundos.
    return arr.astype(np.int64)


def periods_per_year(timestamps) -> int:
    """Deduce P a partir del espaciado MEDIANO entre velas.

    Usa la mediana (no la media) porque los datos de Binance tienen huecos y
    outliers; la mediana devuelve la temporalidad real de la serie.
    """
    ns = _timestamps_to_ns(timestamps)
    if ns.size < 2:
        raise ValueError("Se necesitan al menos 2 timestamps para deducir P.")
    deltas = np.diff(ns)
    deltas = deltas[deltas > 0]
    if deltas.size == 0:
        raise ValueError("Los timestamps no son crecientes; no se puede deducir P.")

    median_seconds = float(np.median(deltas)) / 1_000_000_000.0
    if median_seconds <= 0:
        raise ValueError("Espaciado mediano no positivo; revisar timestamps.")

    p = int(round(DAYS_PER_YEAR * SECONDS_PER_DAY / median_seconds))
    if p < 1:
        raise ValueError(f"P calculado no valido: {p}")
    return p


def timeframe_from_periods(p: int) -> str:
    """Etiqueta legible ('4h', '1m', ...) para un P dado; 'custom' si no coincide."""
    for name, value in TIMEFRAME_PERIODS.items():
        if value == p:
            return name
    return f"custom({p})"


def _resolve_periods(timestamps, p: int | None) -> int:
    if p is not None:
        return int(p)
    if timestamps is None:
        raise ValueError(
            "Falta la temporalidad: pasa 'timestamps' o 'periods_per_year'. "
            "No se asume P por defecto (asi se evita mezclar 1m con 4h)."
        )
    return periods_per_year(timestamps)


def _require_rf(rf_annual: float | None) -> float:
    if rf_annual is None:
        raise ValueError(
            "rf_annual es obligatorio (ej. 0.04). No existe un rf=0 implicito; "
            "si necesitas reproducir resultados historicos, pasalo explicitamente."
        )
    return float(rf_annual)


def _clean_returns(returns) -> np.ndarray:
    if isinstance(returns, pl.Series):
        arr = returns.to_numpy()
    else:
        arr = np.asarray(returns)
    arr = arr.astype(np.float64, copy=False)
    return arr[np.isfinite(arr)]


# --------------------------------------------------------------------------- #
# Metricas
# --------------------------------------------------------------------------- #
def sharpe(
    returns,
    periods_per_year: int | None = None,
    *,
    rf_annual: float | None = None,
    timestamps=None,
) -> float:
    """Sharpe anualizado: (mean(exceso)/std(exceso, ddof=1)) * sqrt(P)."""
    rf = _require_rf(rf_annual)
    p = _resolve_periods(timestamps, periods_per_year)
    r = _clean_returns(returns)

    if r.size < 2:
        return 0.0

    excess = r - rf / p
    sd = float(np.std(excess, ddof=1))
    # Tolerancia: una serie constante deja residuo de redondeo (~1e-18) en std.
    if sd <= 1e-12 or not np.isfinite(sd):
        return 0.0
    return float(np.mean(excess) / sd * np.sqrt(p))


def cagr(
    equity,
    periods_per_year: int | None = None,
    *,
    timestamps=None,
) -> float:
    """Crecimiento anual compuesto: (equity_final/equity_inicial)^(1/anios) - 1."""
    eq = _clean_returns(equity)
    if eq.size < 2 or eq[0] <= 0:
        return 0.0

    p = _resolve_periods(timestamps, periods_per_year)
    years = eq.size / p
    if years <= 0:
        return 0.0

    total_return = eq[-1] / eq[0] - 1.0
    if total_return <= -1.0:
        return -1.0
    return float((1.0 + total_return) ** (1.0 / years) - 1.0)


def max_drawdown(equity) -> tuple[float, int]:
    """Retorna (max_drawdown_pct, duracion_en_barras)."""
    eq = _clean_returns(equity)
    if eq.size == 0:
        return 0.0, 0

    peak = np.maximum.accumulate(eq)
    dd = (eq - peak) / peak
    max_dd = float(np.min(dd))
    trough_idx = int(np.argmin(dd))
    peak_idx = int(np.argmax(eq[: trough_idx + 1]))
    return max_dd, trough_idx - peak_idx


def calmar(
    equity,
    periods_per_year: int | None = None,
    *,
    timestamps=None,
) -> float:
    """CAGR / |MaxDD|."""
    c = cagr(equity, timestamps=timestamps, periods_per_year=periods_per_year)
    mdd, _ = max_drawdown(equity)
    if mdd == 0.0:
        return float("inf") if c > 0 else 0.0
    return float(c / abs(mdd))


# --------------------------------------------------------------------------- #
# Metricas por operacion
# --------------------------------------------------------------------------- #
def _trade_returns(position: np.ndarray, returns: np.ndarray) -> tuple[list[float], int]:
    """Retorno compuesto de cada operacion y barras expuestas totales.

    Una operacion empieza en la vela donde position pasa de 0 a 1 y termina en
    la vela donde vuelve a 0 (esa vela incluye el costo de salida, porque el
    turnover se cobra alli). Si la operacion sigue abierta al final, cierra en
    la ultima vela sin costo de salida.
    """
    n = len(position)
    trades: list[float] = []
    exposed = 0
    i = 0
    while i < n:
        if position[i] != 1:
            i += 1
            continue

        entry = i
        while i + 1 < n and position[i + 1] == 1:
            i += 1
        exit_bar = min(i + 1, n - 1)
        exposed += i - entry + 1
        segment = returns[entry : exit_bar + 1]
        trades.append(float(np.prod(1.0 + segment) - 1.0))
        i = exit_bar + 1

    return trades, exposed


def trade_stats(position, returns) -> dict:
    """Estadisticas POR OPERACION (no por vela)."""
    pos = np.asarray(position)
    pos = np.nan_to_num(pos.astype(np.float64), nan=0.0)

    if isinstance(returns, pl.Series):
        ret = returns.to_numpy()
    else:
        ret = np.asarray(returns)
    ret = np.nan_to_num(ret.astype(np.float64), nan=0.0)

    trades, exposed = _trade_returns(pos, ret)
    arr = np.asarray(trades, dtype=np.float64)

    n_trades = int(arr.size)
    wins = arr[arr > 0]
    losses = arr[arr < 0]
    gross_profit = float(wins.sum()) if wins.size else 0.0
    gross_loss = float(abs(losses.sum())) if losses.size else 0.0

    if gross_loss > 0:
        profit_factor: float | None = gross_profit / gross_loss
    elif gross_profit > 0:
        profit_factor = None  # sin perdidas: se reporta como "—", no como inf
    else:
        profit_factor = 0.0

    return {
        "n_trades": n_trades,
        "win_rate": float(wins.size / n_trades) if n_trades else 0.0,
        "profit_factor": profit_factor,
        "avg_trade": float(arr.mean()) if n_trades else 0.0,
        "avg_holding_bars": float(exposed / n_trades) if n_trades else 0.0,
        "best_trade": float(arr.max()) if n_trades else 0.0,
        "worst_trade": float(arr.min()) if n_trades else 0.0,
    }


def exposure(position) -> float:
    """Fraccion de velas con posicion abierta."""
    pos = np.asarray(position)
    pos = np.nan_to_num(pos.astype(np.float64), nan=0.0)
    return float(np.mean(pos)) if pos.size else 0.0


# --------------------------------------------------------------------------- #
# Resumen completo (la tabla de la tesis)
# --------------------------------------------------------------------------- #
def summarize(
    bt_df: pl.DataFrame,
    *,
    rf_annual: float | None = None,
    ret_col: str = "strategy_ret",
    equity_col: str = "equity",
    position_col: str = "position",
    timestamp_col: str = "timestamp",
    periods_per_year: int | None = None,
) -> dict:
    """Resume un backtest con la convencion canonica del proyecto."""
    rf = _require_rf(rf_annual)

    timestamps = bt_df[timestamp_col] if timestamp_col in bt_df.columns else None
    p = _resolve_periods(timestamps, periods_per_year)

    # rets y pos se alinean por la MISMA mascara (la primera vela tiene
    # strategy_ret nulo pero position=0; si se hacen drop_nulls por separado
    # las series quedan desfasadas una fila).
    core = bt_df.select([ret_col, position_col]).drop_nulls([ret_col])
    rets = core[ret_col].to_numpy()
    pos = core[position_col].to_numpy()
    eq = bt_df[equity_col].drop_nulls().to_numpy()

    mdd, mdd_dur = max_drawdown(eq)
    th = trade_stats(pos, rets)

    turnover = float(bt_df["_turnover"].sum()) if "_turnover" in bt_df.columns else 0.0
    total_return = float(eq[-1] / eq[0] - 1.0) if eq.size > 1 else 0.0
    years = eq.size / p

    return {
        "n_bars": int(eq.size),
        "years": years,
        "trades": th["n_trades"],
        "exposure": round(exposure(bt_df[position_col].to_numpy()), 4),
        "final_equity": float(eq[-1]) if eq.size else 0.0,
        "total_return_%": total_return * 100.0,
        "CAGR_%": cagr(eq, periods_per_year=p) * 100.0,
        "sharpe": sharpe(rets, rf_annual=rf, periods_per_year=p),
        "maxDD_%": mdd * 100.0,
        "maxDD_bars": int(mdd_dur),
        "calmar": calmar(eq, periods_per_year=p),
        "win_rate_%": th["win_rate"] * 100.0,
        "profit_factor": th["profit_factor"],
        "avg_trade_%": th["avg_trade"] * 100.0,
        "avg_holding_bars": th["avg_holding_bars"],
        "turnover": turnover,
        "periods_per_year": p,
        "rf_annual": rf,
    }


# --------------------------------------------------------------------------- #
# Primitivas a nivel de vela (legado / notebooks historicos)
# --------------------------------------------------------------------------- #
def win_rate(returns) -> float:
    """Win rate a nivel de VELA (legado). La tesis usa trade_stats()."""
    nexos = _clean_returns(returns)
    nexos = nexos[nexos != 0]
    if nexos.size == 0:
        return 0.0
    return float(np.mean(nexos > 0))


def profit_factor(returns) -> float | None:
    """Profit factor a nivel de VELA (legado). La tesis usa trade_stats()."""
    nexos = _clean_returns(returns)
    gains = float(nexos[nexos > 0].sum()) if nexos.size else 0.0
    losses = float(abs(nexos[nexos < 0].sum())) if nexos.size else 0.0
    if losses == 0:
        return None if gains > 0 else 0.0
    return gains / losses
