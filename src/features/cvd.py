"""
src/features/cvd.py

CVD = Cumulative Volume Delta.
volume_delta = taker_buy - taker_sell = 2*taker_buy - volume
cvd = cumsum(volume_delta)

Incluye CVD pendiente, divergencias y zscore.
"""
from __future__ import annotations
import polars as pl

def add_cvd_features(df: pl.DataFrame, windows: list[int] = [20,60,240]) -> pl.DataFrame:
    df = df.sort("timestamp")
    if "volume_delta" not in df.columns:
        df = df.with_columns((pl.col("taker_buy_volume") - pl.col("taker_sell_volume")).alias("volume_delta"))
    if "cvd" not in df.columns:
        df = df.with_columns(pl.col("volume_delta").cum_sum().alias("cvd"))
    for w in windows:
        df = df.with_columns([
            pl.col("cvd").rolling_mean(window_size=w, min_samples=w).alias(f"cvd_ma_{w}"),
            (pl.col("cvd") - pl.col("cvd").rolling_mean(window_size=w, min_samples=w)).alias(f"cvd_dev_{w}"),
            pl.col("volume_delta").rolling_sum(window_size=w, min_samples=w).alias(f"delta_sum_{w}"),
        ])
    # divergencia simple: price vs cvd direction en ventana corta
    df = df.with_columns([
        (pl.col("close") - pl.col("close").shift(60)).alias("price_chg_60"),
        (pl.col("cvd") - pl.col("cvd").shift(60)).alias("cvd_chg_60"),
    ])
    df = df.with_columns(
        (pl.col("price_chg_60").sign() * pl.col("cvd_chg_60").sign()).alias("cvd_divergence_sign")
    )
    return df
