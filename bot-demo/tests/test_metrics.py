"""Métricas honestas: lo no calculable se declara con motivo."""
from __future__ import annotations

import math
from decimal import Decimal

import pytest

from app.accounting.metrics import compute_metrics, daily_returns

DAY = 86_400_000
T0 = 1_700_000_000_000


def snaps(values: list[float], step_days: int = 1) -> list[dict]:
    return [{"ts_ms": T0 + i * step_days * DAY, "equity": v} for i, v in enumerate(values)]


def test_drawdown_positive_magnitude():
    metrics = compute_metrics(snaps([100, 80, 90, 110]), [], Decimal("100"))
    assert metrics["max_drawdown"] == pytest.approx(0.20)
    assert metrics["max_drawdown_signed"] == pytest.approx(-0.20)


def test_coverage_and_short_sample():
    days = list(range(26)) + [29]
    values = [10000.0 + i for i in range(27)]
    samples = [{"ts_ms": T0 + d * DAY, "equity": v} for d, v in zip(days, values)]
    metrics = compute_metrics(samples, [], Decimal("10000"))
    assert metrics["cobertura"] == pytest.approx(27 / 30)
    assert metrics["muestra_corta"] is True


def test_no_closed_trades_reports_reasons():
    metrics = compute_metrics(snaps([10000, 10100, 10200]), [], Decimal("10000"))
    assert metrics["win_rate"] is None
    assert metrics["expectativa"] is None
    assert metrics["profit_factor"] is None
    assert "sin_posiciones_cerradas" in metrics["motivos"]["win_rate"]


def test_no_losses_profit_factor_none():
    trades = [
        {"closed": True, "pnl": "10", "duration_s": 100, "exposure_s": 100},
        {"closed": True, "pnl": "5", "duration_s": 200, "exposure_s": 200},
    ]
    metrics = compute_metrics(snaps([10000, 10050, 10100]), trades, Decimal("10000"))
    assert metrics["win_rate"] == pytest.approx(1.0)
    assert metrics["profit_factor"] is None
    assert "sin_perdidas" in metrics["motivos"]["profit_factor"]


def test_sharpe_matches_hand_calculation():
    rets = [0.1, 0.2]
    values = [100.0]
    for r in rets:
        values.append(values[-1] * (1 + r))
    metrics = compute_metrics(snaps(values), [], Decimal("100"))
    mu = sum(rets) / 2
    sd = math.sqrt(sum((r - mu) ** 2 for r in rets) / 1)
    expected = mu / sd * math.sqrt(365)
    assert metrics["sharpe"] == pytest.approx(expected, rel=1e-12)


def test_cagr_exact_days():
    metrics = compute_metrics(snaps([100.0, 121.0], step_days=730), [], Decimal("100"))
    expected = (121.0 / 100.0) ** (365.0 / 730.0) - 1.0
    assert metrics["cagr"] == pytest.approx(expected, rel=1e-12)


def test_zero_variance_reports_reason():
    metrics = compute_metrics(snaps([100.0, 101.0, 102.01]), [], Decimal("100"))
    assert metrics["sharpe"] is None
    assert "varianza_cero" in metrics["motivos"]["sharpe"]


def test_daily_returns_use_utc_cut():
    # Dos snapshots del mismo día: solo cuenta el último.
    s = [
        {"ts_ms": T0, "equity": 100},
        {"ts_ms": T0 + 3600_000, "equity": 110},
        {"ts_ms": T0 + DAY, "equity": 121},
    ]
    rets = daily_returns(s)
    assert len(rets) == 1
    assert rets[0]["ret"] == pytest.approx(0.10)


def test_closed_trade_metrics_with_losses():
    trades = [
        {"closed": True, "pnl": "10", "duration_s": 100, "exposure_s": 100},
        {"closed": True, "pnl": "-4", "duration_s": 300, "exposure_s": 300},
    ]
    metrics = compute_metrics(snaps([10000, 10010, 10006, 10020]), trades, Decimal("10000"))
    assert metrics["win_rate"] == pytest.approx(0.5)
    assert metrics["profit_factor"] == pytest.approx(2.5)
    assert metrics["expectativa"] == pytest.approx(3.0)
    assert metrics["duracion_media_s"] == pytest.approx(200)
    assert metrics["duracion_mediana_s"] == pytest.approx(200)
