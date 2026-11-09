"""
scripts/run_tesis_resultados_v2.py (NUEVA VERSION v2 — no toca la v1).

Diferencias frente a scripts/run_tesis_resultados.py (v1):
1. Split cronologico 70/30: IS70 (primer 70% de velas 4H, seleccion) vs OOS30
   (ultimo 30%, forward testing). Corte determinista por indice, sin shuffle.
2. Foco en las 13 estrategias: 9 independientes (BH, BH+TP/SL, RSI, MACD,
   SMA, EMA, CCI) + 4 compuestas (E2-A A1, E2-A A2, E2-A PSO, E2-C).
3. Optimizacion UNICAMENTE por Enjambre de Particulas (PSO, numpy puro, sin
   Optuna/TPE/geneticos). Objetivo: Sharpe en IS70. Semilla fija (42).
4. Tablas y figuras por temporada (halvings C16/C20/C24 + FULL + IS70/OOS30)
   con ventana de fechas EXPLICITA en cada fila, para que un "132%" siempre
   vaya acompanado de su periodo (p. ej. 2020-05-11 -> 2024-04-19).

Salidas: docs/tesis_resultados_v2/figs/*.png + tablas/*.csv + pso_best.json
"""
from __future__ import annotations

import json
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
OUTDIR = ROOT / "docs" / "tesis_resultados_v2"
FIGS = OUTDIR / "figs"
TABS = OUTDIR / "tablas"
P4H = 2190.0  # velas 4H por anio (6*365)
UTC = timezone.utc
SEED = 42

HALVINGS = {
    "2016-07-09": datetime(2016, 7, 9, tzinfo=UTC),
    "2020-05-11": datetime(2020, 5, 11, tzinfo=UTC),
    "2024-04-20": datetime(2024, 4, 20, tzinfo=UTC),
}

# 13 estrategias v2: 9 independientes (v1) + 4 compuestas (A1, A2, PSO, E2C).
INDEP = ["BH", "BH_TP5", "BH_SL5", "BH_TPSL", "RSI", "MACD", "SMA", "EMA", "CCI"]
COMP = ["BH", "E2A_A1", "E2A_A2", "E2A_PSO", "E2C"]
MAIN5 = ["BH", "SMA", "E2A_A2", "E2A_PSO", "E2C"]  # foco de temporadas y seleccion
ALL = INDEP + ["E2A_A1", "E2A_A2", "E2A_PSO", "E2C"]
COLORS = {
    "BH": "black", "BH_TP5": "gray", "BH_SL5": "silver", "BH_TPSL": "dimgray",
    "RSI": "#1f77b4", "MACD": "#ff7f0e", "SMA": "#2ca02c", "EMA": "#9467bd",
    "CCI": "#d62728", "E2A_A1": "#e377c2", "E2A_A2": "#8c564b", "E2A_PSO": "#ff0000",
    "E2C": "#17becf",
}

# Espacio PSO (7 dims; ATR excluido: no afecta la senal/backtest actual, se fija a 14/2.0
# y se documenta como trabajo futuro con stop intra-vela).
SPACE = [
    ("cci_period", 10.0, 60.0, "int"),
    ("cci_entry", -150.0, 50.0, "float"),
    ("cci_exit", 50.0, 250.0, "float"),
    ("sma_fast", 5.0, 30.0, "int"),
    ("sma_slow", 100.0, 250.0, "int"),
    ("vol_window", 10.0, 60.0, "int"),
    ("vol_z_thr", -0.5, 1.5, "float"),
]
LO = np.array([s[1] for s in SPACE])
HI = np.array([s[2] for s in SPACE])


def load_4h() -> pl.DataFrame:
    cache = ROOT / "data" / "processed" / "btcusdt_4h.parquet"
    if cache.exists():
        df = pl.read_parquet(cache).sort("timestamp")
        print(f"[4h] cache {cache} filas={len(df):,}")
        return df
    print("[4h] resampleando 1m -> 4h...")
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
    return df.with_columns(pl.Series(out, sig, dtype=pl.Int8))


def build_base_signals(df: pl.DataFrame) -> pl.DataFrame:
    """Las 12 senales base (falta E2A_PSO, que se agrega tras el PSO sobre IS70)."""
    df = signal_buy_and_hold(df).rename({"signal_bh": "sig_BH"})
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
    """Alias historico de la v2: rf=0 explicito para reproducir sus tablas.

    La salida canonica del proyecto es scripts/run_resultados.py (v3, rf=4%).
    """
    return summarize(bt, rf_annual=0.0)


def decode(x: np.ndarray) -> dict | None:
    """Vector PSO -> params E2-A. Retorna None si viola entry<exit."""
    vals = {}
    for (name, lo, hi, kind), v in zip(SPACE, x):
        v = float(np.clip(v, lo, hi))
        vals[name] = int(round(v)) if kind == "int" else round(v, 4)
    if not (vals["cci_entry"] < vals["cci_exit"] - 5):
        return None
    if not (vals["sma_fast"] < vals["sma_slow"]):
        return None
    return vals


def fitness_sharpe_is(df_is: pl.DataFrame, x: np.ndarray) -> tuple[float, dict]:
    """Sharpe en IS70 para un vector; penaliza <10 trades o params invalidos."""
    params = decode(x)
    if params is None:
        return -10.0, {}
    try:
        d = signal_e2a_long(df_is, **params).rename({"signal_e2a": "_sigx"})
    except Exception:
        return -10.0, {}
    bt = backtest(d.select(["timestamp", "open", "high", "low", "close", "_sigx"]),
                  signal_col="_sigx", initial_capital=10_000.0,
                  fee_bps=10.0, slippage_bps=5.0, lag=1, allow_short=False)
    m = summarize_4h(bt)
    sh = m["sharpe"]
    if m["trades"] < 10:
        sh -= 2.0  # penaliza estrategias casi sin operar
    return sh, m


def run_pso(df_is: pl.DataFrame, n_particles: int = 12, n_iters: int = 20, seed: int = SEED):
    rng = np.random.default_rng(seed)
    span = HI - LO
    X = rng.uniform(LO, HI, size=(n_particles, len(SPACE)))
    # Semilla 0 = referencia A2 (garantiza PSO >= A2).
    X[0] = np.array([E2A_A2_BEST["cci_period"], E2A_A2_BEST["cci_entry"], E2A_A2_BEST["cci_exit"],
                     E2A_A2_BEST["sma_fast"], E2A_A2_BEST["sma_slow"],
                     E2A_A2_BEST["vol_window"], E2A_A2_BEST["vol_z_thr"]], dtype=float)
    V = rng.uniform(-0.2 * span, 0.2 * span, size=(n_particles, len(SPACE)))
    fit = np.full(n_particles, -np.inf)
    info = [{} for _ in range(n_particles)]
    for i in range(n_particles):
        fit[i], info[i] = fitness_sharpe_is(df_is, X[i])
    pbest_X = X.copy()
    pbest_f = fit.copy()
    gb = int(np.argmax(pbest_f))
    gbest_X, gbest_f = pbest_X[gb].copy(), float(pbest_f[gb])
    hist = [gbest_f]
    print(f"[PSO] init mejor Sharpe_IS={gbest_f:.3f} params={decode(gbest_X)}")
    w, c1, c2 = 0.72, 1.49, 1.49
    Vmax = 0.25 * span
    for it in range(1, n_iters + 1):
        r1 = rng.random((n_particles, len(SPACE)))
        r2 = rng.random((n_particles, len(SPACE)))
        V = w * V + c1 * r1 * (pbest_X - X) + c2 * r2 * (gbest_X - X)
        V = np.clip(V, -Vmax, Vmax)
        X = np.clip(X + V, LO, HI)
        for i in range(n_particles):
            f, m = fitness_sharpe_is(df_is, X[i])
            if f > pbest_f[i]:
                pbest_f[i], pbest_X[i] = f, X[i].copy()
        gb = int(np.argmax(pbest_f))
        if pbest_f[gb] > gbest_f:
            gbest_f, gbest_X = float(pbest_f[gb]), pbest_X[gb].copy()
        hist.append(gbest_f)
        print(f"[PSO] iter {it:02d}/{n_iters} mejor Sharpe_IS={gbest_f:.3f}")
    return decode(gbest_X), gbest_f, hist


def main():
    FIGS.mkdir(parents=True, exist_ok=True)
    TABS.mkdir(parents=True, exist_ok=True)
    df = load_4h()
    n = len(df)
    cut_idx = int(n * 0.70)
    cut_ts = df.sort("timestamp")["timestamp"][cut_idx]
    dmin, dmax = df["timestamp"].min(), df["timestamp"].max()
    print(f"[split70/30] N={n:,} cut_idx={cut_idx} corte={cut_ts} | IS=[{dmin},{cut_ts}) OOS=[{cut_ts},{dmax}]")

    PERIODS = {
        "FULL": (datetime(2017, 8, 17, tzinfo=UTC), datetime(2026, 9, 2, tzinfo=UTC)),
        "C16": (datetime(2017, 8, 17, tzinfo=UTC), datetime(2020, 5, 11, tzinfo=UTC)),
        "C20": (datetime(2020, 5, 11, tzinfo=UTC), datetime(2024, 4, 20, tzinfo=UTC)),
        "C24": (datetime(2024, 4, 20, tzinfo=UTC), datetime(2026, 9, 2, tzinfo=UTC)),
        "IS70": (dmin, cut_ts),
        "OOS30": (cut_ts, datetime(2026, 9, 2, tzinfo=UTC)),
    }

    df = build_base_signals(df)

    # --- PSO sobre IS70 ---
    df_is = df.filter((pl.col("timestamp") >= PERIODS["IS70"][0]) & (pl.col("timestamp") < PERIODS["IS70"][1])).sort("timestamp")
    print(f"[IS70] velas={len(df_is):,} ({df_is['timestamp'].min()} -> {df_is['timestamp'].max()})")
    base_sh, _ = fitness_sharpe_is(df_is, np.array(
        [E2A_A2_BEST["cci_period"], E2A_A2_BEST["cci_entry"], E2A_A2_BEST["cci_exit"],
         E2A_A2_BEST["sma_fast"], E2A_A2_BEST["sma_slow"],
         E2A_A2_BEST["vol_window"], E2A_A2_BEST["vol_z_thr"]], dtype=float))
    print(f"[PSO] baseline A2 Sharpe_IS={base_sh:.3f}")
    best, best_f, hist = run_pso(df_is)
    print(f"[PSO] BEST Sharpe_IS={best_f:.3f} params={best}")
    (TABS / "pso_best.json").write_text(json.dumps(
        {"best_params": best, "best_sharpe_IS": round(best_f, 4), "baseline_A2_sharpe_IS": round(base_sh, 4),
         "n_particles": 12, "n_iters": 20, "seed": SEED, "objective": "sharpe_IS70",
         "space": [{k: v} for k, v in [("dims", [s[0] for s in SPACE]), ("lo", LO.tolist()), ("hi", HI.tolist())]]},
        indent=2), encoding="utf-8")
    pl.DataFrame({"iter": list(range(len(hist))), "best_sharpe_IS": hist}).write_csv(TABS / "pso_history.csv")

    # Senal PSO sobre el df completo (una sola vez) y backtests por periodo.
    df = signal_e2a_long(df, **best).rename({"signal_e2a": "sig_E2A_PSO"})

    bts: dict[str, dict[str, pl.DataFrame]] = {}
    for pname, (d0, d1) in PERIODS.items():
        sub = df.filter((pl.col("timestamp") >= d0) & (pl.col("timestamp") < d1)).sort("timestamp")
        print(f"[{pname}] velas={len(sub):,} ({sub['timestamp'].min()} -> {sub['timestamp'].max()})")
        bts[pname] = {}
        for s in ALL:
            bt = backtest(sub.select(["timestamp", "open", "high", "low", "close", f"sig_{s}"]),
                          signal_col=f"sig_{s}", initial_capital=10_000.0,
                          fee_bps=10.0, slippage_bps=5.0, lag=1, allow_short=False)
            bts[pname][s] = bt

    # --- Tablas (con ventana explicita en cada fila) ---
    rows = []
    for pname, (d0, d1) in PERIODS.items():
        sub0 = df.filter((pl.col("timestamp") >= d0) & (pl.col("timestamp") < d1)).sort("timestamp")
        ventana = f"{sub0['timestamp'].min()} -> {sub0['timestamp'].max()}" if len(sub0) else f"{d0} -> {d1}"
        for s in ALL:
            m = summarize_4h(bts[pname][s])
            m["periodo"] = pname
            m["ventana"] = ventana
            m["estrategia"] = s
            rows.append(m)
    full = pl.DataFrame(rows)
    full.write_csv(TABS / "metricas_por_periodo_v2.csv")
    for pname in PERIODS:
        full.filter(pl.col("periodo") == pname).write_csv(TABS / f"metricas_{pname}_v2.csv")
    with open(TABS / "metricas_por_periodo_v2.txt", "w", encoding="utf-8") as f:
        f.write(full.sort(["periodo", "sharpe"]).to_pandas().to_string())
    print(full.sort(["periodo", "sharpe"]).to_pandas().to_string())

    # --- Figuras v2 ---
    # 1. Precio + halvings + corte 70/30
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.plot(df["timestamp"].to_list(), df["close"].to_list(), lw=0.8, color="black")
    ax.set_yscale("log")
    for label, dt in HALVINGS.items():
        if dmin <= dt <= dmax:
            ax.axvline(dt, color="red", ls="--", lw=1)
            ax.text(dt, df["close"].max(), f" halving {label}", color="red", fontsize=8, va="top")
    ax.axvline(cut_ts, color="blue", ls="-.", lw=1.2)
    ax.text(cut_ts, df["close"].min(), " corte 70/30 ", color="blue", fontsize=8, va="bottom", ha="right")
    ax.set_title("BTC/USDT 4H (log) 2017-2026: halvings + corte 70/30 (IS | OOS)")
    ax.set_ylabel("Close USDT (log)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGS / "v2_fig01_precio_halvings_split.png", dpi=150)
    plt.close(fig)

    def fig_equity(pname, strats, fname, title):
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

    fig_equity("FULL", INDEP, "v2_fig02_equity_FULL_indep.png",
               "Equity FULL 2017-08-17→2026-09-01 (4H, costos 15bps, lag=1) — independientes vs BH")
    fig_equity("FULL", COMP, "v2_fig03_equity_FULL_comp.png",
               "Equity FULL 2017-08-17→2026-09-01 (4H) — compuestas (E2-A A1/A2/PSO, E2-C) vs BH")
    fig_equity("IS70", INDEP, "v2_fig04_equity_IS70_indep.png",
               f"Equity IS70 IN-SAMPLE ({PERIODS['IS70'][0].date()}→{cut_ts.date()}) — independientes")
    fig_equity("IS70", COMP, "v2_fig05_equity_IS70_comp.png",
               f"Equity IS70 IN-SAMPLE ({PERIODS['IS70'][0].date()}→{cut_ts.date()}) — compuestas (PSO optimizada aqui)")
    fig_equity("OOS30", INDEP, "v2_fig06_equity_OOS30_indep.png",
               f"Equity OOS30 FORWARD no visto ({cut_ts.date()}→2026-09-01) — independientes")
    fig_equity("OOS30", COMP, "v2_fig07_equity_OOS30_comp.png",
               f"Equity OOS30 FORWARD no visto ({cut_ts.date()}→2026-09-01) — compuestas")
    fig_equity("C16", MAIN5, "v2_fig08a_equity_C16.png",
               "Equity ciclo 2016 (2017-08-17→2020-05-11, parcial sin datos pre-2017-08)")
    fig_equity("C20", MAIN5, "v2_fig08b_equity_C20.png", "Equity ciclo 2020 (2020-05-11→2024-04-20)")
    fig_equity("C24", MAIN5, "v2_fig08c_equity_C24.png", "Equity ciclo 2024 (2024-04-20→2026-09-01)")

    # Barras por temporada (halvings + FULL) con las 13 estrategias
    for metric, fname, title in [
        ("sharpe", "v2_fig09_barras_sharpe.png", "Sharpe (4H, rf=0) por estrategia y temporada"),
        ("total_return_%", "v2_fig10_barras_retorno.png", "Retorno total % neto por estrategia y temporada"),
        ("maxDD_%", "v2_fig11_barras_maxdd.png", "Max Drawdown % por estrategia y temporada"),
    ]:
        piv = full.pivot(index="estrategia", on="periodo", values=metric).sort("estrategia")
        cats = piv["estrategia"].to_list()
        pers = ["C16", "C20", "C24", "FULL"]
        pers = [p for p in pers if p in piv.columns]
        x = np.arange(len(cats))
        fig, ax = plt.subplots(figsize=(14, 5))
        for i, p in enumerate(pers):
            vals = [0 if v is None else v for v in piv[p].to_list()]
            ax.bar(x + (i - (len(pers) - 1) / 2) * 0.2, vals, width=0.2, label=p)
        ax.set_xticks(x)
        ax.set_xticklabels(cats, rotation=20, ha="right", fontsize=8)
        ax.set_title(title)
        ax.legend(fontsize=8, ncol=4)
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        fig.savefig(FIGS / fname, dpi=150)
        plt.close(fig)

    # Barras IS70 vs OOS30: Sharpe con las 13 (valida robustez fuera de muestra)
    piv = full.pivot(index="estrategia", on="periodo", values="sharpe").sort("estrategia")
    cats = piv["estrategia"].to_list()
    x = np.arange(len(cats))
    fig, ax = plt.subplots(figsize=(14, 5))
    for i, p in enumerate(["IS70", "OOS30"]):
        vals = [0 if v is None else v for v in piv[p].to_list()]
        ax.bar(x + (i - 0.5) * 0.35, vals, width=0.35, label=p)
    ax.set_xticks(x)
    ax.set_xticklabels(cats, rotation=20, ha="right", fontsize=8)
    ax.set_title("Sharpe IS70 (2017-08-17→2023-12-16, backtest) vs OOS30 (2023-12-17→2026-09-01, forward no visto)")
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGS / "v2_fig12_barras_sharpe_ISOOS.png", dpi=150)
    plt.close(fig)

    # Convergencia PSO
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(range(len(hist)), hist, marker="o", lw=1.5)
    ax.set_title(f"Convergencia PSO (12 particulas x 20 iters, semilla {SEED}): mejor Sharpe IS70")
    ax.set_xlabel("Iteracion")
    ax.set_ylabel("Mejor Sharpe IS70")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGS / "v2_fig13_pso_convergencia.png", dpi=150)
    plt.close(fig)

    # Drawdown FULL (2x3): BH, SMA, E2-A A1/A2/PSO, E2-C
    fig, axes = plt.subplots(2, 3, figsize=(14, 6), sharex=False)
    for ax, s in zip(axes.flat, COMP + ["SMA"]):
        bt = bts["FULL"][s]
        eq = bt["equity"].to_numpy()
        peak = np.maximum.accumulate(eq)
        dd = (eq - peak) / peak * 100
        ax.fill_between(range(len(dd)), dd, 0, color="red", alpha=0.3)
        ax.set_title(f"DD FULL — {s} ({dd.min():.1f}%)")
        ax.set_ylabel("DD %")
        ax.grid(alpha=0.3)
    fig.suptitle("Drawdown % en FULL (2017-08-17→2026-09-01): comparativa riesgo")
    fig.tight_layout()
    fig.savefig(FIGS / "v2_fig14_drawdown_full.png", dpi=150)
    plt.close(fig)

    print("[OK v2] tablas + figuras en docs/tesis_resultados_v2/")


if __name__ == "__main__":
    main()
