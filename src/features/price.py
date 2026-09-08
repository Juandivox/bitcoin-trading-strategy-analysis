"""
src/features/price.py

Features de precio: retornos, log-retornos, gaps.
Sin look-ahead: retorno en t usa close[t] / close[t-n]
"""
from __future__ import annotations
import polars as pl
import numpy as np

def add_price_features(df: pl.DataFrame, periods: list[int] = [1,5,15,60,240], log: bool = True) -> pl.DataFrame:
    df = df.sort("timestamp")
    for n in periods:
        df = df.with_columns(
            (pl.col("close") / pl.col("close").shift(n) - 1).alias(f"return_{n}m")
        )
        if log:
            df = df.with_columns(
                (pl.col("close").log() - pl.col("close").shift(n).log()).alias(f"log_return_{n}m")
            )
    # gap intraday (para 1m es 0 salvo gaps reales)
    df = df.with_columns(
        (pl.col("open") / pl.col("close").shift(1) - 1).alias("gap_1m")
    )
    return df
