"""Exporta los datos de los graficos de la sustentacion desde el motor canonico.

Reutiliza scripts/run_resultados.py (mismos params v3, costos, lag, rf=4%).
Uso (venv de investigacion):  python docs/sustentacion/build/export_data.py
"""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
import polars as pl
from run_resultados import load_config, build_signals, ALL
from src.backtesting.engine import backtest
from src.backtesting.metrics import summarize
from src.features.technical import cci, sma
from src.strategies.e2a_composite import volume_zscore

OUT = Path(__file__).parent / "data"; OUT.mkdir(exist_ok=True)
scfg, dcfg = load_config(); bt = scfg["backtest"]; params = scfg["v3_selection"]["params"]
df = pl.read_parquet(ROOT / dcfg["paths"]["analytics_4h"]).sort("timestamp")
df = build_signals(df, params)
res, summ = {}, {}
for s in ALL:
    r = backtest(df.select(["timestamp","open","high","low","close",f"sig_{s}"]), signal_col=f"sig_{s}",
                 initial_capital=float(bt["initial_capital"]), fee_bps=float(bt["fees"]["taker"])*1e4,
                 slippage_bps=float(bt["slippage"]["bps"]), lag=int(bt["execution"]["lag"]), allow_short=False)
    res[s] = r; m = summarize(r, rf_annual=float(bt["risk_free_annual"]))
    summ[s] = {k: (float(v) if isinstance(v,(int,float)) and v is not None else v) for k,v in m.items()}

# Serie semanal (cierre de semana) de equity y drawdown
eq = pl.DataFrame({"timestamp": df["timestamp"], "close": df["close"],
                   **{f"eq_{s}": res[s]["equity"] for s in ALL},
                   **{f"pos_{s}": res[s]["position"] for s in ALL}})
for s in ALL:
    eq = eq.with_columns((pl.col(f"eq_{s}")/pl.col(f"eq_{s}").cum_max()-1).alias(f"dd_{s}"))
wk = eq.group_by_dynamic("timestamp", every="1w").agg(
    pl.col("close").last(), *[pl.col(f"eq_{s}").last() for s in ALL], *[pl.col(f"dd_{s}").min() for s in ALL])
wk.with_columns(pl.col("timestamp").dt.strftime("%Y-%m-%d")).write_csv(OUT / "weekly.csv")
dly = eq.group_by_dynamic("timestamp", every="1d").agg(pl.col("close").last(),
        *[pl.col(f"pos_{s}").max() for s in ALL])
dly.with_columns(pl.col("timestamp").dt.strftime("%Y-%m-%d")).write_csv(OUT / "daily.csv")

# Operaciones de A2 (entrada 0->1, salida 1->0 sobre la posicion efectiva)
p = res["E2A_A2"].with_columns(pl.col("position").diff().fill_null(0).alias("d"))
ent = p.filter(pl.col("d") == 1)["timestamp"].to_list(); ext = p.filter(pl.col("d") == -1)["timestamp"].to_list()
trades = []
for i, t0 in enumerate(ent):
    t1 = next((x for x in ext if x > t0), None)
    c0 = df.filter(pl.col("timestamp") == t0)["close"][0]
    c1 = df.filter(pl.col("timestamp") == t1)["close"][0] if t1 else None
    trades.append({"entry": str(t0), "exit": str(t1), "entry_px": c0, "exit_px": c1,
                   "ret_gross_%": (c1/c0-1)*100 if c1 else None})
a2 = params["e2a"]
ind = df.select(["timestamp","open","high","low","close","volume"]).with_columns(
    cci(pl.col("high"), pl.col("low"), pl.col("close"), a2["cci_period"]).alias("cci"),
    sma(pl.col("close"), a2["sma_fast"]).alias("sma_f"), sma(pl.col("close"), a2["sma_slow"]).alias("sma_s"),
    volume_zscore(pl.col("volume"), a2["vol_window"]).alias("vz"))
ind = ind.with_columns(res["E2A_A2"]["position"].alias("pos"))
ind.with_columns(pl.col("timestamp").dt.strftime("%Y-%m-%d %H:%M")).write_csv(OUT / "a2_indicators.csv")
json.dump({"summary": summ, "a2_trades": trades, "a2_params": a2, "params": params}, open(OUT/"summary.json","w"), indent=1, default=str)
for s in ALL: print(f"{s:7s} sharpe={summ[s]['sharpe']:.3f} cagr={summ[s]['CAGR_%']:.2f} dd={summ[s]['maxDD_%']:.2f} exp={summ[s]['exposure']:.4f} trades={summ[s]['trades']}")
print("A2 trades:", len(trades)); print(trades[-4:])
