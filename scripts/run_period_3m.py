"""
scripts/run_period_3m.py

Calcula el desempeno de las 9 estrategias en los ultimos 3 meses:
2026-08-09 -> 2026-11-09 (o el ultimo dato disponible).

Descarga los klines diarios que faltan, resamplea a 4H, une con el parquet
de la tesis y corre el mismo motor con los parametros v3.

Salida:
- docs/tesis_resultados_v3/tablas/periodo_3m_2026-08-09_2026-11-09.csv
- docs/tesis_resultados_v3/tablas/periodo_3m_2026-08-09_2026-11-09.json
"""
from __future__ import annotations

import json
import sys
import time
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import polars as pl
import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backtesting.engine import backtest
from src.ingestion.binance import read_kline_zip
from src.processing.resample import resample
from src.strategies.buy_and_hold import signal_buy_and_hold
from src.strategies.e2a_composite import E2A_A1, signal_e2a_long
from src.strategies.e2c_winners import signal_e2c_long
from src.strategies.individuals import (
    signal_cci_long, signal_ma_long, signal_macd_long, signal_rsi_long,
)

UTC = timezone.utc
RAW = ROOT / "data" / "raw" / "spot" / "daily" / "klines" / "BTCUSDT" / "1m"
TABS = ROOT / "docs" / "tesis_resultados_v3" / "tablas"
BASE_4H = ROOT / "data" / "processed" / "btcusdt_4h.parquet"

START = datetime(2026, 8, 9, tzinfo=UTC)
DL_START = date(2026, 9, 2)
DL_END = date(2026, 11, 9)


def ensure_data() -> list[Path]:
    RAW.mkdir(parents=True, exist_ok=True)
    paths = []
    d = DL_START
    while d <= DL_END:
        p = RAW / f"BTCUSDT-1m-{d.isoformat()}.zip"
        if not p.exists() or p.stat().st_size == 0:
            url = (
                "https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/"
                f"BTCUSDT-1m-{d.isoformat()}.zip"
            )
            for attempt in range(3):
                try:
                    r = requests.get(url, timeout=60)
                    r.raise_for_status()
                    p.write_bytes(r.content)
                    with zipfile.ZipFile(p) as z:
                        z.testzip()
                    break
                except Exception as exc:
                    if attempt == 2:
                        raise RuntimeError(f"No se pudo descargar {d}: {exc}")
                    time.sleep(2)
        paths.append(p)
        d += timedelta(days=1)
    return paths


def build_combined() -> pl.DataFrame:
    paths = ensure_data()
    frames = [read_kline_zip(p) for p in paths]
    new_1m = pl.concat(frames).sort("timestamp")
    new_4h = resample(new_1m, "4h")
    old = pl.read_parquet(BASE_4H).sort("timestamp")
    common = [c for c in old.columns if c in new_4h.columns]
    combined = (
        pl.concat([old.select(common), new_4h.select(common)], how="vertical")
        .unique(subset=["timestamp"], keep="last")
        .sort("timestamp")
    )
    return combined


def main() -> None:
    cfg = yaml.safe_load((ROOT / "configs" / "strategies.yaml").read_text(encoding="utf-8"))
    p = cfg["v3_selection"]["params"]

    df = build_combined()
    end = df["timestamp"].max() + timedelta(hours=4)
    print(f"[datos] combinado: {len(df):,} velas | {df['timestamp'].min()} -> {df['timestamp'].max()}")
    print(f"[ventana] {START} -> {end} (exclusivo)")

    df = signal_buy_and_hold(df).rename({"signal_bh": "sig_BH"})
    df = signal_rsi_long(df, **p["rsi"]).rename({"signal_rsi": "sig_RSI"})
    df = signal_macd_long(df, **p["macd"]).rename({"signal_macd": "sig_MACD"})
    df = signal_ma_long(df, kind="sma", **p["sma"]).rename({"signal_sma": "sig_SMA"})
    df = signal_ma_long(df, kind="ema", **p["ema"]).rename({"signal_ema": "sig_EMA"})
    df = signal_cci_long(df, **p["cci"]).rename({"signal_cci": "sig_CCI"})
    df = signal_e2a_long(df, **E2A_A1).rename({"signal_e2a": "sig_E2A_A1"})
    df = signal_e2a_long(df, **p["e2a"]).rename({"signal_e2a": "sig_E2A_A2"})
    df = signal_e2c_long(df).rename({"signal_e2c": "sig_E2C"})

    ALL = ["SMA", "EMA", "MACD", "E2A_A2", "BH", "CCI", "RSI", "E2C", "E2A_A1"]
    rows = []
    for s in ALL:
        bt = backtest(
            df.select(["timestamp", "open", "high", "low", "close", f"sig_{s}"]),
            signal_col=f"sig_{s}", fee_bps=10.0, slippage_bps=5.0, lag=1,
        ).sort("timestamp")

        base = bt.filter(pl.col("timestamp") < START).tail(1)
        period = bt.filter((pl.col("timestamp") >= START) & (pl.col("timestamp") < end))

        if len(base) == 0 or len(period) == 0:
            print(f"[AVISO] {s}: sin datos en la ventana")
            continue

        eq_base = float(base["equity"][0])
        eq_end = float(period["equity"][-1])
        eq_series = np.concatenate([[eq_base], period["equity"].to_numpy()])
        peak = np.maximum.accumulate(eq_series)
        mdd = float(np.min(eq_series / peak - 1) * 100)

        pos_base = int(base["position"][0])
        pos = period["position"].to_numpy()
        pos_series = np.concatenate([[pos_base], pos])
        entries = int(np.sum((pos_series[1:] == 1) & (pos_series[:-1] == 0)))
        exits = int(np.sum((pos_series[1:] == 0) & (pos_series[:-1] == 1)))

        r = period["strategy_ret"].to_numpy()
        r = r[np.isfinite(r)]
        sharpe_ann = 0.0
        if len(r) > 2 and r.std(ddof=1) > 0:
            ex = r - 0.04 / 2190
            sharpe_ann = float(ex.mean() / ex.std(ddof=1) * np.sqrt(2190))

        rows.append({
            "estrategia": s,
            "retorno_%": (eq_end / eq_base - 1) * 100,
            "maxDD_%": mdd,
            "sharpe_anual_ref": sharpe_ann,
            "entradas": entries,
            "salidas": exits,
            "exposicion_%": float(pos.mean() * 100) if len(pos) else 0.0,
            "eq_inicio": eq_base,
            "eq_fin": eq_end,
            "n_velas": len(period),
        })

    out = pl.DataFrame(rows)
    TABS.mkdir(parents=True, exist_ok=True)
    out.write_csv(TABS / "periodo_3m_2026-08-09_2026-11-09.csv")

    meta = {
        "ventana": "2026-08-09 -> ultimo dato",
        "desde": str(START),
        "hasta": str(end),
        "n_velas_4h": int(out["n_velas"].max()) if out.height else 0,
        "rf_annual": 0.04,
        "costos": "10 bps fee + 5 bps slippage",
        "fuente": "Binance Data Vision (klines 1m diarios, resampleados a 4H)",
    }
    (TABS / "periodo_3m_2026-08-09_2026-11-09.json").write_text(
        json.dumps({"meta": meta, "resultados": rows}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\n=== VENTANA {meta['ventana']} ({meta['n_velas_4h']} velas 4H) ===")
    print(f"{'est':7s} {'retorno%':>9s} {'maxDD%':>8s} {'entradas':>8s} {'salidas':>8s} {'expo%':>7s}")
    for row in rows:
        print(f"{row['estrategia']:7s} {row['retorno_%']:>9.2f} {row['maxDD_%']:>8.2f} "
              f"{row['entradas']:>8d} {row['salidas']:>8d} {row['exposicion_%']:>7.1f}")
    print(f"\n[OK] {TABS / 'periodo_3m_2026-08-09_2026-11-09.csv'}")


if __name__ == "__main__":
    main()
