"""
scripts/run_hypothesis_tests.py

Prueba de hipotesis para SMA vs E2-A A2 vs Buy & Hold.

Metodologia:
1. Retornos diarios (compuestos desde 4H) para reducir ruido de microestructura.
2. Test de Jobson-Korkie (1981) con correccion de Memmel (2003) para la
   diferencia de dos Sharpe pareados.
3. Bootstrap de bloques moviles (20 dias, 5.000 remuestras) para la diferencia
   de Sharpe, con intervalo de confianza al 95%.
4. Correccion de Holm para las 3 comparaciones pareadas.
5. Test t pareado sobre retornos diarios (secundario, no ajustado por riesgo).

Salida: docs/tesis_resultados_v3/tablas/hipotesis.json
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import polars as pl
import yaml
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backtesting.engine import backtest
from src.strategies.buy_and_hold import signal_buy_and_hold
from src.strategies.e2a_composite import signal_e2a_long
from src.strategies.individuals import signal_ma_long

UTC = timezone.utc
RF = 0.04
DAYS = 365.0
BLOCK = 20
BOOT = 5000
SEED = 42
OUT = ROOT / "docs" / "tesis_resultados_v3" / "tablas" / "hipotesis.json"

cfg = yaml.safe_load((ROOT / "configs" / "strategies.yaml").read_text(encoding="utf-8"))
p = cfg["v3_selection"]["params"]
df = pl.read_parquet(ROOT / "data/processed/btcusdt_4h.parquet").sort("timestamp")

df = signal_ma_long(df, kind="sma", **p["sma"]).rename({"signal_sma": "_SMA"})
df = signal_e2a_long(df, **p["e2a"]).rename({"signal_e2a": "_A2"})
df = signal_buy_and_hold(df).rename({"signal_bh": "_BH"})

frames = {}
for name, col in (("SMA", "_SMA"), ("A2", "_A2"), ("BH", "_BH")):
    bt = backtest(
        df.select(["timestamp", "open", "high", "low", "close", col]),
        signal_col=col, fee_bps=10.0, slippage_bps=5.0, lag=1,
    )
    frames[name] = bt.select(["timestamp", "strategy_ret", "equity"]).rename(
        {"strategy_ret": name, "equity": f"eq_{name}"}
    )

# Unir las tres series por timestamp
merged = frames["SMA"]
for name in ("A2", "BH"):
    merged = merged.join(frames[name], on="timestamp", how="inner")
merged = merged.sort("timestamp").with_columns(
    pl.col("timestamp").dt.date().alias("date")
)

# Retornos diarios compuestos
daily = (
    merged.group_by("date")
    .agg([
        (1 + pl.col("SMA").fill_null(0)).product().alias("SMA"),
        (1 + pl.col("A2").fill_null(0)).product().alias("A2"),
        (1 + pl.col("BH").fill_null(0)).product().alias("BH"),
        pl.col("eq_SMA").last().alias("eq_SMA"),
        pl.col("eq_A2").last().alias("eq_A2"),
        pl.col("eq_BH").last().alias("eq_BH"),
    ])
    .sort("date")
    .with_columns([
        (pl.col("SMA") - 1).alias("SMA"),
        (pl.col("A2") - 1).alias("A2"),
        (pl.col("BH") - 1).alias("BH"),
    ])
)


def max_dd(eq: np.ndarray) -> float:
    peak = np.maximum.accumulate(eq)
    return float(np.min(eq / peak - 1))


def desc(r: np.ndarray) -> dict:
    ex = r - RF / DAYS
    return {
        "n": int(len(r)),
        "mean_daily_%": float(r.mean() * 100),
        "std_daily_%": float(r.std(ddof=1) * 100),
        "sharpe": float(ex.mean() / ex.std(ddof=1) * np.sqrt(DAYS)),
        "skew": float(stats.skew(r)),
        "kurtosis": float(stats.kurtosis(r, fisher=True)),
    }


def jk_test(r1: np.ndarray, r2: np.ndarray) -> dict:
    """Jobson-Korkie (1981) con correccion de Memmel (2003)."""
    n = len(r1)
    sr1 = r1.mean() / r1.std(ddof=1)
    sr2 = r2.mean() / r2.std(ddof=1)
    rho = float(np.corrcoef(r1, r2)[0, 1])
    var = (1.0 / n) * (
        2.0 * (1.0 - rho)
        + 0.5 * (sr1**2 + sr2**2 - 2.0 * sr1 * sr2 * rho**2)
    )
    z = float((sr1 - sr2) / np.sqrt(var))
    p = float(2.0 * (1.0 - stats.norm.cdf(abs(z))))
    diff_ann = float((sr1 - sr2) * np.sqrt(DAYS))
    return {
        "sharpe_1": float(sr1 * np.sqrt(DAYS)),
        "sharpe_2": float(sr2 * np.sqrt(DAYS)),
        "diff_ann": diff_ann,
        "corr": rho,
        "z": z,
        "p": p,
    }


def block_bootstrap(r1: np.ndarray, r2: np.ndarray, block: int = BLOCK,
                    B: int = BOOT, seed: int = SEED) -> dict:
    n = len(r1)
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block))
    diffs = np.empty(B)
    chunk = 500
    for start in range(0, B, chunk):
        size = min(chunk, B - start)
        starts = rng.integers(0, n - block + 1, size=(size, n_blocks))
        idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(size, -1)[:, :n]
        x1 = r1[idx]
        x2 = r2[idx]
        sr1 = x1.mean(axis=1) / x1.std(axis=1, ddof=1)
        sr2 = x2.mean(axis=1) / x2.std(axis=1, ddof=1)
        diffs[start:start + size] = sr1 - sr2
    diffs_ann = diffs * np.sqrt(DAYS)
    lo, hi = np.percentile(diffs_ann, [2.5, 97.5])
    p = 2.0 * min(float(np.mean(diffs <= 0)), float(np.mean(diffs >= 0)))
    return {
        "diff_ann": float((r1.mean() / r1.std(ddof=1) - r2.mean() / r2.std(ddof=1)) * np.sqrt(DAYS)),
        "ci95": [float(lo), float(hi)],
        "p": float(min(p, 1.0)),
        "B": B,
        "block": block,
    }


def holm(pvals: list[float]) -> list[float]:
    m = len(pvals)
    order = np.argsort(pvals)
    adj = np.empty(m)
    prev = 0.0
    for rank, idx in enumerate(order):
        val = (m - rank) * pvals[idx]
        val = max(prev, val)
        adj[idx] = min(val, 1.0)
        prev = adj[idx]
    return [float(v) for v in adj]


def paired_t(r1: np.ndarray, r2: np.ndarray) -> dict:
    diff = r1 - r2
    t, p = stats.ttest_rel(r1, r2)
    return {
        "mean_diff_daily_%": float(diff.mean() * 100),
        "t": float(t),
        "p": float(p),
    }


# --------------------------------------------------------------------------- #
# Periodos
# --------------------------------------------------------------------------- #
periods = {
    "FULL": (None, None),
    "HOLDOUT": (datetime(2025, 1, 1, tzinfo=UTC).date(), None),
}

PAIRS = [("SMA", "A2"), ("SMA", "BH"), ("A2", "BH")]
results: dict = {"rf_annual": RF, "frequency": "daily", "periods": {}}

for pname, (d0, d1) in periods.items():
    sub = daily
    if d0 is not None:
        sub = sub.filter(pl.col("date") >= d0)
    if d1 is not None:
        sub = sub.filter(pl.col("date") <= d1)
    sub = sub.drop_nulls(["SMA", "A2", "BH"])

    r = {k: sub[k].to_numpy() for k in ("SMA", "A2", "BH")}
    descs = {k: desc(v) for k, v in r.items()}
    for k in ("SMA", "A2", "BH"):
        eq = sub[f"eq_{k}"].to_numpy()
        descs[k]["maxDD_%"] = max_dd(eq) * 100

    jk = {}
    bs = {}
    tt = {}
    for a, b in PAIRS:
        jk[f"{a}-{b}"] = jk_test(r[a] - RF / DAYS, r[b] - RF / DAYS)
        bs[f"{a}-{b}"] = block_bootstrap(r[a] - RF / DAYS, r[b] - RF / DAYS)
        tt[f"{a}-{b}"] = paired_t(r[a], r[b])

    raw_p = [jk[k]["p"] for k in jk]
    adj_p = holm(raw_p)
    for k, pa in zip(jk.keys(), adj_p):
        jk[k]["p_holm"] = pa

    raw_p_b = [bs[k]["p"] for k in bs]
    adj_p_b = holm(raw_p_b)
    for k, pa in zip(bs.keys(), adj_p_b):
        bs[k]["p_holm"] = pa

    results["periods"][pname] = {
        "n_days": int(len(sub)),
        "from": str(sub["date"][0]),
        "to": str(sub["date"][-1]),
        "descriptives": descs,
        "correlations": {
            "SMA-A2": float(np.corrcoef(r["SMA"], r["A2"])[0, 1]),
            "SMA-BH": float(np.corrcoef(r["SMA"], r["BH"])[0, 1]),
            "A2-BH": float(np.corrcoef(r["A2"], r["BH"])[0, 1]),
        },
        "jk": jk,
        "bootstrap": bs,
        "paired_t": tt,
    }

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

# --------------------------------------------------------------------------- #
# Impresion
# --------------------------------------------------------------------------- #
for pname, res in results["periods"].items():
    print(f"\n===== {pname} ({res['from']} -> {res['to']}, n={res['n_days']} dias) =====")
    print(f"{'est':4s} {'Sharpe':>7s} {'Vol diaria%':>11s} {'MaxDD%':>8s} {'Skew':>7s} {'Kurt':>7s}")
    for k in ("SMA", "A2", "BH"):
        d = res["descriptives"][k]
        print(f"{k:4s} {d['sharpe']:>7.3f} {d['std_daily_%']:>11.3f} {d['maxDD_%']:>8.2f} "
              f"{d['skew']:>7.2f} {d['kurtosis']:>7.2f}")
    print("correlaciones:", {k: round(v, 3) for k, v in res["correlations"].items()})
    print(f"\n{'par':8s} {'dif Sharpe':>10s} {'JK z':>7s} {'JK p':>7s} {'Holm':>7s} {'Boot 95% CI':>22s} {'Boot p':>7s}")
    for a, b in PAIRS:
        key = f"{a}-{b}"
        j = res["jk"][key]
        bt = res["bootstrap"][key]
        print(f"{key:8s} {j['diff_ann']:>10.3f} {j['z']:>7.2f} {j['p']:>7.3f} {j['p_holm']:>7.3f} "
              f"[{bt['ci95'][0]:>8.3f}, {bt['ci95'][1]:>8.3f}] {bt['p']:>7.3f}")
    print("t-test pareado:")
    for a, b in PAIRS:
        key = f"{a}-{b}"
        t = res["paired_t"][key]
        print(f"  {key}: diff media diaria={t['mean_diff_daily_%']:.4f}%  t={t['t']:.2f}  p={t['p']:.3f}")

print(f"\n[OK] {OUT}")
