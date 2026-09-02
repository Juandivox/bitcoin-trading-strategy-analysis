"""
src/backtesting/metrics.py

Metricas de performance: Sharpe, Sortino, Calmar, drawdown, win rate, profit factor, etc.
"""
from __future__ import annotations
import numpy as np
import polars as pl

TRADING_PERIODS_PER_YEAR_1M = 525_600  # 365*24*60 (crypto 24/7)

def sharpe(returns: np.ndarray, periods_per_year: int = TRADING_PERIODS_PER_YEAR_1M, risk_free: float = 0.0) -> float:
    excess = returns - risk_free / periods_per_year
    std = np.std(excess, ddof=1)
    if std == 0 or np.isnan(std):
        return 0.0
    return float(np.mean(excess) / std * np.sqrt(periods_per_year))

def sortino(returns: np.ndarray, periods_per_year: int = TRADING_PERIODS_PER_YEAR_1M, risk_free: float = 0.0) -> float:
    excess = returns - risk_free / periods_per_year
    downside = excess[excess < 0]
    if len(downside) == 0:
        return float("inf") if np.mean(excess) > 0 else 0.0
    std_down = np.std(downside, ddof=1)
    if std_down == 0:
        return 0.0
    return float(np.mean(excess) / std_down * np.sqrt(periods_per_year))

def max_drawdown(equity: np.ndarray) -> tuple[float, int]:
    """Retorna (max_dd_pct, duration_bars)."""
    peak = np.maximum.accumulate(equity)
    dd = (equity - peak) / peak
    max_dd = float(np.min(dd))
    # duracion
    # encontrar tramo de max dd
    trough_idx = int(np.argmin(dd))
    # buscar peak previo
    peak_idx = int(np.argmax(equity[:trough_idx+1]))
    duration = trough_idx - peak_idx
    return max_dd, duration

def cagr(equity: np.ndarray, periods_per_year: int = TRADING_PERIODS_PER_YEAR_1M) -> float:
    n = len(equity)
    if n < 2:
        return 0.0
    total_ret = equity[-1] / equity[0] - 1
    years = n / periods_per_year
    if years <= 0:
        return 0.0
    return float((1 + total_ret) ** (1 / years) - 1)

def calmar(equity: np.ndarray, periods_per_year: int = TRADING_PERIODS_PER_YEAR_1M) -> float:
    c = cagr(equity, periods_per_year)
    mdd, _ = max_drawdown(equity)
    if mdd == 0:
        return float("inf") if c > 0 else 0.0
    return float(c / abs(mdd))

def win_rate(returns: np.ndarray) -> float:
    # solo periodos con posicion !=0 idealmente; aqui todos los retornos
    nonzero = returns[returns != 0]
    if len(nonzero) == 0:
        return 0.0
    return float(np.mean(nonzero > 0))

def profit_factor(returns: np.ndarray) -> float:
    gains = returns[returns > 0].sum()
    losses = abs(returns[returns < 0].sum())
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return float(gains / losses)

def summarize(bt_df: pl.DataFrame, ret_col: str = "strategy_ret", equity_col: str = "equity") -> dict:
    rets = bt_df[ret_col].drop_nulls().to_numpy()
    eq = bt_df[equity_col].drop_nulls().to_numpy()
    # turnover y costos si existen
    turnover = float(bt_df["_turnover"].sum()) if "_turnover" in bt_df.columns else 0.0
    fees = float(bt_df["_cost"].sum() * bt_df["equity"].first()) if "_cost" in bt_df.columns else 0.0
    mdd, mdd_dur = max_drawdown(eq)
    return {
        "cagr": cagr(eq),
        "sharpe": sharpe(rets),
        "sortino": sortino(rets),
        "calmar": calmar(eq),
        "max_drawdown": mdd,
        "max_drawdown_duration_bars": mdd_dur,
        "win_rate": win_rate(rets),
        "profit_factor": profit_factor(rets),
        "turnover": turnover,
        "total_return": float(eq[-1]/eq[0]-1) if len(eq)>1 else 0.0,
        "final_equity": float(eq[-1]) if len(eq)>0 else 0.0,
        "n_bars": len(bt_df),
    }
