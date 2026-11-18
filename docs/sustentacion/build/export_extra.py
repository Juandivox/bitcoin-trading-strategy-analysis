"""Datos extra de la sustentacion: ejemplo numerico del Sharpe y PSO vs TPE.

Uso (venv de investigacion): python docs/sustentacion/build/export_extra.py
Salida: data/extra.json
"""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
import numpy as np
import polars as pl
from run_resultados import load_config, build_periods
from src.backtesting.engine import backtest
from src.backtesting.metrics import summarize, sharpe
from src.strategies.e2a_composite import signal_e2a_long
from src.strategies.individuals import signal_ma_long
from src.strategies.buy_and_hold import signal_buy_and_hold

OUT = Path(__file__).parent / "data"
scfg, dcfg = load_config(); bt = scfg["backtest"]; params = scfg["v3_selection"]["params"]
RF, P = float(bt["risk_free_annual"]), 2190
df = pl.read_parquet(ROOT / dcfg["paths"]["analytics_4h"]).sort("timestamp")
pso = json.load(open(ROOT / "docs/tesis_resultados_v3/tablas/pso_v3.json", encoding="utf-8"))
VARIANTS = {"A2_TPE": params["e2a"], "PSO_informe": pso["old_pso_v2"]["params"], "PSO_v3": pso["best_params"]}
for k, v in VARIANTS.items():
    df = signal_e2a_long(df, **v).rename({"signal_e2a": f"sig_{k}"})
df = signal_ma_long(df, kind="sma", **params["sma"]).rename({"signal_sma": "sig_SMA"})
df = signal_buy_and_hold(df).rename({"signal_bh": "sig_BH"})
periods = build_periods(df)


def run(sub, k):
    return backtest(sub.select(["timestamp", "open", "high", "low", "close", f"sig_{k}"]), signal_col=f"sig_{k}",
                    initial_capital=float(bt["initial_capital"]), fee_bps=float(bt["fees"]["taker"]) * 1e4,
                    slippage_bps=float(bt["slippage"]["bps"]), lag=int(bt["execution"]["lag"]), allow_short=False)


out = {"rf_annual": RF, "P": P, "rf_per_bar": RF / P, "pso_space": pso["space"], "variants": VARIANTS, "periods": {}}
for pname in ("FULL", "IS70", "OOS30"):
    d0, d1 = periods[pname]
    sub = df.filter((pl.col("timestamp") >= d0) & (pl.col("timestamp") < d1)).sort("timestamp")
    out["periods"][pname] = {}
    for k in list(VARIANTS) + ["SMA", "BH"]:
        r = run(sub, k)
        m = summarize(r, rf_annual=RF)
        out["periods"][pname][k] = {x: m[x] for x in ("sharpe", "CAGR_%", "maxDD_%", "trades", "exposure")}
        if pname == "FULL":
            ret = r["strategy_ret"].drop_nulls().drop_nans().to_numpy()
            ex = ret - RF / P
            out["periods"][pname][k]["mean_bar"] = float(np.mean(ret))
            out["periods"][pname][k]["mean_excess_bar"] = float(np.mean(ex))
            out["periods"][pname][k]["std_excess_bar"] = float(np.std(ex, ddof=1))
            out["periods"][pname][k]["sharpe_check"] = float(np.mean(ex) / np.std(ex, ddof=1) * np.sqrt(P))
            out["periods"][pname][k]["sharpe_rf0"] = sharpe(ret, P, rf_annual=0.0)
json.dump(out, open(OUT / "extra.json", "w"), indent=1, default=float)
for pn, d in out["periods"].items():
    for k, m in d.items():
        print(pn, f"{k:12s}", {x: round(v, 6) if isinstance(v, float) else v for x, v in m.items()})
