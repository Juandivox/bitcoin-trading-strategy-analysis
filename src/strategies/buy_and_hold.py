"""
src/strategies/buy_and_hold.py

Benchmark: hold BTC con el capital (fiel a notebooks/05-06).
Señal siempre LONG (1) desde la primera vela con datos validos.
Sirve como tercera pata de la comparacion: si BH (CAGR ~40%, MaxDD -30%)
supera a la estrategia en CAGR neto y Sharpe, la estrategia no aporta alpha.
"""
from __future__ import annotations
import polars as pl


def signal_buy_and_hold(df: pl.DataFrame) -> pl.DataFrame:
    df = df.sort("timestamp")
    return df.with_columns(pl.lit(1, dtype=pl.Int8).alias("signal_bh"))
