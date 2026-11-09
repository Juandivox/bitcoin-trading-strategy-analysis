"""
src/backtesting/metrics_legacy.py

API historica (rf=0) para los notebooks 04/05/06.

NO usar en codigo nuevo. Existe solo para que los notebooks archivados sigan
siendo reproducibles: el rf=0 esta declarado aqui, en un unico sitio, y no se
propaga a la API canonica de ``src/backtesting/metrics.py``.

La salida oficial del proyecto es ``scripts/run_resultados.py`` (v3, rf=4%).
"""
from __future__ import annotations

from src.backtesting.metrics import calmar as _calmar
from src.backtesting.metrics import cagr as _cagr
from src.backtesting.metrics import max_drawdown, profit_factor, trade_stats, win_rate
from src.backtesting.metrics import sharpe as _sharpe
from src.backtesting.metrics import summarize as _summarize

__all__ = [
    "sharpe", "cagr", "calmar", "max_drawdown", "win_rate",
    "profit_factor", "trade_stats", "summarize",
]


def sharpe(returns, periods_per_year=None, rf_annual=0.0, timestamps=None) -> float:
    """Sharpe con rf=0 explicito (convencion historica de los notebooks)."""
    return _sharpe(
        returns,
        rf_annual=rf_annual,
        timestamps=timestamps,
        periods_per_year=periods_per_year,
    )


def cagr(equity, periods_per_year=None, timestamps=None) -> float:
    return _cagr(equity, timestamps=timestamps, periods_per_year=periods_per_year)


def calmar(equity, periods_per_year=None, timestamps=None) -> float:
    return _calmar(equity, timestamps=timestamps, periods_per_year=periods_per_year)


def summarize(bt_df, **kwargs) -> dict:
    kwargs.setdefault("rf_annual", 0.0)
    return _summarize(bt_df, **kwargs)
