"""
tests/test_metrics.py

Fija la convencion canonica de metricas (docs/03_backtesting_y_validacion.md):
Sharpe con tasa libre de riesgo, P deducido de los timestamps y metricas
por operacion. Si algo de esto se rompe, estos tests fallan.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import polars as pl
import pytest

from src.backtesting.engine import backtest
from src.backtesting import metrics_legacy
from src.backtesting.metrics import (
    cagr,
    max_drawdown,
    periods_per_year,
    sharpe,
    summarize,
    timeframe_from_periods,
    trade_stats,
)

UTC = timezone.utc


def _timestamps(n: int, step_hours: float = 4.0, start: datetime | None = None) -> pl.Series:
    start = start or datetime(2020, 1, 1, tzinfo=UTC)
    return pl.Series([start + timedelta(hours=step_hours * i) for i in range(n)])


# --------------------------------------------------------------------------- #
# P automatico desde timestamps
# --------------------------------------------------------------------------- #
def test_periods_per_year_4h():
    assert periods_per_year(_timestamps(100, 4.0)) == 2190


def test_periods_per_year_1m():
    assert periods_per_year(_timestamps(100, 1.0 / 60.0)) == 525_600


def test_periods_per_year_1d():
    assert periods_per_year(_timestamps(100, 24.0)) == 365


def test_periods_per_year_robusto_a_huecos():
    """Un hueco no debe cambiar la temporalidad detectada (se usa la mediana)."""
    ts = [datetime(2020, 1, 1, tzinfo=UTC) + timedelta(hours=4 * i) for i in range(10)]
    ts.insert(5, ts[4] + timedelta(hours=8))  # hueco de 8h
    assert periods_per_year(pl.Series(ts)) == 2190


def test_periods_per_year_falla_con_serie_corta():
    with pytest.raises(ValueError):
        periods_per_year(pl.Series([datetime(2020, 1, 1, tzinfo=UTC)]))


def test_timeframe_from_periods():
    assert timeframe_from_periods(2190) == "4h"
    assert timeframe_from_periods(525_600) == "1m"
    assert timeframe_from_periods(365) == "1d"
    assert timeframe_from_periods(123) == "custom(123)"


# --------------------------------------------------------------------------- #
# Sharpe
# --------------------------------------------------------------------------- #
def test_sharpe_formula_exacta():
    r = np.array([0.01, -0.005, 0.02, -0.01, 0.0, 0.004])
    rf, p = 0.04, 2190
    expected = float(np.mean(r - rf / p) / np.std(r - rf / p, ddof=1) * np.sqrt(p))
    assert sharpe(r, rf_annual=rf, periods_per_year=p) == pytest.approx(expected, rel=1e-12)


def test_sharpe_rf_cero_reproduce_formula_legacy():
    r = np.array([0.01, -0.005, 0.02, -0.01, 0.0, 0.004])
    legacy = float(np.mean(r) / np.std(r, ddof=1) * np.sqrt(2190))
    assert sharpe(r, rf_annual=0.0, periods_per_year=2190) == pytest.approx(legacy, rel=1e-12)


def test_sharpe_exige_rf_explicito():
    with pytest.raises(ValueError, match="rf_annual"):
        sharpe([0.01, -0.02], periods_per_year=2190)


def test_sharpe_exige_temporalidad():
    with pytest.raises(ValueError, match="timestamps"):
        sharpe([0.01, -0.02], rf_annual=0.04)


def test_sharpe_mas_rf_baja_el_valor():
    r = np.array([0.01, -0.005, 0.02, -0.01, 0.0, 0.004])
    s0 = sharpe(r, rf_annual=0.0, periods_per_year=2190)
    s4 = sharpe(r, rf_annual=0.04, periods_per_year=2190)
    assert s4 < s0


def test_sharpe_serie_constante_es_cero():
    assert sharpe([0.01] * 10, rf_annual=0.04, periods_per_year=2190) == 0.0


# --------------------------------------------------------------------------- #
# CAGR / drawdown
# --------------------------------------------------------------------------- #
def test_cagr_un_anio_duplica():
    eq = np.linspace(100.0, 200.0, 2190)
    assert cagr(eq, periods_per_year=2190) == pytest.approx(1.0, rel=1e-9)


def test_max_drawdown_conocido():
    mdd, dur = max_drawdown(np.array([100.0, 120.0, 90.0, 110.0]))
    assert mdd == pytest.approx(-0.25)
    assert dur == 1


# --------------------------------------------------------------------------- #
# Metricas por operacion
# --------------------------------------------------------------------------- #
def test_trade_stats_dos_operaciones():
    pos = np.array([0, 1, 1, 0, 1, 0])
    ret = np.array([0.0, 0.01, 0.02, 0.01, -0.01, 0.0])

    st = trade_stats(pos, ret)
    assert st["n_trades"] == 2
    assert st["win_rate"] == pytest.approx(0.5)
    assert st["avg_holding_bars"] == pytest.approx(1.5)
    assert st["avg_trade"] == pytest.approx(
        ((1.01 * 1.02 * 1.01 - 1) + (0.99 - 1)) / 2
    )


def test_profit_factor_sin_perdidas_es_none():
    st = trade_stats(np.array([0, 1, 0]), np.array([0.0, 0.05, 0.0]))
    assert st["n_trades"] == 1
    assert st["profit_factor"] is None


def test_sin_operaciones():
    st = trade_stats(np.zeros(10), np.zeros(10))
    assert st["n_trades"] == 0
    assert st["win_rate"] == 0.0
    assert st["profit_factor"] == 0.0


# --------------------------------------------------------------------------- #
# summarize: contrato de la tabla de la tesis
# --------------------------------------------------------------------------- #
def _synthetic_backtest() -> pl.DataFrame:
    n = 300
    ts = _timestamps(n, 4.0)
    close = 100.0 * np.cumprod(1.0 + np.sin(np.arange(n) / 8.0) * 0.01)
    signal = ((np.arange(n) // 10) % 2).astype(np.int8)  # alterna 10 velas dentro/fuera
    df = pl.DataFrame({
        "timestamp": ts,
        "open": close,
        "high": close * 1.001,
        "low": close * 0.999,
        "close": close,
        "signal": signal,
    })
    return backtest(df, signal_col="signal", fee_bps=10.0, slippage_bps=5.0, lag=1)


def test_summarize_contrato():
    bt = _synthetic_backtest()
    m = summarize(bt, rf_annual=0.04)

    for key in (
        "n_bars", "years", "trades", "exposure", "final_equity", "total_return_%",
        "CAGR_%", "sharpe", "maxDD_%", "maxDD_bars", "calmar", "win_rate_%",
        "profit_factor", "avg_trade_%", "avg_holding_bars", "turnover",
        "periods_per_year", "rf_annual",
    ):
        assert key in m, f"falta {key}"

    assert "sortino" not in m
    assert m["periods_per_year"] == 2190
    assert m["rf_annual"] == pytest.approx(0.04)


def test_summarize_exige_rf():
    with pytest.raises(ValueError, match="rf_annual"):
        summarize(_synthetic_backtest())


def test_summarize_usa_timestamps_para_p():
    bt = _synthetic_backtest()
    m = summarize(bt, rf_annual=0.0)
    assert m["periods_per_year"] == 2190
    assert m["years"] == pytest.approx(bt.height / 2190)


def test_legacy_sharpe_posicional_equivale_a_rf0():
    r = np.array([0.01, -0.005, 0.02, -0.01, 0.0, 0.004])
    assert metrics_legacy.sharpe(r, 2190) == pytest.approx(
        sharpe(r, 2190, rf_annual=0.0), rel=1e-12
    )


def test_legacy_summarize_usa_rf0():
    m = metrics_legacy.summarize(_synthetic_backtest())
    assert m["rf_annual"] == 0.0
    assert m["periods_per_year"] == 2190


def test_sharpe_posicional_sin_rf_da_error_claro():
    with pytest.raises(ValueError, match="rf_annual"):
        sharpe([0.01, -0.02], 2190)


def test_summarize_alinea_pos_y_returns():
    """La primera vela nula de strategy_ret no debe desfasar position."""
    bt = _synthetic_backtest()
    m = summarize(bt, rf_annual=0.0)

    core = bt.select(["strategy_ret", "position"]).drop_nulls(["strategy_ret"])
    st = trade_stats(core["position"], core["strategy_ret"])

    assert m["trades"] == st["n_trades"]
    assert m["win_rate_%"] == pytest.approx(st["win_rate"] * 100.0)
    assert m["avg_trade_%"] == pytest.approx(st["avg_trade"] * 100.0)
