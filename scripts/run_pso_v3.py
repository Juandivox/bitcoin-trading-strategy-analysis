"""
scripts/run_pso_v3.py

Re-optimizacion PSO de E2-A para la v3. Diferencia con la v2: la funcion de
aptitud usa el Sharpe canonico CON tasa libre de riesgo (rf del config, 4%).

No toca los resultados historicos de la v2. Salidas:
- docs/tesis_resultados_v3/tablas/pso_v3.json
- docs/tesis_resultados_v3/tablas/pso_v3_history.csv
- docs/tesis_resultados_v3/figs/v3_fig06_pso_convergencia.png

Uso:
    python scripts/run_pso_v3.py
    python scripts/run_pso_v3.py --rf 0.04 --iters 20
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backtesting.engine import backtest
from src.backtesting.metrics import periods_per_year, summarize
from src.strategies.e2a_composite import E2A_A2_BEST, signal_e2a_long

OUTDIR = ROOT / "docs" / "tesis_resultados_v3"
TABS = OUTDIR / "tablas"
FIGS = OUTDIR / "figs"
UTC = timezone.utc
SEED = 42

# Mismo espacio que la v2 (7 dimensiones; sin ATR).
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


def decode(x: np.ndarray) -> dict | None:
    """Vector PSO -> parametros E2-A. None si viola entry < exit."""
    vals: dict = {}
    for (name, lo, hi, kind), v in zip(SPACE, x):
        v = float(np.clip(v, lo, hi))
        vals[name] = int(round(v)) if kind == "int" else round(v, 4)
    if not (vals["cci_entry"] < vals["cci_exit"] - 5):
        return None
    if not (vals["sma_fast"] < vals["sma_slow"]):
        return None
    return vals


def load_setup() -> tuple[pl.DataFrame, float, float, float, int, float]:
    with open(ROOT / "configs" / "strategies.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    with open(ROOT / "configs" / "data.yaml", encoding="utf-8") as f:
        data_cfg = yaml.safe_load(f)

    bt = cfg["backtest"]
    rf_annual = float(bt["risk_free_annual"])
    fee_bps = float(bt["fees"]["taker"]) * 10_000.0
    slippage_bps = float(bt["slippage"]["bps"])
    lag = int(bt["execution"]["lag"])
    capital = float(bt["initial_capital"])

    path = ROOT / data_cfg["paths"]["analytics_4h"]
    df = pl.read_parquet(path).sort("timestamp")
    if periods_per_year(df["timestamp"]) != 2190:
        raise SystemExit("[PSO v3] el dataset no es 4H; abortando.")
    return df, rf_annual, fee_bps, slippage_bps, lag, capital


def make_fitness(df_is: pl.DataFrame, rf_annual: float, fee_bps: float,
                 slippage_bps: float, lag: int, capital: float):
    def fitness(x: np.ndarray) -> tuple[float, dict]:
        params = decode(x)
        if params is None:
            return -10.0, {}
        d = signal_e2a_long(df_is, **params).rename({"signal_e2a": "_sigx"})
        bt = backtest(
            d.select(["timestamp", "open", "high", "low", "close", "_sigx"]),
            signal_col="_sigx",
            initial_capital=capital,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            lag=lag,
            allow_short=False,
        )
        m = summarize(bt, rf_annual=rf_annual)
        sh = m["sharpe"]
        if m["trades"] < 10:
            sh -= 2.0
        return sh, m

    return fitness


def run_pso(fitness, n_particles: int, n_iters: int, seed: int):
    rng = np.random.default_rng(seed)
    span = HI - LO
    X = rng.uniform(LO, HI, size=(n_particles, len(SPACE)))
    # Semilla 0 = referencia A2 (garantiza PSO >= A2).
    X[0] = np.array([
        E2A_A2_BEST["cci_period"], E2A_A2_BEST["cci_entry"], E2A_A2_BEST["cci_exit"],
        E2A_A2_BEST["sma_fast"], E2A_A2_BEST["sma_slow"],
        E2A_A2_BEST["vol_window"], E2A_A2_BEST["vol_z_thr"],
    ], dtype=float)
    V = rng.uniform(-0.2 * span, 0.2 * span, size=(n_particles, len(SPACE)))
    fit = np.full(n_particles, -np.inf)
    info = [{} for _ in range(n_particles)]
    for i in range(n_particles):
        fit[i], info[i] = fitness(X[i])

    pbest_X = X.copy()
    pbest_f = fit.copy()
    gb = int(np.argmax(pbest_f))
    gbest_X, gbest_f = pbest_X[gb].copy(), float(pbest_f[gb])
    hist = [gbest_f]
    print(f"[PSO v3] init mejor Sharpe_IS={gbest_f:.3f} params={decode(gbest_X)}")

    w, c1, c2 = 0.72, 1.49, 1.49
    Vmax = 0.25 * span
    for it in range(1, n_iters + 1):
        r1 = rng.random((n_particles, len(SPACE)))
        r2 = rng.random((n_particles, len(SPACE)))
        V = w * V + c1 * r1 * (pbest_X - X) + c2 * r2 * (gbest_X - X)
        V = np.clip(V, -Vmax, Vmax)
        X = np.clip(X + V, LO, HI)
        for i in range(n_particles):
            f, m = fitness(X[i])
            if f > pbest_f[i]:
                pbest_f[i], pbest_X[i] = f, X[i].copy()
        gb = int(np.argmax(pbest_f))
        if pbest_f[gb] > gbest_f:
            gbest_f, gbest_X = float(pbest_f[gb]), pbest_X[gb].copy()
        hist.append(gbest_f)
        print(f"[PSO v3] iter {it:02d}/{n_iters} mejor Sharpe_IS={gbest_f:.3f}")

    return decode(gbest_X), gbest_f, hist


def main() -> None:
    parser = argparse.ArgumentParser(description="PSO v3 con rf (default 4%).")
    parser.add_argument("--rf", type=float, default=None)
    parser.add_argument("--particles", type=int, default=12)
    parser.add_argument("--iters", type=int, default=20)
    args = parser.parse_args()

    df, rf_cfg, fee_bps, slippage_bps, lag, capital = load_setup()
    rf = float(args.rf if args.rf is not None else rf_cfg)

    n = len(df)
    cut_idx = int(n * 0.70)
    df_is = df[:cut_idx]
    print(f"[PSO v3] IS70={len(df_is):,} velas | rf={rf:.2%} | fees={fee_bps:.0f}+{slippage_bps:.0f}bps | lag={lag}")

    fitness = make_fitness(df_is, rf, fee_bps, slippage_bps, lag, capital)

    # Referencias: A2 y PSO v2, ambas reevaluadas con el rf actual.
    a2_vec = np.array([
        E2A_A2_BEST["cci_period"], E2A_A2_BEST["cci_entry"], E2A_A2_BEST["cci_exit"],
        E2A_A2_BEST["sma_fast"], E2A_A2_BEST["sma_slow"],
        E2A_A2_BEST["vol_window"], E2A_A2_BEST["vol_z_thr"],
    ], dtype=float)
    a2_fit, a2_m = fitness(a2_vec)

    old_path = ROOT / "docs" / "tesis_resultados_v2" / "tablas" / "pso_best.json"
    old_params = json.loads(old_path.read_text(encoding="utf-8"))["best_params"]
    old_vec = np.array([
        old_params["cci_period"], old_params["cci_entry"], old_params["cci_exit"],
        old_params["sma_fast"], old_params["sma_slow"],
        old_params["vol_window"], old_params["vol_z_thr"],
    ], dtype=float)
    old_fit, old_m = fitness(old_vec)

    print(f"[PSO v3] referencia A2     : Sharpe_IS={a2_fit:.3f} params={E2A_A2_BEST}")
    print(f"[PSO v3] referencia PSO v2 : Sharpe_IS={old_fit:.3f} params={decode(old_vec)}")

    best, best_f, hist = run_pso(fitness, args.particles, args.iters, SEED)
    _, best_m = fitness(np.array([
        best[k] for k in ("cci_period", "cci_entry", "cci_exit", "sma_fast",
                          "sma_slow", "vol_window", "vol_z_thr")
    ], dtype=float))

    TABS.mkdir(parents=True, exist_ok=True)
    FIGS.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "objective": "sharpe_IS70",
        "rf_annual": rf,
        "timeframe": "4h",
        "periods_per_year": 2190,
        "n_particles": args.particles,
        "n_iters": args.iters,
        "seed": SEED,
        "space": {
            "dims": [s[0] for s in SPACE],
            "lo": LO.tolist(),
            "hi": HI.tolist(),
        },
        "best_params": best,
        "best_sharpe_IS": round(best_f, 4),
        "best_metrics_IS": {
            "sharpe": round(best_m["sharpe"], 4),
            "trades": best_m["trades"],
            "exposure": best_m["exposure"],
            "maxDD_%": round(best_m["maxDD_%"], 2),
            "CAGR_%": round(best_m["CAGR_%"], 2),
        },
        "baseline_A2": {
            "params": {k: E2A_A2_BEST[k] for k in
                       ("cci_period", "cci_entry", "cci_exit", "sma_fast",
                        "sma_slow", "vol_window", "vol_z_thr")},
            "sharpe_IS_rf": round(a2_fit, 4),
        },
        "old_pso_v2": {
            "params": decode(old_vec),
            "sharpe_IS_rf": round(old_fit, 4),
        },
    }
    (TABS / "pso_v3.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    pl.DataFrame({"iter": list(range(len(hist))), "best_sharpe_IS": hist}).write_csv(
        TABS / "pso_v3_history.csv"
    )

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(range(len(hist)), hist, marker="o", lw=1.5)
    ax.axhline(a2_fit, color="gray", ls="--", lw=1, label=f"A2 ref ({a2_fit:.3f})")
    ax.axhline(old_fit, color="tab:orange", ls=":", lw=1, label=f"PSO v2 ref ({old_fit:.3f})")
    ax.set_title(f"Convergencia PSO v3 (rf={rf:.1%}, {args.particles} particulas x {args.iters} iters)")
    ax.set_xlabel("Iteracion")
    ax.set_ylabel("Mejor Sharpe IS70")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIGS / "v3_fig06_pso_convergencia.png", dpi=150)
    plt.close(fig)

    print(f"\n[PSO v3] BEST Sharpe_IS={best_f:.3f}")
    print(f"[PSO v3] params={best}")
    print(f"[PSO v3] A2={a2_fit:.3f} | PSO v2={old_fit:.3f} | PSO v3={best_f:.3f}")
    print(f"[OK] {TABS / 'pso_v3.json'}")


if __name__ == "__main__":
    main()
