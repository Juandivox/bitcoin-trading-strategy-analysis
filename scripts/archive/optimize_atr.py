import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np
import polars as pl
from scripts.audit_and_run_atr import run_simulation, E2A_PSO, E2A_A2_BEST

df4h = pl.read_parquet(ROOT / "data" / "processed" / "btcusdt_4h.parquet").sort("timestamp")
n_is = int(len(df4h) * 0.70)
df_is = df4h[:n_is]
df_oos = df4h[n_is:]

print("=" * 80)
print("BARRIDO / OPTIMIZACION DE HIPERPARAMETROS DEL ATR (periodo y factor k)")
print("=" * 80)

print("\n>>> 1. Estrategia E2-A A2 (Optuna Base)")
print(f"{'ATR k':<8} | {'ATR Period':<10} | {'Sharpe IS':<10} | {'MaxDD IS':<10} | {'Sharpe OOS':<10} | {'MaxDD OOS':<10} | {'Ret FULL':<10}")
print("-" * 80)

best_a2 = None
best_sh_a2 = -999

for k in [1.5, 2.0, 2.44, 2.5, 3.0, 3.5, 4.0]:
    for period in [14, 21, 28]:
        p = dict(E2A_A2_BEST)
        p["atr_k"] = k
        p["atr_period"] = period
        m_is = run_simulation(df_is, p, stop_mode="fixed_atr")
        m_oos = run_simulation(df_oos, p, stop_mode="fixed_atr")
        m_full = run_simulation(df4h, p, stop_mode="fixed_atr")
        
        if m_is["sharpe"] > best_sh_a2:
            best_sh_a2 = m_is["sharpe"]
            best_a2 = (k, period, m_is, m_oos, m_full)
            
        print(f"k={k:<6.2f} | p={period:<8} | {m_is['sharpe']:<10.3f} | {m_is['maxDD_%']:<10.1f}% | {m_oos['sharpe']:<10.3f} | {m_oos['maxDD_%']:<10.1f}% | {m_full['total_ret_%']:<10.1f}%")

print(f"\n--> MEJOR ATR PARA A2: k={best_a2[0]}, period={best_a2[1]} -> Sharpe IS: {best_a2[2]['sharpe']:.3f}, Sharpe OOS: {best_a2[3]['sharpe']:.3f}, MaxDD FULL: {best_a2[4]['maxDD_%']:.1f}%")

print("\n" + "=" * 80)
print(">>> 2. Estrategia E2-A PSO (Optimizado IA)")
print(f"{'ATR k':<8} | {'ATR Period':<10} | {'Sharpe IS':<10} | {'MaxDD IS':<10} | {'Sharpe OOS':<10} | {'MaxDD OOS':<10} | {'Ret FULL':<10}")
print("-" * 80)

best_pso = None
best_sh_pso = -999

for k in [2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]:
    for period in [10, 14, 21]:
        p = dict(E2A_PSO)
        p["atr_k"] = k
        p["atr_period"] = period
        m_is = run_simulation(df_is, p, stop_mode="fixed_atr")
        m_oos = run_simulation(df_oos, p, stop_mode="fixed_atr")
        m_full = run_simulation(df4h, p, stop_mode="fixed_atr")
        
        if m_is["sharpe"] > best_sh_pso:
            best_sh_pso = m_is["sharpe"]
            best_pso = (k, period, m_is, m_oos, m_full)
            
        print(f"k={k:<6.2f} | p={period:<8} | {m_is['sharpe']:<10.3f} | {m_is['maxDD_%']:<10.1f}% | {m_oos['sharpe']:<10.3f} | {m_oos['maxDD_%']:<10.1f}% | {m_full['total_ret_%']:<10.1f}%")

print(f"\n--> MEJOR ATR PARA PSO: k={best_pso[0]}, period={best_pso[1]} -> Sharpe IS: {best_pso[2]['sharpe']:.3f}, Sharpe OOS: {best_pso[3]['sharpe']:.3f}, MaxDD FULL: {best_pso[4]['maxDD_%']:.1f}%, Ret FULL: {best_pso[4]['total_ret_%']:.1f}%")
