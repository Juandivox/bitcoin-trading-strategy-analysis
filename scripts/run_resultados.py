"""
scripts/run_resultados.py

Generador CANONICO de resultados (v3 normalizada).

Universo: 9 estrategias (Buy & Hold, 5 indicadores, E2-A A1, E2-A A2, E2-C).
Protocolo de seleccion: TPE con mediana de Sharpe OOS (folds 2021-2024),
rf=4% y warmup global. Los parametros viven en configs/strategies.yaml
(bloque `v3_selection`) y fueron producidos por scripts/run_tpe_v3.py.

Que hace:
1. Carga configs y valida el guardrail de temporalidad.
2. Corre los backtests sobre la serie canonica 4H.
3. Calcula TODAS las metricas con src/backtesting/metrics.py.
4. Genera tablas, 5 figuras, sensibilidad de rf y manifiesto.

Salidas: docs/tesis_resultados_v3/{tablas,figs}/ + RESUMEN.md + manifest.json

Uso:
    python scripts/run_resultados.py
    python scripts/run_resultados.py --rf 0.038
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Permite `python scripts/run_resultados.py` desde la raiz sin PYTHONPATH.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import yaml

from src.backtesting.engine import backtest
from src.backtesting.metrics import (
    TIMEFRAME_PERIODS,
    periods_per_year,
    sharpe,
    summarize,
    timeframe_from_periods,
)
from src.strategies.buy_and_hold import signal_buy_and_hold
from src.strategies.e2a_composite import E2A_A1, signal_e2a_long
from src.strategies.e2c_winners import signal_e2c_long
from src.strategies.individuals import (
    signal_cci_long,
    signal_ma_long,
    signal_macd_long,
    signal_rsi_long,
)

OUTDIR = ROOT / "docs" / "tesis_resultados_v3"
FIGS = OUTDIR / "figs"
TABS = OUTDIR / "tablas"
UTC = timezone.utc

ALL = ["BH", "RSI", "MACD", "SMA", "EMA", "CCI", "E2A_A1", "E2A_A2", "E2C"]
MAIN = ["BH", "SMA", "MACD", "E2A_A2", "E2C"]
COLORS = {
    "BH": "black", "SMA": "#2ca02c", "MACD": "#ff7f0e",
    "E2A_A2": "#8c564b", "E2C": "#17becf", "RSI": "#1f77b4",
    "EMA": "#9467bd", "CCI": "#d62728", "E2A_A1": "#e377c2",
}
RF_GRID = (0.0, 0.038, 0.04, 0.05)


def load_config() -> tuple[dict, dict]:
    with open(ROOT / "configs" / "strategies.yaml", encoding="utf-8") as f:
        strategies = yaml.safe_load(f)
    with open(ROOT / "configs" / "data.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return strategies, data


def validate_timeframe(df: pl.DataFrame, configured: str) -> int:
    """Guardrail: el P deducido de los datos debe coincidir con el config."""
    detected = periods_per_year(df["timestamp"])
    expected = TIMEFRAME_PERIODS.get(configured)
    if expected is None:
        raise SystemExit(f"[GUARDRAIL] timeframe desconocido en config: {configured!r}")
    if detected != expected:
        raise SystemExit(
            f"[GUARDRAIL] temporalidad inconsistente: config={configured!r} "
            f"(P={expected}) pero los datos tienen P={detected} "
            f"({timeframe_from_periods(detected)}). Abortando para no mezclar escalas."
        )
    return detected


def build_signals(df: pl.DataFrame, params: dict) -> pl.DataFrame:
    df = signal_buy_and_hold(df).rename({"signal_bh": "sig_BH"})

    df = signal_rsi_long(df, **params["rsi"]).rename({"signal_rsi": "sig_RSI"})
    df = signal_macd_long(df, **params["macd"]).rename({"signal_macd": "sig_MACD"})
    df = signal_ma_long(df, kind="sma", **params["sma"]).rename({"signal_sma": "sig_SMA"})
    df = signal_ma_long(df, kind="ema", **params["ema"]).rename({"signal_ema": "sig_EMA"})
    df = signal_cci_long(df, **params["cci"]).rename({"signal_cci": "sig_CCI"})

    df = signal_e2a_long(df, **E2A_A1).rename({"signal_e2a": "sig_E2A_A1"})
    df = signal_e2a_long(df, **params["e2a"]).rename({"signal_e2a": "sig_E2A_A2"})
    df = signal_e2c_long(df).rename({"signal_e2c": "sig_E2C"})
    return df


def _as_datetime(value) -> datetime:
    """Normaliza datetime de Polars/Python a datetime tz-aware UTC."""
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value


def build_periods(df: pl.DataFrame) -> dict[str, tuple[datetime, datetime]]:
    n = len(df)
    cut_idx = int(n * 0.70)
    cut_ts = _as_datetime(df.sort("timestamp")["timestamp"][cut_idx])
    dmin = _as_datetime(df["timestamp"].min())
    dmax = _as_datetime(df["timestamp"].max())
    end = dmax + timedelta(seconds=1)
    return {
        "FULL": (dmin, end),
        "C16": (dmin, datetime(2020, 5, 11, tzinfo=UTC)),
        "C20": (datetime(2020, 5, 11, tzinfo=UTC), datetime(2024, 4, 20, tzinfo=UTC)),
        "C24": (datetime(2024, 4, 20, tzinfo=UTC), end),
        "IS70": (dmin, cut_ts),
        "OOS30": (cut_ts, end),
    }


def round_table(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns(
        pl.col("years").round(2),
        pl.col("exposure").round(4),
        pl.col("final_equity").round(2),
        pl.col("total_return_%").round(2),
        pl.col("CAGR_%").round(2),
        pl.col("sharpe").round(3),
        pl.col("maxDD_%").round(2),
        pl.col("calmar").round(3),
        pl.col("win_rate_%").round(2),
        pl.col("profit_factor").round(3),
        pl.col("avg_trade_%").round(3),
        pl.col("avg_holding_bars").round(1),
        pl.col("turnover").round(1),
        pl.col("rf_annual").round(4),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera resultados canonicos v3 (4H, rf=4%).")
    parser.add_argument("--rf", type=float, default=None, help="Sobrescribe risk_free_annual del config.")
    args = parser.parse_args()

    strategies_cfg, data_cfg = load_config()
    bt_cfg = strategies_cfg["backtest"]
    timeframe = str(bt_cfg["timeframe"])
    analytics_tf = str(data_cfg.get("analytics", {}).get("timeframe", timeframe))
    if analytics_tf != timeframe:
        raise SystemExit(
            f"[GUARDRAIL] configs/data.yaml analytics.timeframe={analytics_tf!r} "
            f"no coincide con backtest.timeframe={timeframe!r}."
        )

    rf_annual = float(args.rf if args.rf is not None else bt_cfg["risk_free_annual"])
    v3 = strategies_cfg["v3_selection"]
    params = v3["params"]

    fee_bps = float(bt_cfg["fees"]["taker"]) * 10_000.0
    slippage_bps = float(bt_cfg["slippage"]["bps"])
    lag = int(bt_cfg["execution"]["lag"])
    initial_capital = float(bt_cfg["initial_capital"])

    data_path = ROOT / data_cfg["paths"]["analytics_4h"]
    if not data_path.exists():
        raise SystemExit(f"[ERROR] No existe {data_path}. Corre primero el resampleo 1m->4h.")

    FIGS.mkdir(parents=True, exist_ok=True)
    TABS.mkdir(parents=True, exist_ok=True)

    df = pl.read_parquet(data_path).sort("timestamp")
    p_detected = validate_timeframe(df, timeframe)
    print(f"[v3] {data_path.name}: {len(df):,} velas | P={p_detected} "
          f"({timeframe_from_periods(p_detected)}) | rf={rf_annual:.2%} | "
          f"fees={fee_bps:.0f}bps + slip={slippage_bps:.0f}bps | lag={lag}")

    df = build_signals(df, params)
    periods = build_periods(df)

    bts: dict[str, dict[str, pl.DataFrame]] = {}
    for pname, (d0, d1) in periods.items():
        sub = df.filter((pl.col("timestamp") >= d0) & (pl.col("timestamp") < d1)).sort("timestamp")
        bts[pname] = {}
        for s in ALL:
            bts[pname][s] = backtest(
                sub.select(["timestamp", "open", "high", "low", "close", f"sig_{s}"]),
                signal_col=f"sig_{s}",
                initial_capital=initial_capital,
                fee_bps=fee_bps,
                slippage_bps=slippage_bps,
                lag=lag,
                allow_short=False,
            )

    rows = []
    for pname, (d0, d1) in periods.items():
        sub0 = df.filter((pl.col("timestamp") >= d0) & (pl.col("timestamp") < d1))
        ventana = f"{sub0['timestamp'].min()} -> {sub0['timestamp'].max()}" if len(sub0) else f"{d0} -> {d1}"
        for s in ALL:
            m = summarize(bts[pname][s], rf_annual=rf_annual)
            m["periodo"] = pname
            m["ventana"] = ventana
            m["estrategia"] = s
            rows.append(m)

    full = round_table(pl.DataFrame(rows))
    full.write_csv(TABS / "metricas_por_periodo.csv")
    for pname in periods:
        full.filter(pl.col("periodo") == pname).write_csv(TABS / f"metricas_{pname}.csv")
    with open(TABS / "metricas_por_periodo.txt", "w", encoding="utf-8") as f:
        f.write(full.sort(["periodo", "sharpe"], descending=[False, True]).to_pandas().to_string())
    print(full.sort(["periodo", "sharpe"], descending=[False, True]).to_pandas().to_string())

    # Sensibilidad de rf sobre los mismos retornos.
    sens_rows = []
    for pname in periods:
        for s in ALL:
            bt = bts[pname][s]
            for rf in RF_GRID:
                sens_rows.append({
                    "periodo": pname,
                    "estrategia": s,
                    "rf_annual": rf,
                    "sharpe": round(sharpe(bt["strategy_ret"], rf_annual=rf,
                                           timestamps=bt["timestamp"]), 3),
                })
    pl.DataFrame(sens_rows).write_csv(TABS / "sensibilidad_rf.csv")

    # --- Figuras (5) ---
    fig, ax = plt.subplots(figsize=(12, 5))
    for s in MAIN:
        serie = bts["FULL"][s].sort("timestamp")
        ax.plot(serie["timestamp"].to_list(), serie["equity"].to_list(),
                lw=1.2, color=COLORS[s], label=s)
    ax.set_yscale("log")
    ax.set_title(f"Equity FULL 2017-08-17 -> 2026-09-01 (4H, rf={rf_annual:.1%}, "
                 f"costos {fee_bps + slippage_bps:.0f}bps)")
    ax.set_ylabel("Equity (USDT, capital inicial 10k, log)")
    ax.legend(ncol=5, fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGS / "v3_fig01_equity_full.png", dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), sharey=True)
    for ax, pname in zip(axes, ["C16", "C20", "C24"]):
        for s in MAIN:
            serie = bts[pname][s].sort("timestamp")
            ax.plot(serie["timestamp"].to_list(), serie["equity"].to_list(),
                    lw=1.1, color=COLORS[s], label=s)
        ax.set_yscale("log")
        ax.set_title(f"{pname}: {periods[pname][0].date()} -> {periods[pname][1].date()}")
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("Equity (log)")
    axes[-1].legend(fontsize=7, ncol=2)
    fig.suptitle(f"Equity por temporada de halving (4H, rf={rf_annual:.1%})")
    fig.tight_layout()
    fig.savefig(FIGS / "v3_fig02_equity_temporadas.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 4.5))
    for s in MAIN:
        serie = bts["FULL"][s].sort("timestamp")
        eq = serie["equity"].to_numpy()
        peak = np.maximum.accumulate(eq)
        dd = (eq - peak) / peak * 100.0
        ax.plot(serie["timestamp"].to_list(), dd, lw=1.0, color=COLORS[s],
                label=f"{s} ({dd.min():.1f}%)")
    ax.set_title("Drawdown FULL (4H)")
    ax.set_ylabel("Drawdown %")
    ax.legend(fontsize=8, ncol=5)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGS / "v3_fig03_drawdown_full.png", dpi=150)
    plt.close(fig)

    piv = full.pivot(index="estrategia", on="periodo", values="sharpe")
    pers = ["C16", "C20", "C24", "FULL"]
    x = np.arange(len(MAIN))
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for i, pname in enumerate(pers):
        vals = []
        for s in MAIN:
            v = piv.filter(pl.col("estrategia") == s)[pname].to_list()[0]
            vals.append(0.0 if v is None else float(v))
        ax.bar(x + (i - 1.5) * 0.2, vals, width=0.2, label=pname)
    ax.set_xticks(x)
    ax.set_xticklabels(MAIN, fontsize=9)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title(f"Sharpe por temporada (4H, rf={rf_annual:.1%})")
    ax.legend(fontsize=8, ncol=4)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGS / "v3_fig04_barras_sharpe.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4.5))
    sens = pl.DataFrame(sens_rows).filter(pl.col("periodo") == "FULL")
    for s in MAIN:
        sub = sens.filter(pl.col("estrategia") == s).sort("rf_annual")
        ax.plot([r * 100 for r in sub["rf_annual"].to_list()],
                sub["sharpe"].to_list(), marker="o", lw=1.4, color=COLORS[s], label=s)
    ax.set_xlabel("Tasa libre de riesgo anual (%)")
    ax.set_ylabel("Sharpe FULL")
    ax.set_title("Sensibilidad del Sharpe a la tasa libre de riesgo (FULL, 4H)")
    ax.legend(fontsize=8, ncol=5)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGS / "v3_fig05_sensibilidad_rf.png", dpi=150)
    plt.close(fig)

    # --- Manifiesto ---
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
        dirty = bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True
        ).strip())
    except Exception:
        commit = "unknown"
        dirty = None

    cfg_bytes = (ROOT / "configs" / "strategies.yaml").read_bytes()
    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "git_commit": commit,
        "git_dirty": dirty,
        "config_sha256": hashlib.sha256(cfg_bytes).hexdigest()[:16],
        "timeframe": timeframe,
        "periods_per_year": p_detected,
        "rf_annual": rf_annual,
        "fee_bps": fee_bps,
        "slippage_bps": slippage_bps,
        "lag": lag,
        "initial_capital": initial_capital,
        "dataset": str(data_path.relative_to(ROOT)),
        "n_bars": len(df),
        "fecha_inicio": str(df["timestamp"].min()),
        "fecha_fin": str(df["timestamp"].max()),
        "universo": ALL,
        "selection_protocol": v3["protocol"],
        "selected_params": params,
    }
    (OUTDIR / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- Resumen ---
    lines = [
        "# Resultados v3 (4H, rf=4%, universo normalizado)",
        "",
        f"- Dataset: `{manifest['dataset']}` — {len(df):,} velas, {manifest['fecha_inicio']} -> {manifest['fecha_fin']}",
        f"- Timeframe: **{timeframe}** (P = {p_detected:,} velas/anio)",
        f"- Tasa libre de riesgo: **{rf_annual:.2%} anual** ({rf_annual / p_detected:.6f} por vela)",
        f"- Costos: {fee_bps:.0f} bps fee + {slippage_bps:.0f} bps slippage | lag = {lag}",
        f"- Commit: `{commit}`{' (arbol de trabajo sucio)' if dirty else ''} | config hash: `{manifest['config_sha256']}`",
        f"- Universo: {', '.join(ALL)}",
        f"- Seleccion: {v3['protocol']}",
        "",
        "## Sharpe por temporada",
        "",
        "| Estrategia | C16 | C20 | C24 | FULL |",
        "|---|---:|---:|---:|---:|",
    ]
    for s in ALL:
        vals = []
        for pname in ["C16", "C20", "C24", "FULL"]:
            v = piv.filter(pl.col("estrategia") == s)[pname].to_list()[0]
            vals.append("—" if v is None else f"{float(v):.3f}")
        lines.append(f"| {s} | " + " | ".join(vals) + " |")

    lines += [
        "",
        "## Operaciones (FULL)",
        "",
        "| Estrategia | Trades | Win rate | Profit factor | Retorno medio | Duracion media (velas) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for s in ALL:
        row = full.filter((pl.col("periodo") == "FULL") & (pl.col("estrategia") == s)).row(0, named=True)
        pf = row["profit_factor"]
        pf_txt = "—" if pf is None else f"{pf:.2f}"
        lines.append(
            f"| {s} | {row['trades']} | {row['win_rate_%']:.2f}% | {pf_txt} | "
            f"{row['avg_trade_%']:.2f}% | {row['avg_holding_bars']:.1f} |"
        )

    lines += [
        "",
        "> Nota: `profit_factor` se calcula POR OPERACION.",
        "",
        "## Archivos",
        "",
        "- `tablas/metricas_por_periodo.csv` — 9 estrategias x 6 periodos",
        "- `tablas/sensibilidad_rf.csv` — Sharpe para rf = 0%, 3,8%, 4% y 5%",
        "- `figs/v3_fig01..05` — equity FULL, temporadas, drawdown, barras y sensibilidad",
        "- `manifest.json` — commit, hash de config, rf, timeframe, universo y protocolo",
        "- `tablas/tpe_v3.json` — re-seleccion TPE (anexo metodologico)",
        "- `tablas/pso_v3.json` — PSO con rf=4% (anexo, contraejemplo de sobreajuste)",
    ]
    (OUTDIR / "RESUMEN.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\n[OK v3] {OUTDIR}")


if __name__ == "__main__":
    main()
