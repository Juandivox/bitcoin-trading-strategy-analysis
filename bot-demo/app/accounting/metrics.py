"""Métricas de la prueba (spec v2.0 §15.3/§15.4). Honestas: lo no calculable se declara."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from decimal import Decimal

DAY_MS = 86_400_000


def _day_key(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def daily_returns(snapshots: list[dict]) -> list[dict]:
    """Rendimientos diarios con cortes UTC coherentes: último snapshot de cada día."""
    by_day: dict[str, dict] = {}
    for snap in sorted(snapshots, key=lambda s: s["ts_ms"]):
        equity = Decimal(str(snap["equity"]))
        if equity <= 0:
            continue
        by_day[_day_key(snap["ts_ms"])] = {"day": _day_key(snap["ts_ms"]), "ts_ms": snap["ts_ms"], "equity": equity}
    ordered = [by_day[k] for k in sorted(by_day)]
    out: list[dict] = []
    for prev, cur in zip(ordered, ordered[1:]):
        ret = float(cur["equity"] / prev["equity"] - 1)
        out.append({"day": cur["day"], "ts_ms": cur["ts_ms"], "equity": cur["equity"], "ret": ret})
    return out


def _max_drawdown(equities: list[float]) -> tuple[float, float]:
    peak = equities[0]
    worst = 0.0
    for value in equities:
        peak = max(peak, value)
        dd = value / peak - 1.0
        worst = min(worst, dd)
    return -worst, worst


def compute_metrics(snapshots: list[dict], trades: list[dict], initial_equity: Decimal) -> dict:
    motivos: dict[str, str] = {}
    out: dict = {"motivos": motivos}

    snaps = sorted(
        [s for s in snapshots if Decimal(str(s["equity"])) > 0],
        key=lambda s: s["ts_ms"],
    )
    if not snaps:
        out.update(
            retorno_total=None, pnl_cerrado=None, pnl_abierto=None, max_drawdown=None,
            win_rate=None, profit_factor=None, expectativa=None, duracion_media_s=None,
            duracion_mediana_s=None, exposicion=None, cobertura=0.0, cagr=None,
            sharpe=None, sortino=None, calmar=None, muestra_corta=True,
        )
        motivos["todas"] = "sin_snapshots_validos"
        return out

    equities = [float(Decimal(str(s["equity"]))) for s in snaps]
    e0, eT = equities[0], equities[-1]
    days = (snaps[-1]["ts_ms"] - snaps[0]["ts_ms"]) / DAY_MS

    out["retorno_total"] = eT / e0 - 1.0 if e0 > 0 else None
    if out["retorno_total"] is None:
        motivos["retorno_total"] = "equity_inicial_no_positiva"

    if days > 0 and e0 > 0 and eT > 0:
        out["cagr"] = (eT / e0) ** (365.0 / days) - 1.0
    else:
        out["cagr"] = None
        motivos["cagr"] = "periodo_no_positivo"

    maxdd, worst_signed = _max_drawdown(equities)
    out["max_drawdown"] = maxdd
    out["max_drawdown_signed"] = worst_signed

    closed = [t for t in trades if t.get("closed") and t.get("pnl") is not None]
    if closed:
        pnls = [Decimal(str(t["pnl"])) for t in closed]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        out["pnl_cerrado"] = float(sum(pnls, Decimal("0")))
        out["win_rate"] = len(wins) / len(closed)
        gross_win = sum(wins, Decimal("0"))
        gross_loss = abs(sum(losses, Decimal("0")))
        if gross_loss > 0:
            out["profit_factor"] = float(gross_win / gross_loss)
        else:
            out["profit_factor"] = None
            motivos["profit_factor"] = "sin_perdidas_denominador_cero"
        out["expectativa"] = float(sum(pnls, Decimal("0")) / len(closed))
        durations = sorted(
            (t["duration_s"] for t in closed if t.get("duration_s") is not None)
        )
        if durations:
            out["duracion_media_s"] = sum(durations) / len(durations)
            mid = len(durations) // 2
            out["duracion_mediana_s"] = (
                durations[mid] if len(durations) % 2 else (durations[mid - 1] + durations[mid]) / 2
            )
        else:
            out["duracion_media_s"] = None
            out["duracion_mediana_s"] = None
            motivos["duracion"] = "sin_duraciones_registradas"
    else:
        out["pnl_cerrado"] = 0.0 if trades else None
        out["win_rate"] = None
        out["profit_factor"] = None
        out["expectativa"] = None
        out["duracion_media_s"] = None
        out["duracion_mediana_s"] = None
        motivos["win_rate"] = "no_calculable: sin_posiciones_cerradas"
        motivos["expectativa"] = "no_calculable: sin_posiciones_cerradas"
        motivos["profit_factor"] = "no_calculable: sin_posiciones_cerradas"

    open_trades = [t for t in trades if not t.get("closed")]
    out["pnl_abierto"] = float(sum(Decimal(str(t.get("pnl", 0))) for t in open_trades))

    total_expected = max(1, int(days) + 1)
    out["cobertura"] = len(snaps) / total_expected
    out["exposicion"] = (
        sum(float(t.get("exposure_s", 0)) for t in trades) / (days * 86400)
        if days > 0 and trades
        else None
    )

    rets = [r["ret"] for r in daily_returns(snaps)]
    out["muestra_corta"] = len(rets) < 30
    if len(rets) >= 2:
        mu = sum(rets) / len(rets)
        var = sum((r - mu) ** 2 for r in rets) / (len(rets) - 1)
        sd = math.sqrt(var)
        if sd > 0:
            out["sharpe"] = mu / sd * math.sqrt(365)
        else:
            out["sharpe"] = None
            motivos["sharpe"] = "varianza_cero"
        downside = [min(r, 0.0) ** 2 for r in rets]
        dd_dev = math.sqrt(sum(downside) / len(downside))
        if dd_dev > 0:
            out["sortino"] = mu / dd_dev * math.sqrt(365)
        else:
            out["sortino"] = None
            motivos["sortino"] = "sin_desviacion_negativa"
    else:
        out["sharpe"] = None
        out["sortino"] = None
        motivos["sharpe"] = "menos_de_dos_retornos_diarios"
        motivos["sortino"] = "menos_de_dos_retornos_diarios"

    if out.get("cagr") is not None and maxdd > 0:
        out["calmar"] = out["cagr"] / maxdd
    else:
        out["calmar"] = None
        motivos["calmar"] = "cagr_o_drawdown_no_calculables"

    return out
