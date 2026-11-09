"""
src/evaluation/statistics.py

Estadisticas para comparar estrategias y test de robustez.
"""
from __future__ import annotations

import polars as pl

from src.backtesting.metrics import summarize


def compare_strategies(
    backtests: dict[str, pl.DataFrame],
    *,
    rf_annual: float | None = None,
    periods_per_year: int | None = None,
) -> pl.DataFrame:
    """Compara backtests con la convencion canonica de metricas.

    ``rf_annual`` es obligatorio (ej. 0.04); no se asume rf=0.
    """
    rows = []
    for name, df in backtests.items():
        s = summarize(df, rf_annual=rf_annual, periods_per_year=periods_per_year)
        s["strategy"] = name
        rows.append(s)
    df = pl.DataFrame(rows)
    return df.sort("sharpe", descending=True)


def walk_forward_summary(fold_results: list[dict]) -> pl.DataFrame:
    """Agrega metricas por fold."""
    return pl.DataFrame(fold_results)
