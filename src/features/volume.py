"""
src/features/volume.py

Features de volumen y order-flow derivados de taker_buy / taker_sell.
"""
from __future__ import annotations
import polars as pl

def add_volume_features(df: pl.DataFrame, windows: list[int] = [20,60,240], zscore_window: int = 60) -> pl.DataFrame:
    df = df.sort("timestamp")
    # buy_ratio, sell_ratio, volume_delta ya vienen de cleaner; recalcular por si resample
    if "buy_ratio" not in df.columns:
        df = df.with_columns([
            (pl.col("taker_buy_volume") / pl.col("volume")).alias("buy_ratio"),
            (pl.col("taker_sell_volume") / pl.col("volume")).alias("sell_ratio"),
            (pl.col("taker_buy_volume") - pl.col("taker_sell_volume")).alias("volume_delta"),
        ])
    df = df.with_columns([
        (pl.col("taker_buy_volume") - pl.col("taker_sell_volume")).alias("volume_delta"),
        ((pl.col("taker_buy_volume") - pl.col("taker_sell_volume")) / pl.col("volume")).alias("imbalance"),
    ])
    # CVD (si no existe)
    if "cvd" not in df.columns:
        df = df.with_columns(pl.col("volume_delta").cum_sum().alias("cvd"))

    for w in windows:
        df = df.with_columns([
            pl.col("volume").rolling_mean(window_size=w, min_samples=w).alias(f"volume_ma_{w}"),
            pl.col("quote_volume").rolling_mean(window_size=w, min_samples=w).alias(f"quote_volume_ma_{w}"),
            (pl.col("volume") / pl.col("volume").rolling_mean(window_size=w, min_samples=w) - 1).alias(f"volume_ratio_{w}"),
            pl.col("trade_count").rolling_mean(window_size=w, min_samples=w).alias(f"trade_count_ma_{w}"),
            (pl.col("volume") / pl.col("trade_count")).alias("avg_trade_size"),  # se sobrescribe pero ok
        ])
    # zscore
    df = df.with_columns([
        ((pl.col("volume") - pl.col("volume").rolling_mean(window_size=zscore_window, min_samples=zscore_window))
         / pl.col("volume").rolling_std(window_size=zscore_window, min_samples=zscore_window)).alias("volume_zscore"),
        pl.col("buy_ratio").rolling_mean(window_size=zscore_window, min_samples=zscore_window).alias("buy_ratio_ma"),
    ])
    # average trade size rolling
    df = df.with_columns([
        (pl.col("volume") / pl.col("trade_count")).alias("avg_trade_size"),
        ((pl.col("volume") / pl.col("trade_count")).rolling_mean(window_size=zscore_window).alias("avg_trade_size_ma")),
    ])
    return df
