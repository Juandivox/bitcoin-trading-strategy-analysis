"""
src/strategies/trend_following.py

Estrategia de seguimiento de tendencia (SMA crossover + filtro ATR/vol).
Genera senales {-1,0,1} sin look-ahead.

Senal en t se calcula con info hasta t, se ejecuta en t+lag (default 1).
"""
from __future__ import annotations
import polars as pl

def signal_trend_following(
    df: pl.DataFrame,
    fast: int = 20,
    slow: int = 60,
    atr_period: int = 14,
    atr_multiplier: float = 1.5,
) -> pl.DataFrame:
    df = df.sort("timestamp")
    # Asegurar SMAs existen, si no calcular
    if f"sma_{fast}" not in df.columns:
        df = df.with_columns(pl.col("close").rolling_mean(window_size=fast, min_samples=fast).alias(f"sma_{fast}"))
    if f"sma_{slow}" not in df.columns:
        df = df.with_columns(pl.col("close").rolling_mean(window_size=slow, min_samples=slow).alias(f"sma_{slow}"))
    if "atr_14" not in df.columns:
        # true range rapido
        df = df.with_columns([
            (pl.col("high")-pl.col("low")).alias("_tr1"),
            ((pl.col("high")-pl.col("close").shift(1)).abs()).alias("_tr2"),
            ((pl.col("low")-pl.col("close").shift(1)).abs()).alias("_tr3"),
        ])
        df = df.with_columns(pl.max_horizontal("_tr1","_tr2","_tr3").alias("true_range"))
        df = df.with_columns(pl.col("true_range").rolling_mean(window_size=atr_period, min_samples=atr_period).alias("atr_14"))
        df = df.drop(["_tr1","_tr2","_tr3","true_range"])

    df = df.with_columns([
        (pl.col(f"sma_{fast}") > pl.col(f"sma_{slow}")).alias("_fast_above"),
        (pl.col(f"sma_{fast}") < pl.col(f"sma_{slow}")).alias("_fast_below"),
    ])
    # Filtro: solo tomar senal si distancia entre MAs > atr * mult (evita whipsaw)
    df = df.with_columns(
        ((pl.col(f"sma_{fast}") - pl.col(f"sma_{slow}")).abs() > pl.col("atr_14") * atr_multiplier).alias("_strong")
    )
    df = df.with_columns(
        pl.when(pl.col("_fast_above") & pl.col("_strong")).then(1)
        .when(pl.col("_fast_below") & pl.col("_strong")).then(-1)
        .otherwise(0)
        .alias("signal_trend")
    )
    return df.drop(["_fast_above","_fast_below","_strong"])
