"""
scripts/run_tpe_v3.py

Re-seleccion de parametros con TPE para la v3 normalizada.

Protocolo (identico al original, con dos correcciones):
- 4 folds walk-forward: test 2021, 2022, 2023 y 2024.
- Objetivo: MEDIANA del Sharpe OOS entre folds.
- rf = 4% (antes 0%).
- Warmup GLOBAL: los indicadores se calculan sobre toda la historia y luego
  se recorta el fold (antes se recalculaban dentro de cada fold).
- Regla de validez UNICA para las 6 estrategias: exposicion >= 0.5%, al menos
  5 operaciones en el fold, no (PF < 1 y retorno <= 0) y MaxDD >= -50%.
  Si un fold es invalido, puntua -5.0. Se reemplazo el minimo de turnover de
  Exp01 (que penalizaba estrategias de baja frecuencia como A2) por un minimo
  de operaciones, mas interpretable y aplicable a todo el universo.

Salida: docs/tesis_resultados_v3/tablas/tpe_v3.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import optuna
import polars as pl
import yaml
from optuna.samplers import TPESampler

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backtesting.engine import backtest
from src.backtesting.metrics import summarize
from src.strategies.e2a_composite import E2A_A2_BEST, signal_e2a_long
from src.strategies.individuals import (
    EXP01_BEST,
    signal_cci_long,
    signal_ma_long,
    signal_macd_long,
    signal_rsi_long,
)

optuna.logging.set_verbosity(optuna.logging.WARNING)

UTC = timezone.utc
SEED = 42
RF = 0.04
FOLDS = [
    ("2021", datetime(2021, 1, 1, tzinfo=UTC), datetime(2022, 1, 1, tzinfo=UTC)),
    ("2022", datetime(2022, 1, 1, tzinfo=UTC), datetime(2023, 1, 1, tzinfo=UTC)),
    ("2023", datetime(2023, 1, 1, tzinfo=UTC), datetime(2024, 1, 1, tzinfo=UTC)),
    ("2024", datetime(2024, 1, 1, tzinfo=UTC), datetime(2025, 1, 1, tzinfo=UTC)),
]
HOLD = (datetime(2025, 1, 1, tzinfo=UTC), datetime(2026, 9, 2, tzinfo=UTC))
OUT = ROOT / "docs" / "tesis_resultados_v3" / "tablas" / "tpe_v3.json"


def load_setup():
    with open(ROOT / "configs" / "strategies.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    with open(ROOT / "configs" / "data.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    bt = cfg["backtest"]
    df = pl.read_parquet(ROOT / data["paths"]["analytics_4h"]).sort("timestamp")
    return df, float(cfg["backtest"]["risk_free_annual"]), float(bt["fees"]["taker"]) * 10_000, float(bt["slippage"]["bps"]), int(bt["execution"]["lag"])


def metrics_on(df: pl.DataFrame, sig_col: str, rf: float, fee_bps: float, slip_bps: float, lag: int) -> dict:
    bt = backtest(
        df.select(["timestamp", "open", "high", "low", "close", sig_col]),
        signal_col=sig_col,
        fee_bps=fee_bps,
        slippage_bps=slip_bps,
        lag=lag,
    )
    return summarize(bt, rf_annual=rf)


def is_valid(m: dict) -> bool:
    """Regla unica de la v3 normalizada (aplicada a las 6 estrategias)."""
    if m["exposure"] < 0.005:
        return False
    if m["trades"] < 5:
        return False
    pf = m["profit_factor"] if m["profit_factor"] is not None else float("inf")
    if pf < 1.0 and m["total_return_%"] <= 0:
        return False
    if m["maxDD_%"] < -50.0:
        return False
    return True


def fold_scores(signal_df: pl.DataFrame, sig_col: str, rf: float,
                fee_bps: float, slip_bps: float, lag: int) -> tuple[list[float], list[dict]]:
    scores, detail = [], []
    for name, d0, d1 in FOLDS:
        sub = signal_df.filter((pl.col("timestamp") >= d0) & (pl.col("timestamp") < d1))
        m = metrics_on(sub, sig_col, rf, fee_bps, slip_bps, lag)
        ok = is_valid(m)
        scores.append(m["sharpe"] if ok else -5.0)
        detail.append({
            "fold": name,
            "sharpe": round(m["sharpe"], 4),
            "valid": ok,
            "score": round(m["sharpe"], 4) if ok else -5.0,
            "trades": m["trades"],
            "maxDD_%": round(m["maxDD_%"], 2),
        })
    return scores, detail


# --------------------------------------------------------------------------- #
# Espacios de busqueda (identicos a los experimentos originales)
# --------------------------------------------------------------------------- #
def suggest(indicator: str, trial: optuna.Trial) -> dict | None:
    if indicator == "rsi":
        p = trial.suggest_int("period", 2, 50)
        os_ = trial.suggest_int("oversold", 10, 45)
        ob = trial.suggest_int("overbought", 55, 90)
        if not (os_ < 50 < ob):
            return None
        return {"period": p, "oversold": os_, "overbought": ob}
    if indicator == "macd":
        f = trial.suggest_int("fast", 3, 30)
        s = trial.suggest_int("slow", 15, 100)
        sig = trial.suggest_int("signal", 2, 30)
        if not (f < s):
            return None
        return {"fast": f, "slow": s, "signal": sig}
    if indicator in ("sma", "ema"):
        f = trial.suggest_int("fast", 2, 100)
        s = trial.suggest_int("slow", 20, 400)
        if not (f < s):
            return None
        return {"fast": f, "slow": s, "kind": indicator}
    if indicator == "cci":
        p = trial.suggest_int("period", 5, 50)
        e = trial.suggest_int("entry", -150, 0)
        x = trial.suggest_int("exit", 0, 150)
        if not (e < x):
            return None
        return {"period": p, "entry": e, "exit_": x}
    if indicator == "e2a":
        p = trial.suggest_int("cci_period", 10, 60)
        e = trial.suggest_int("cci_entry", -150, 0)
        x = trial.suggest_int("cci_exit", 0, 200)
        f = trial.suggest_int("sma_fast", 3, 50)
        s = trial.suggest_int("sma_slow", 80, 300)
        w = trial.suggest_int("vol_window", 10, 60)
        z = trial.suggest_float("vol_z_thr", 0.0, 2.5)
        if not (e < x and f < s):
            return None
        return {
            "cci_period": p, "cci_entry": e, "cci_exit": x,
            "sma_fast": f, "sma_slow": s, "vol_window": w, "vol_z_thr": z,
        }
    raise ValueError(indicator)


def apply_signal(indicator: str, df: pl.DataFrame, params: dict) -> tuple[pl.DataFrame, str]:
    if indicator == "rsi":
        return signal_rsi_long(df, **params), "signal_rsi"
    if indicator == "macd":
        return signal_macd_long(df, **params), "signal_macd"
    if indicator in ("sma", "ema"):
        return signal_ma_long(df, **params), f"signal_{indicator}"
    if indicator == "cci":
        return signal_cci_long(df, **params), "signal_cci"
    if indicator == "e2a":
        return signal_e2a_long(df, **params), "signal_e2a"
    raise ValueError(indicator)


def evaluate(indicator: str, df: pl.DataFrame, params: dict, rf: float,
             fee_bps: float, slip_bps: float, lag: int) -> dict:
    sig_df, col = apply_signal(indicator, df, params)
    scores, detail = fold_scores(sig_df, col, rf, fee_bps, slip_bps, lag)

    hold = sig_df.filter((pl.col("timestamp") >= HOLD[0]) & (pl.col("timestamp") <= HOLD[1]))
    m_hold = metrics_on(hold, col, rf, fee_bps, slip_bps, lag)

    full = metrics_on(sig_df, col, rf, fee_bps, slip_bps, lag)

    return {
        "params": params,
        "median_oos": round(float(np.median(scores)), 4),
        "folds": detail,
        "holdout": {
            "sharpe": round(m_hold["sharpe"], 4),
            "CAGR_%": round(m_hold["CAGR_%"], 2),
            "maxDD_%": round(m_hold["maxDD_%"], 2),
            "trades": m_hold["trades"],
        },
        "full": {
            "sharpe": round(full["sharpe"], 4),
            "CAGR_%": round(full["CAGR_%"], 2),
            "maxDD_%": round(full["maxDD_%"], 2),
            "trades": full["trades"],
            "win_rate_%": round(full["win_rate_%"], 2),
            "profit_factor": round(full["profit_factor"], 3) if full["profit_factor"] is not None else None,
        },
    }


def enqueue_dict(indicator: str, params: dict) -> dict:
    """Adapta los parametros viejos a los nombres que sugiere Optuna."""
    if indicator == "cci":
        return {"period": params["period"], "entry": params["entry"], "exit": params["exit_"]}
    if indicator in ("sma", "ema"):
        return {"fast": params["fast"], "slow": params["slow"]}
    return {k: v for k, v in params.items() if k != "kind"}


def optimize(indicator: str, df: pl.DataFrame, n_trials: int, rf: float,
             fee_bps: float, slip_bps: float, lag: int, seed_params: dict) -> dict:
    def objective(trial: optuna.Trial) -> float:
        params = suggest(indicator, trial)
        if params is None:
            raise optuna.TrialPruned()
        sig_df, col = apply_signal(indicator, df, params)
        scores, _ = fold_scores(sig_df, col, rf, fee_bps, slip_bps, lag)
        trial.set_user_attr("fold_scores", scores)
        return float(np.median(scores))

    study = optuna.create_study(direction="maximize", sampler=TPESampler(seed=SEED))
    # Warm start: el TPE arranca desde la seleccion anterior. Asi la
    # re-optimizacion no puede quedar peor que el punto de partida.
    study.enqueue_trial(enqueue_dict(indicator, seed_params))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    best = study.best_trial
    params = suggest(indicator, best)
    return {
        "best_params": params,
        "best_value": round(float(best.value), 4),
        "n_trials": n_trials,
        "seed_value": round(float(study.trials[0].value), 4),
    }


def main() -> None:
    df, rf_cfg, fee_bps, slip_bps, lag = load_setup()
    rf = RF if rf_cfg is None else rf_cfg
    print(f"[TPE v3] {len(df):,} velas | rf={rf:.2%} | folds={[f[0] for f in FOLDS]} | holdout=2025-2026")

    old_params = {
        "rsi": dict(EXP01_BEST["rsi"]),
        "macd": dict(EXP01_BEST["macd"]),
        "sma": {"fast": EXP01_BEST["sma"]["fast"], "slow": EXP01_BEST["sma"]["slow"], "kind": "sma"},
        "ema": {"fast": EXP01_BEST["ema"]["fast"], "slow": EXP01_BEST["ema"]["slow"], "kind": "ema"},
        "cci": dict(EXP01_BEST["cci"]),
        "e2a": {k: E2A_A2_BEST[k] for k in (
            "cci_period", "cci_entry", "cci_exit", "sma_fast", "sma_slow", "vol_window", "vol_z_thr")},
    }
    # Mismo presupuesto para todas: la unica diferencia es el espacio de busqueda.
    budgets = {k: 100 for k in ("rsi", "macd", "sma", "ema", "cci", "e2a")}

    results: dict[str, dict] = {}
    for indicator in ("rsi", "macd", "sma", "ema", "cci", "e2a"):
        print(f"\n[TPE v3] optimizando {indicator.upper()} ({budgets[indicator]} trials)...")
        opt = optimize(indicator, df, budgets[indicator], rf, fee_bps, slip_bps, lag, old_params[indicator])
        new = evaluate(indicator, df, opt["best_params"], rf, fee_bps, slip_bps, lag)
        old = evaluate(indicator, df, old_params[indicator], rf, fee_bps, slip_bps, lag)
        results[indicator] = {
            "optimization": opt,
            "new": new,
            "old": old,
        }
        print(f"  NEW mediana={new['median_oos']:.3f} holdout={new['holdout']['sharpe']:.3f} "
              f"full={new['full']['sharpe']:.3f} | OLD mediana={old['median_oos']:.3f} "
              f"holdout={old['holdout']['sharpe']:.3f} full={old['full']['sharpe']:.3f}")
        print(f"  NEW params={new['params']}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "method": "TPE + median OOS Sharpe (folds 2021-2024), rf=4%, warmup global",
        "rf_annual": rf,
        "seed": SEED,
        "folds": [{"fold": f[0], "from": str(f[1]), "to": str(f[2])} for f in FOLDS],
        "holdout": {"from": str(HOLD[0]), "to": str(HOLD[1])},
        "validity_rule": "exposure>=0.5%, trades>=5, not(PF<1 and ret<=0), maxDD>=-50%; invalido -> -5.0",
        "results": results,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[OK] {OUT}")


if __name__ == "__main__":
    main()
