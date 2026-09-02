"""
src/strategies/mean_reversion.py

Reversion a la media: RSI + Bollinger Bands.
"""
from __future__ import annotations
import polars as pl

def signal_mean_reversion(
    df: pl.DataFrame,
    rsi_period: int = 14,
    rsi_oversold: int = 30,
    rsi_overbought: int = 70,
) -> pl.DataFrame:
    df = df.sort("timestamp")
    # Asegurar indicadores existen
    if f"rsi_{rsi_period}" not in df.columns:
        # fallback calculo rapido
        delta = pl.col("close").diff()
        gain = pl.when(delta > 0).then(delta).otherwise(0)
        loss = pl.when(delta < 0).then(-delta).otherwise(0)
        avg_gain = gain.ewm_mean(alpha=1/rsi_period, adjust=False, min_samples=rsi_period)
        avg_loss = loss.ewm_mean(alpha=1/rsi_period, adjust=False, min_samples=rsi_period)
        rs = avg_gain / avg_loss
        df = df.with_columns((100 - (100/(1+rs))).alias(f"rsi_{rsi_period}"))

    rsi_col = f"rsi_{rsi_period}"
    # Necesita Bollinger: bb_lower/bb_upper
    if "bb_lower" not in df.columns:
        df = df.with_columns([
            pl.col("close").rolling_mean(window_size=20, min_samples=20).alias("bb_mid"),
            pl.col("close").rolling_std(window_size=20, min_samples=20).alias("bb_std"),
        ])
        df = df.with_columns([
            (pl.col("bb_mid")+2*pl.col("bb_std")).alias("bb_upper"),
            (pl.col("bb_mid")-2*pl.col("bb_std")).alias("bb_lower"),
        ])
        df = df.drop(["bb_std"])

    df = df.with_columns(
        pl.when((pl.col(rsi_col) < rsi_oversold) & (pl.col("close") < pl.col("bb_lower"))).then(1)
        .when((pl.col(rsi_col) > rsi_overbought) & (pl.col("close") > pl.col("bb_upper"))).then(-1)
        .otherwise(0)
        .alias("signal_mr")
    )
    return df
