"""
src/backtesting/engine.py

Motor de backtesting vectorizado (event-driven simplificado).
Recibe: timestamp, signal, price (close)
Calcula: position (con lag), PnL, equity curve.

Incluye fees + slippage via costs.py (opcional).
Evita look-ahead: signal en t -> position en t+lag.

Metricas via metrics.py
"""
from __future__ import annotations
import polars as pl
import numpy as np

def backtest(
    df: pl.DataFrame,
    signal_col: str = "signal",
    price_col: str = "close",
    timestamp_col: str = "timestamp",
    initial_capital: float = 10_000.0,
    fee_bps: float = 10.0,       # 10 bps = 0.10%
    slippage_bps: float = 5.0,   # 5 bps
    lag: int = 1,
    allow_short: bool = True,
) -> pl.DataFrame:
    """
    Retorna DataFrame con equity curve y retornos.
    """
    df = df.sort(timestamp_col).with_columns(
        pl.col(signal_col).shift(lag).fill_null(0).alias("_position_raw")
    )
    if not allow_short:
        df = df.with_columns(pl.col("_position_raw").clip(lower_bound=0).alias("_position_raw"))

    # position = signal desplazado
    df = df.with_columns(pl.col("_position_raw").alias("position"))

    # retornos de precio
    df = df.with_columns(
        (pl.col(price_col) / pl.col(price_col).shift(1) - 1).alias("_ret")
    )
    # PnL bruto por periodo: position_{t-1} * ret_t  (ya que position es lagged)
    # En vectorizado: position * _ret (position ya es lagged signal)
    df = df.with_columns(
        (pl.col("position") * pl.col("_ret")).alias("_gross_ret")
    )
    # costos: turnover * (fee + slippage)
    df = df.with_columns(
        (pl.col("position").diff().abs().fill_null(0)).alias("_turnover")
    )
    cost_rate = (fee_bps + slippage_bps) / 10_000
    df = df.with_columns(
        (pl.col("_turnover") * cost_rate).alias("_cost")
    )
    df = df.with_columns(
        (pl.col("_gross_ret") - pl.col("_cost")).alias("strategy_ret")
    )
    # equity
    df = df.with_columns(
        (1 + pl.col("strategy_ret").fill_null(0)).cum_prod().alias("_growth")
    )
    df = df.with_columns(
        (pl.col("_growth") * initial_capital).alias("equity")
    )
    # buy & hold benchmark
    df = df.with_columns(
        (pl.col(price_col) / pl.col(price_col).first()).alias("_bh_growth")
    )
    df = df.with_columns(
        (pl.col("_bh_growth") * initial_capital).alias("bh_equity")
    )
    return df

def backtest_from_predictions(
    pred_df: pl.DataFrame,
    price_col: str = "close",
    signal_col: str = "signal_ml",
    **kwargs,
) -> pl.DataFrame:
    return backtest(pred_df, signal_col=signal_col, price_col=price_col, **kwargs)
