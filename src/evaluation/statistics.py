"""
src/evaluation/statistics.py

Estadisticas para comparar estrategias y test de robustez.
"""
from __future__ import annotations
import numpy as np
import polars as pl
from src.backtesting.metrics import summarize

def compare_strategies(backtests: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """backtests = {"trend": df_bt, "mr": df_bt, "ml": df_bt}"""
    rows = []
    for name, df in backtests.items():
        s = summarize(df)
        s["strategy"] = name
        rows.append(s)
    df = pl.DataFrame(rows)
    # ordenar por sharpe desc
    return df.sort("sharpe", descending=True)

def walk_forward_summary(fold_results: list[dict]) -> pl.DataFrame:
    """Agrega metricas por fold."""
    return pl.DataFrame(fold_results)
