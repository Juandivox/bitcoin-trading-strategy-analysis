"""
src/backtesting/costs.py

Modelos de costos de transaccion.
"""
from __future__ import annotations
import polars as pl

def apply_costs(
    df: pl.DataFrame,
    turnover_col: str = "_turnover",
    fee_bps: float = 10.0,
    slippage_bps: float = 5.0,
    atr_col: str | None = None,
    atr_multiplier: float = 0.1,
) -> pl.DataFrame:
    """
    Aplica costos. Si atr_col se provee, slippage es dinamico: atr * multiplier / price
    """
    if atr_col and atr_col in df.columns:
        # slippage dinamico proporcional a volatilidad
        df = df.with_columns(
            ((pl.col(atr_col) / pl.col("close") * atr_multiplier * 10_000).clip(lower_bound=1, upper_bound=50)).alias("_dyn_slippage_bps")
        )
        total_bps = fee_bps + pl.col("_dyn_slippage_bps")
        df = df.with_columns((pl.col(turnover_col) * total_bps / 10_000).alias("_cost"))
    else:
        cost_rate = (fee_bps + slippage_bps) / 10_000
        df = df.with_columns((pl.col(turnover_col) * cost_rate).alias("_cost"))
    return df
