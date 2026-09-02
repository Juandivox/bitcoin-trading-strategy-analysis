"""
src/processing/resample.py

Resampleo del dataset maestro 1m a timeframes superiores (5m,15m,1h,4h,1d)
preservando agregaciones correctas de order-flow.

Reglas:
  open  = first
  high  = max
  low   = min
  close = last
  volume, quote_volume, trade_count, taker_buy_* -> sum
  taker_sell_* -> sum (derivado)
  buy_ratio / sell_ratio / volume_delta -> recalculados post-agregacion
  cvd -> recalculado (cumsum de volume_delta resampleado)

Uso:
  python -m src.processing.resample --input data/processed/btcusdt_1m.parquet --timeframes 5m,15m,1h,4h,1d
"""
from __future__ import annotations

import argparse
from pathlib import Path
import polars as pl

TF_MAP = {
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "2h": "2h",
    "4h": "4h",
    "6h": "6h",
    "8h": "8h",
    "12h": "12h",
    "1d": "1d",
}

def resample(df: pl.DataFrame, timeframe: str) -> pl.DataFrame:
    """
    df debe contener: timestamp (datetime UTC), OHLCV, taker_* y estar ordenado.
    """
    assert "timestamp" in df.columns
    # Polars: dynamic group_by
    every = TF_MAP[timeframe]
    out = (
        df.sort("timestamp")
        .group_by_dynamic("timestamp", every=every)
        .agg([
            pl.col("open").first().alias("open"),
            pl.col("high").max().alias("high"),
            pl.col("low").min().alias("low"),
            pl.col("close").last().alias("close"),
            pl.col("volume").sum().alias("volume"),
            pl.col("quote_volume").sum().alias("quote_volume"),
            pl.col("trade_count").sum().alias("trade_count"),
            pl.col("taker_buy_volume").sum().alias("taker_buy_volume"),
            pl.col("taker_buy_quote_volume").sum().alias("taker_buy_quote_volume"),
            pl.col("taker_sell_volume").sum().alias("taker_sell_volume"),
            pl.col("taker_sell_quote_volume").sum().alias("taker_sell_quote_volume"),
        ])
        .sort("timestamp")
        .with_columns([
            (pl.col("taker_buy_volume") / pl.col("volume")).alias("buy_ratio"),
            (pl.col("taker_sell_volume") / pl.col("volume")).alias("sell_ratio"),
            (pl.col("taker_buy_volume") - pl.col("taker_sell_volume")).alias("volume_delta"),
        ])
        .with_columns(
            pl.col("volume_delta").cum_sum().alias("cvd")
        )
    )
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="data/processed/btcusdt_1m.parquet")
    p.add_argument("--output-dir", default="data/processed")
    p.add_argument("--timeframes", default="5m,15m,1h,4h,1d")
    args = p.parse_args()

    inp = Path(args.input)
    df = pl.read_parquet(inp)
    # Asegurar timestamp es datetime
    if df["timestamp"].dtype != pl.Datetime("ns", "UTC"):
        df = df.with_columns(pl.col("timestamp").cast(pl.Datetime("ns", "UTC")))

    for tf in [t.strip() for t in args.timeframes.split(",") if t.strip()]:
        out_df = resample(df, tf)
        out_path = Path(args.output_dir) / f"{inp.stem.replace('_1m','')}_{tf}.parquet"
        out_df.write_parquet(out_path, compression="zstd")
        print(f"[resample] {tf:4s} -> {out_path}  filas={len(out_df):,}")

if __name__ == "__main__":
    main()
