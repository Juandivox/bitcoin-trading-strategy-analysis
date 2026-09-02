"""
src/features/technical.py

Indicadores tecnicos clasicos: RSI, MACD, Bollinger, SMA/EMA.
Implementados con polars (sin talib) para portabilidad.
"""
from __future__ import annotations
import polars as pl

def rsi(close: pl.Expr, period: int = 14) -> pl.Expr:
    delta = close.diff()
    gain = pl.when(delta > 0).then(delta).otherwise(0)
    loss = pl.when(delta < 0).then(-delta).otherwise(0)
    # Wilder smoothing = EMA con alpha=1/period
    avg_gain = gain.ewm_mean(alpha=1/period, adjust=False, min_samples=period)
    avg_loss = loss.ewm_mean(alpha=1/period, adjust=False, min_samples=period)
    rs = avg_gain / avg_loss
    return (100 - (100 / (1 + rs))).alias(f"rsi_{period}")

def macd(close: pl.Expr, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = close.ewm_mean(span=fast, adjust=False, min_samples=slow)
    ema_slow = close.ewm_mean(span=slow, adjust=False, min_samples=slow)
    macd_line = (ema_fast - ema_slow).alias("macd_line")
    signal_line = (ema_fast - ema_slow).ewm_mean(span=signal, adjust=False, min_samples=slow).alias("macd_signal")
    hist = (macd_line - signal_line).alias("macd_hist")
    return macd_line, signal_line, hist

def add_technical_features(df: pl.DataFrame, rsi_period: int = 14) -> pl.DataFrame:
    df = df.sort("timestamp")
    # SMAs / EMAs
    for w in [20, 50, 60, 200]:
        df = df.with_columns([
            pl.col("close").rolling_mean(window_size=w, min_samples=w).alias(f"sma_{w}"),
            pl.col("close").ewm_mean(span=w, adjust=False, min_samples=w).alias(f"ema_{w}"),
        ])
    # RSI
    df = df.with_columns(rsi(pl.col("close"), rsi_period))
    # MACD
    ml, sl, h = macd(pl.col("close"))
    df = df.with_columns([ml, sl, h])
    # Bollinger 20,2
    df = df.with_columns([
        pl.col("close").rolling_mean(window_size=20, min_samples=20).alias("bb_mid"),
        pl.col("close").rolling_std(window_size=20, min_samples=20).alias("bb_std"),
    ])
    df = df.with_columns([
        (pl.col("bb_mid") + 2*pl.col("bb_std")).alias("bb_upper"),
        (pl.col("bb_mid") - 2*pl.col("bb_std")).alias("bb_lower"),
        ((pl.col("close") - pl.col("bb_mid")) / (2*pl.col("bb_std"))).alias("bb_pct"),
    ])
    df = df.drop(["bb_std"])
    # SMA crossover signal prep
    df = df.with_columns([
        (pl.col("sma_20") - pl.col("sma_60")).alias("sma_diff_20_60"),
    ])
    return df
