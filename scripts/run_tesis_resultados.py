"""
scripts/run_tesis_resultados.py

Backtests para el capitulo de RESULTADOS del trabajo de grado:
- Independientes: BH (only-buy), BH+TP5, BH+SL5, BH+TP/SL5, RSI, MACD, SMA, EMA, CCI
- Compuestas: E2-A A1 (CCI+SMA+Volumen+ATR paper), E2-A A2 (TPE150), E2-C (SMA+MACD+RSI)
- Periodos por halvings BTC: FULL 2017-2026, C16 (2017->2020-05-10, parcial),
  C20 (2020-05-11->2024-04-19), C24 (2024-04-20->2026-09-01).
- Timeframe 4H (tesis sec. 6.2), costos 10bps fee + 5bps slippage, lag=1, long-only.
- Metricas anualizadas con P=2190 (4H crypto 24/7: 6*365).

Salidas: docs/tesis_resultados/figs/*.png + tablas/*.csv
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import polars as pl
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.processing.resample import resample
from src.backtesting.engine import backtest
from src.backtesting.metrics import summarize
from src.strategies.buy_and_hold import signal_buy_and_hold
from src.strategies.individuals import (
    signal_rsi_long, signal_macd_long, signal_ma_long, signal_cci_long, EXP01_BEST,
)
from src.strategies.e2a_composite import signal_e2a_long, E2A_A1, E2A_A2_BEST
from src.strategies.e2c_winners import signal_e2c_long

ROOT = Path(__file__).resolve().parents[1]
FIGS = ROOT / "docs" / "tesis_resultados" / "figs"
TABS = ROOT / "docs" / "tesis_resultados" / "tablas"
P4H = 2190.0  # periodos 4H por anio
UTC = timezone.utc

PERIODS = {
    "FULL": (datetime(2017, 8, 17, tzinfo=UTC), datetime(2026, 9, 2, tzinfo=UTC)),
    "C16": (datetime(2017, 8, 17, tzinfo=UTC), datetime(2020, 5, 11, tzinfo=UTC)),
    "C20": (datetime(2020, 5, 11, tzinfo=UTC), datetime(2024, 4, 20, tzinfo=UTC)),
    "C24": (datetime(2024, 4, 20, tzinfo=UTC), datetime(2026, 9, 2, tzinfo=UTC)),
}
HALVINGS = {
    "2016-07-09": datetime(2016, 7, 9, tzinfo=UTC),
    "2020-05-11": datetime(2020, 5, 11, tzinfo=UTC),
    "2024-04-20": datetime(2024, 4, 20, tzinfo=UTC),
}

STRAT_LABELS = {
    "BH": "Buy & Hold (only-buy)",
    "BH_TP5": "BH + Take-Profit 5%",
    "BH_SL5": "BH + Stop-Loss 5%",
    "BH_TPSL": "BH + TP 5% / SL 5%",
    "RSI": "RSI",
    "MACD": "MACD",
    "SMA": "SMA (MA)",
    "EMA": "EMA (MA)",
    "CCI": "CCI",
    "E2A_A1": "E2-A paper (CCI+SMA+Vol+ATR)",
    "E2A_A2": "E2-A TPE150 (optimizada)",
    "E2C": "E2-C (SMA+MACD+RSI)",
}
INDEP = ["BH", "BH_TP5", "BH_SL5", "BH_TPSL", "RSI", "MACD", "SMA", "EMA", "CCI"]
COMP = ["BH", "E2A_A1", "E2A_A2", "E2C"]
ALL = INDEP + ["E2A_A1", "E2A_A2", "E2C"]
COLORS = {
    "BH": "black", "BH_TP5": "gray", "BH_SL5": "silver", "BH_TPSL": "dimgray",
    "RSI": "#1f77b4", "MACD": "#ff7f0e", "SMA": "#2ca02c", "EMA": "#9467bd",
    "CCI": "#d62728", "E2A_A1": "#e377c2", "E2A_A2": "#8c564b", "E2C": "#17becf",
}


def load_4h() -> pl.DataFrame:
    cache = ROOT / "data" / "processed" / "btcusdt_4h.parquet"
    if cache.exists():
        df = pl.read_parquet(cache)
        print(f"[4h] cache {cache} filas={len(df):,}")
        return df.sort("timestamp")
    print("[4h] resampleando 1m -> 4h (puede tardar ~1 min)...")
    df1m = pl.read_parquet(
        ROOT / "data" / "processed" / "btcusdt_1m.parquet",
        columns=["timestamp", "open", "high", "low", "close", "volume",
                 "quote_volume", "trade_count", "taker_buy_volume",
                 "taker_buy_quote_volume", "taker_sell_volume", "taker_sell_quote_volume"],
    )
    df = resample(df1m.sort("timestamp"), "4h")
    df.write_parquet(cache, compression="zstd")
    print(f"[4h] OK -> {cache} filas={len(df):,}")
    return df.sort("timestamp")


def apply_tp_sl_to_bh(df: pl.DataFrame, tp: float | None, sl: float | None, out: str) -> pl.DataFrame:
    """BH con TP/SL 5%: entra LONG, sale en TP/SL, re-entra en la siguiente vela."""
    close = df["close"].to_numpy()
    sig = np.ones(len(close), dtype=np.int8)
    if tp is None and sl is None:
        return df.with_columns(pl.Series(out, sig, dtype=pl.Int8))
    entry = close[0]
    holding = True
    for i in range(1, len(close)):
        if not holding:
            sig[i] = 0
            # re-entrada en la vela siguiente al cierre de la operacion
            holding = True
            entry = close[i]
            sig[i] = 1
            continue
        hit_tp = tp is not None and close[i] >= entry * (1 + tp)
        hit_sl = sl is not None and close[i] <= entry * (1 - sl)
        if hit_tp or hit_sl:
            sig[i] = 0
            holding = False
        else:
            sig[i] = 1
            if i == 1 or sig[i - 1] == 0:
                entry = close[i - 1] if sig[i - 1] == 0 else entry
    # ejecuta con lag en el backtester; la senal 0 dura 1 vela (re-entrada)
    return df.with_columns(pl.Series(out, sig, dtype=pl.Int8))


def build_signals(df: pl.DataFrame) -> pl.DataFrame:
    df = signal_buy_and_hold(df)
    df = df.rename({"signal_bh": "sig_BH"})
    df = apply_tp_sl_to_bh(df, 0.05, None, "sig_BH_TP5")
    df = apply_tp_sl_to_bh(df, None, 0.05, "sig_BH_SL5")
    df = apply_tp_sl_to_bh(df, 0.05, 0.05, "sig_BH_TPSL")
    p = EXP01_BEST
    df = signal_rsi_long(df, **{k: v for k, v in p["rsi"].items()}, exit_level=50).rename({"signal_rsi": "sig_RSI"})
    df = signal_macd_long(df, **p["macd"]).rename({"signal_macd": "sig_MACD"})
    df = signal_ma_long(df, fast=p["sma"]["fast"], slow=p["sma"]["slow"], kind="sma").rename({"signal_sma": "sig_SMA"})
    df = signal_ma_long(df, fast=p["ema"]["fast"], slow=p["ema"]["slow"], kind="ema").rename({"signal_ema": "sig_EMA"})
    df = signal_cci_long(df, period=p["cci"]["period"], entry=p["cci"]["entry"], exit_=p["cci"]["exit_"]).rename({"signal_cci": "sig_CCI"})
    df = signal_e2a_long(df, **E2A_A1).rename({"signal_e2a": "sig_E2A_A1"})
    df = signal_e2a_long(df, **E2A_A2_BEST).rename({"signal_e2a": "sig_E2A_A2"})
    df = signal_e2c_long(df).rename({"signal_e2c": "sig_E2C"})
    return df


def summarize_4h(bt: pl.DataFrame) -> dict:
    """Alias historico de la v1: rf=0 explicito para reproducir sus tablas.

    La salida canonica del proyecto es scripts/run_resultados.py (v3, rf=4%).
    """
    return summarize(bt, rf_annual=0.0)


def run_backtests(df: pl.DataFrame) -> dict[str, dict[str, pl.DataFrame]]:
    out: dict[str, dict[str, pl.DataFrame]] = {}
    for pname, (d0, d1) in PERIODS.items():
        sub = df.filter((pl.col("timestamp") >= d0) & (pl.col("timestamp") < d1))
        print(f"[{pname}] velas 4h = {len(sub):,}  ({sub['timestamp'].min()} -> {sub['timestamp'].max()})")
        out[pname] = {}
        for s in ALL:
            bt = backtest(sub.select(["timestamp", "open", "high", "low", "close", f"sig_{s}"]),
                          signal_col=f"sig_{s}", initial_capital=10_000.0,
                          fee_bps=10.0, slippage_bps=5.0, lag=1, allow_short=False)
            out[pname][s] = bt
    return out


def save_tables(bts: dict) -> pl.DataFrame:
    rows = []
    for pname in PERIODS:
        for s in ALL:
            m = summarize_4h(bts[pname][s])
            m["periodo"] = pname
            m["estrategia"] = s
            rows.append(m)
    full = pl.DataFrame(rows)
    full.write_csv(TABS / "metricas_por_periodo.csv")
    for pname in PERIODS:
        full.filter(pl.col("periodo") == pname).write_csv(TABS / f"metricas_{pname}.csv")
    with open(TABS / "metricas_por_periodo.txt", "w", encoding="utf-8") as f:
        f.write(full.sort(["periodo", "sharpe"]).to_pandas().to_string())
    print(full.sort(["periodo", "sharpe"]).to_pandas().to_string())
    return full


# ---------------- Figuras ----------------
def fig_price_halvings(df: pl.DataFrame):
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.plot(df["timestamp"].to_list(), df["close"].to_list(), lw=0.8, color="black")
    ax.set_yscale("log")
    for label, dt in HALVINGS.items():
        if df["timestamp"].min() <= dt <= df["timestamp"].max():
            ax.axvline(dt, color="red", ls="--", lw=1)
            ax.text(dt, df["close"].max(), f" halving {label}", color="red", fontsize=8, va="top")
    ax.set_title("BTC/USDT 4H (log) 2017-2026 con halvings — Binance Spot (sin datos 2012-2017)")
    ax.set_ylabel("Close USDT (log)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGS / "fig01_precio_halvings.png", dpi=150)
    plt.close(fig)


def fig_equity(bts: dict, pname: str, strats: list[str], fname: str, title: str):
    fig, ax = plt.subplots(figsize=(12, 5))
    bt0 = bts[pname][strats[0]]
    ax.plot(bt0["timestamp"].to_list(), bt0["bh_equity"].to_list(), color="black", lw=1.2, alpha=0.5, label="Precio BH ref")
    for s in strats:
        bt = bts[pname][s]
        ax.plot(bt["timestamp"].to_list(), bt["equity"].to_list(), lw=1.1, color=COLORS[s], label=s)
    ax.set_title(title)
    ax.set_ylabel("Equity (USDT, cap. 10k)")
    ax.legend(ncol=3, fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGS / fname, dpi=150)
    plt.close(fig)


def fig_bars(full: pl.DataFrame):
    for metric, fname, title in [
        ("sharpe", "fig06_barras_sharpe.png", "Sharpe (4H, rf=0) por estrategia y ciclo"),
        ("CAGR_%", "fig07_barras_cagr.png", "CAGR % neto por estrategia y ciclo"),
        ("maxDD_%", "fig08_barras_maxdd.png", "Max Drawdown % por estrategia y ciclo"),
    ]:
        piv = full.pivot(index="estrategia", on="periodo", values=metric).sort("estrategia")
        cats = piv["estrategia"].to_list()
        pers = ["C16", "C20", "C24", "FULL"]
        x = np.arange(len(cats))
        fig, ax = plt.subplots(figsize=(13, 5))
        for i, p in enumerate(pers):
            vals = piv[p].to_list()
            vals = [0 if v is None else v for v in vals]
            ax.bar(x + (i - 1.5) * 0.18, vals, width=0.18, label=p)
        ax.set_xticks(x)
        ax.set_xticklabels(cats, rotation=20, ha="right", fontsize=8)
        ax.set_title(title)
        ax.legend()
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(FIGS / fname, dpi=150)
        plt.close(fig)


def fig_drawdown(bts: dict):
    fig, axes = plt.subplots(2, 2, figsize=(12, 6), sharex=False)
    for ax, s in zip(axes.flat, ["BH", "SMA", "E2A_A1", "E2C"]):
        bt = bts["FULL"][s]
        eq = bt["equity"].to_numpy()
        peak = np.maximum.accumulate(eq)
        dd = (eq - peak) / peak * 100
        ax.fill_between(range(len(dd)), dd, 0, color="red", alpha=0.3)
        ax.set_title(f"Drawdown FULL — {s} ({dd.min():.1f}%)")
        ax.set_ylabel("DD %")
        ax.grid(alpha=0.3)
    fig.suptitle("Drawdown % en FULL (2017-2026): BH vs SMA vs E2-A vs E2-C")
    fig.tight_layout()
    fig.savefig(FIGS / "fig09_drawdown_full.png", dpi=150)
    plt.close(fig)


def fig_indicadores(df: pl.DataFrame):
    from src.features.technical import rsi as _rsi, macd as _macd, sma as _sma, cci as _cci
    sub = df.filter((pl.col("timestamp") >= datetime(2024, 9, 1, tzinfo=UTC)) &
                    (pl.col("timestamp") < datetime(2025, 3, 1, tzinfo=UTC))).sort("timestamp")
    sub = sub.with_columns([
        _sma(pl.col("close"), 7).alias("sma7"),
        _sma(pl.col("close"), 228).alias("sma228"),
        _rsi(pl.col("close"), 27).alias("rsi27"),
        _cci(pl.col("high"), pl.col("low"), pl.col("close"), 39).alias("cci39"),
    ])
    ml, sl, _h = _macd(pl.col("close"), 30, 46, 25)
    sub = sub.with_columns([ml.alias("ml"), sl.alias("sl")])
    ts = sub["timestamp"].to_list()
    fig, axes = plt.subplots(4, 1, figsize=(12, 9), sharex=True)
    axes[0].plot(ts, sub["close"].to_list(), lw=0.9, color="black", label="Close")
    axes[0].plot(ts, sub["sma7"].to_list(), lw=0.9, color="#2ca02c", label="SMA7")
    axes[0].plot(ts, sub["sma228"].to_list(), lw=0.9, color="#d62728", label="SMA228")
    axes[0].set_title("Ventana ejemplo 2024-09→2025-02: precio + SMA7/228 (SMA LONG cuando SMA7>SMA228)")
    axes[0].legend(fontsize=8, ncol=3)
    axes[0].grid(alpha=0.3)
    axes[1].plot(ts, sub["rsi27"].to_list(), lw=0.9, color="#1f77b4")
    axes[1].axhline(41, color="green", ls="--", lw=1, label="OS 41 (entrada al cruzar arriba)")
    axes[1].axhline(50, color="gray", ls="--", lw=1, label="Exit 50")
    axes[1].axhline(86, color="red", ls="--", lw=1, label="OB 86")
    axes[1].set_title("RSI(27)")
    axes[1].legend(fontsize=8, ncol=3)
    axes[1].grid(alpha=0.3)
    axes[2].plot(ts, sub["ml"].to_list(), lw=0.9, color="#ff7f0e", label="MACD")
    axes[2].plot(ts, sub["sl"].to_list(), lw=0.9, color="blue", label="Signal")
    axes[2].set_title("MACD(30,46,25): LONG en cruce alcista, FLAT en cruce bajista")
    axes[2].legend(fontsize=8, ncol=2)
    axes[2].grid(alpha=0.3)
    axes[3].plot(ts, sub["cci39"].to_list(), lw=0.9, color="#d62728")
    axes[3].axhline(-64, color="green", ls="--", lw=1, label="Entry -64")
    axes[3].axhline(143, color="red", ls="--", lw=1, label="Exit 143")
    axes[3].set_title("CCI(39)")
    axes[3].legend(fontsize=8, ncol=2)
    axes[3].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGS / "fig10_ejemplo_indicadores.png", dpi=150)
    plt.close(fig)


def main():
    FIGS.mkdir(parents=True, exist_ok=True)
    TABS.mkdir(parents=True, exist_ok=True)
    df = load_4h()
    print(f"[rango] {df['timestamp'].min()} -> {df['timestamp'].max()} | filas={len(df):,}")
    df = build_signals(df)
    bts = run_backtests(df)
    full = save_tables(bts)
    fig_price_halvings(df)
    fig_equity(bts, "FULL", INDEP, "fig02_equity_full_independientes.png",
               "Equity FULL 2017-2026 (4H, costos 15bps, lag=1) — indicadores independientes vs BH")
    fig_equity(bts, "FULL", COMP, "fig03_equity_full_compuestas.png",
               "Equity FULL 2017-2026 (4H) — E2-A (CCI+SMA+Vol+ATR) y E2-C vs BH")
    fig_equity(bts, "C16", ["BH", "RSI", "SMA", "E2A_A1", "E2A_A2", "E2C"], "fig04_equity_C16.png",
               "Equity ciclo 2016 (2017-08→2020-05, parcial: sin datos pre-2017-08)")
    fig_equity(bts, "C20", ["BH", "RSI", "SMA", "E2A_A1", "E2A_A2", "E2C"], "fig05a_equity_C20.png",
               "Equity ciclo 2020 (2020-05→2024-04)")
    fig_equity(bts, "C24", ["BH", "RSI", "SMA", "E2A_A1", "E2A_A2", "E2C"], "fig05b_equity_C24.png",
               "Equity ciclo 2024 (2024-04→2026-09)")
    fig_bars(full)
    fig_drawdown(bts)
    fig_indicadores(df)
    print("[OK] tablas + figuras en docs/tesis_resultados/")


if __name__ == "__main__":
    main()
