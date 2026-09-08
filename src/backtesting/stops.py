"""
src/backtesting/stops.py

Risk Engine ATR (fiel a notebooks/06, celda 22).
Mismo risk para todas las estrategias para que gane la señal, no el risk.

Stop long-only: stop = entry_price - k * ATR_entry.
La entrada se detecta cuando position pasa 0 -> 1; entry y ATR se propagan
con forward-fill. Si close < stop estando long -> FLAT hasta proxima señal.

Retorna el backtest con columna `_pos_atr` (requiere re-backtest para equity final).
"""
from __future__ import annotations
import polars as pl


def apply_atr_stop_to_backtest(
    bt: pl.DataFrame, atr_col: str = "_atr", atr_k: float = 2.0
) -> pl.DataFrame:
    from src.strategies.e2a_composite import atr as atr_expr

    if atr_col not in bt.columns:
        bt = bt.with_columns(
            atr_expr(pl.col("high"), pl.col("low"), pl.col("close"), 14).alias("_atr")
        )
    bt = bt.with_columns(
        [
            pl.when((pl.col("position").shift(1) == 0) & (pl.col("position") == 1))
            .then(pl.col("close"))
            .otherwise(None)
            .alias("_entry_price"),
            pl.when((pl.col("position").shift(1) == 0) & (pl.col("position") == 1))
            .then(pl.col(atr_col))
            .otherwise(None)
            .alias("_entry_atr"),
        ]
    )
    bt = bt.with_columns(
        [
            pl.col("_entry_price").forward_fill().alias("_entry_price"),
            pl.col("_entry_atr").forward_fill().alias("_entry_atr"),
        ]
    )
    bt = bt.with_columns([(pl.col("_entry_price") - atr_k * pl.col("_entry_atr")).alias("_stop_price")])
    bt = bt.with_columns(
        [
            pl.when((pl.col("position") == 1) & (pl.col("close") < pl.col("_stop_price")))
            .then(0)
            .otherwise(pl.col("position"))
            .alias("_pos_atr")
        ]
    )
    return bt
