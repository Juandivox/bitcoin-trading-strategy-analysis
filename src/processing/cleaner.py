"""
src/processing/cleaner.py

Limpieza y consolidacion de ZIPs -> Parquet maestro 1m.

Pipeline:
  1) Descubre ZIPs en data/raw/spot/{monthly,daily}/klines/BTCUSDT/1m/
  2) Parsea cada ZIP con src.ingestion.binance.read_kline_zip (normaliza us->ms)
  3) Concatena, ordena por timestamp, deduplica, valida gaps
  4) Deriva campos faltantes + validaciones OHLC
  5) Guarda Parquet particionado en data/processed/btcusdt_1m.parquet
     (y opcionalmente DuckDB-ready)

Uso:
  python -m src.processing.cleaner --raw-dir data/raw --processed data/processed --symbol BTCUSDT --interval 1m
"""
from __future__ import annotations

import argparse
from pathlib import Path
import polars as pl

from src.ingestion.binance import read_kline_zip


def discover_zips(raw_dir: Path, symbol: str = "BTCUSDT", interval: str = "1m") -> list[Path]:
    raw_dir = Path(raw_dir)
    patterns = [
        raw_dir / "spot" / "monthly" / "klines" / symbol / interval / "*.zip",
        raw_dir / "spot" / "daily" / "klines" / symbol / interval / "*.zip",
    ]
    zips: list[Path] = []
    for pat in patterns:
        zips.extend(sorted(pat.parent.glob(pat.name)))
    return sorted(set(zips))


def consolidate(
    raw_dir: str | Path = "data/raw",
    processed_dir: str | Path = "data/processed",
    symbol: str = "BTCUSDT",
    interval: str = "1m",
    output_name: str | None = None,
) -> Path:
    raw_dir = Path(raw_dir)
    processed_dir = Path(processed_dir)
    processed_dir.mkdir(parents=True, exist_ok=True)

    zips = discover_zips(raw_dir, symbol, interval)
    if not zips:
        raise FileNotFoundError(f"No se encontraron ZIPs en {raw_dir}/spot/**/klines/{symbol}/{interval}/  . Ejecuta download.py primero.")

    print(f"[cleaner] {len(zips)} ZIPs encontrados. Parseando...")

    frames: list[pl.DataFrame] = []
    for zp in zips:
        try:
            df = read_kline_zip(zp, add_derived=True)
            # Solo columnas del dataset maestro + timestamp
            frames.append(df)
        except Exception as e:
            print(f"[cleaner][WARN] fallo {zp.name}: {e}")

    if not frames:
        raise RuntimeError("Ningun ZIP pudo ser parseado.")

    df = pl.concat(frames, how="vertical_relaxed")
    # Deduplicar por open_time_ms (o timestamp)
    df = df.unique(subset=["open_time_ms"], keep="last").sort("timestamp")

    # Validaciones OHLC basicas
    # high >= max(open,close,low), low <= min(open,close,high)
    invalid = df.filter(
        (pl.col("high") < pl.col("open")) |
        (pl.col("high") < pl.col("close")) |
        (pl.col("high") < pl.col("low")) |
        (pl.col("low") > pl.col("open")) |
        (pl.col("low") > pl.col("close"))
    )
    if len(invalid) > 0:
        print(f"[cleaner][WARN] {len(invalid)} filas con OHLC inconsistente (se mantienen pero se reportan)")

    # Detectar gaps de 1m (para reporte)
    # diference entre timestamps consecutivos
    df_gaps = df.select([
        pl.col("timestamp"),
        pl.col("timestamp").diff().alias("delta"),
    ])
    gaps = df_gaps.filter(pl.col("delta") > pl.duration(minutes=1))
    if len(gaps) > 0:
        print(f"[cleaner] {len(gaps)} gaps >1m detectados (posibles mantenimientos de Binance)")

    # Seleccionar y ordenar columnas maestras
    keep = [
        "timestamp", "open_time_ms", "close_timestamp",
        "open", "high", "low", "close",
        "volume", "quote_volume", "trade_count",
        "taker_buy_volume", "taker_buy_quote_volume",
        "taker_sell_volume", "taker_sell_quote_volume",
        "buy_ratio", "sell_ratio", "volume_delta",
    ]
    # Añadir columnas si faltan (defensivo)
    for c in keep:
        if c not in df.columns:
            df = df.with_columns(pl.lit(None).alias(c))
    df = df.select(keep).sort("timestamp")

    # Guardar parquet
    out = processed_dir / (output_name or f"{symbol.lower()}_{interval}.parquet")
    df.write_parquet(out, compression="zstd")
    print(f"[cleaner] OK -> {out}  |  filas={len(df):,}  |  rango={df['timestamp'].min()} -> {df['timestamp'].max()}  |  {out.stat().st_size/1e6:.1f} MB")
    if len(gaps) > 0:
        print(f"[cleaner] gaps ejemplo:\n{gaps.head(5)}")
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--raw-dir", default="data/raw")
    p.add_argument("--processed", default="data/processed")
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--interval", default="1m")
    p.add_argument("--output", default=None)
    args = p.parse_args()
    consolidate(args.raw_dir, args.processed, args.symbol, args.interval, args.output)


if __name__ == "__main__":
    main()
