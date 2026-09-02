"""
src/features/volatility.py

Realized volatility, ATR, VWAP.
"""
from __future__ import annotations
import polars as pl
import numpy as np

def add_volatility_features(df: pl.DataFrame, windows: list[int] = [60,240]) -> pl.DataFrame:
    df = df.sort("timestamp")
    # log return 1m
    df = df.with_columns((pl.col("close").log() - pl.col("close").shift(1).log()).alias("_log_ret_1m"))
    for w in windows:
        df = df.with_columns(
            (pl.col("_log_ret_1m").rolling_std(window_size=w, min_samples=w) * (w ** 0.5)).alias(f"realized_vol_{w}")
        )
    # ATR (14 por defecto) - true range
    df = df.with_columns([
        (pl.col("high") - pl.col("low")).alias("_tr1"),
        ((pl.col("high") - pl.col("close").shift(1)).abs()).alias("_tr2"),
        ((pl.col("low") - pl.col("close").shift(1)).abs()).alias("_tr3"),
    ])
    df = df.with_columns(pl.max_horizontal("_tr1","_tr2","_tr3").alias("true_range"))
    df = df.with_columns(pl.col("true_range").rolling_mean(window_size=14, min_samples=14).alias("atr_14"))
    df = df.drop(["_tr1","_tr2","_tr3","_log_ret_1m"])
    return df

def add_vwap(df: pl.DataFrame, window: int = 60) -> pl.DataFrame:
    # VWAP rolling: sum(price*volume)/sum(volume) . Usamos typical price (HLC3)
    df = df.with_columns(((pl.col("high")+pl.col("low")+pl.col("close"))/3).alias("_typical"))
    df = df.with_columns([
        (pl.col("_typical")*pl.col("volume")).rolling_sum(window_size=window, min_samples=window).alias("_pv_sum"),
        pl.col("volume").rolling_sum(window_size=window, min_samples=window).alias("_v_sum"),
    ])
    df = df.with_columns((pl.col("_pv_sum")/pl.col("_v_sum")).alias(f"vwap_{window}"))
    df = df.with_columns((pl.col("close") - pl.col(f"vwap_{window}")).alias(f"vwap_dist_{window}"))
    return df.drop(["_typical","_pv_sum","_v_sum"])
