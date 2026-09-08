"""
src/strategies/individuals.py

Etapa 1 — Indicadores aislados (fiel a notebooks/05, celda 10).
Cada indicador se prueba SOLO, sin combinar. Solo LONG (0/1), lag=1 en backtest.

Reglas (long-only):
- RSI: ENTRY cuando RSI cruza arriba oversold -> LONG; EXIT cuando RSI >= exit_level (50) -> FLAT.
- MACD: LONG si MACD cruza arriba Signal; FLAT si cruza abajo.
- MA (SMA/EMA): fast > slow -> LONG, si no FLAT.
- CCI: ENTRY cuando CCI cruza arriba entry -> LONG; EXIT cuando CCI > exit_ -> FLAT.

Best params Exp01 (TPE 80, 4h, docs/experimento_01_resumen.md):
    EXP01_BEST = rsi(27,41,86) macd(30,46,25) sma(7,228) ema(2,190) cci(39,-64,143)
"""
from __future__ import annotations
import polars as pl
from src.features.technical import rsi, macd, cci, sma, ema

# Best params Exp01 — TPE median OOS Sharpe (ver docs/experimento_01_resumen.md)
EXP01_BEST: dict[str, dict] = {
    "rsi": {"period": 27, "oversold": 41, "overbought": 86},
    "macd": {"fast": 30, "slow": 46, "signal": 25},
    "sma": {"fast": 7, "slow": 228},
    "ema": {"fast": 2, "slow": 190},
    "cci": {"period": 39, "entry": -64, "exit_": 143},
}


def signal_rsi_long(
    df: pl.DataFrame,
    period: int = 27,
    oversold: int = 41,
    overbought: int = 86,
    exit_level: int = 50,
) -> pl.DataFrame:
    assert oversold < 50 < overbought
    df = df.sort("timestamp")
    col = f"rsi_{period}"
    if col not in df.columns:
        df = df.with_columns(rsi(pl.col("close"), period))
    df = df.with_columns(
        [
            pl.when((pl.col(col).shift(1) < oversold) & (pl.col(col) > oversold))
            .then(1)
            .when(pl.col(col) >= exit_level)
            .then(0)
            .otherwise(None)
            .alias("_sig")
        ]
    )
    df = df.with_columns(pl.col("_sig").forward_fill().fill_null(0).alias("signal_rsi"))
    return df.drop("_sig")


def signal_macd_long(
    df: pl.DataFrame, fast: int = 30, slow: int = 46, signal: int = 25
) -> pl.DataFrame:
    assert fast < slow
    df = df.sort("timestamp")
    ml, sl, _h = macd(pl.col("close"), fast, slow, signal)
    df = df.with_columns([ml.alias("ml"), sl.alias("sl")])
    df = df.with_columns(
        [
            pl.when((pl.col("ml").shift(1) < pl.col("sl").shift(1)) & (pl.col("ml") > pl.col("sl")))
            .then(1)
            .when((pl.col("ml").shift(1) > pl.col("sl").shift(1)) & (pl.col("ml") < pl.col("sl")))
            .then(0)
            .otherwise(None)
            .alias("_sig")
        ]
    )
    df = df.with_columns(pl.col("_sig").forward_fill().fill_null(0).alias("signal_macd"))
    return df.drop(["ml", "sl", "_sig"])


def signal_ma_long(
    df: pl.DataFrame, fast: int = 7, slow: int = 228, kind: str = "sma"
) -> pl.DataFrame:
    assert fast < slow
    df = df.sort("timestamp")
    if kind == "sma":
        df = df.with_columns(
            [sma(pl.col("close"), fast).alias("_fast"), sma(pl.col("close"), slow).alias("_slow")]
        )
        col = "signal_sma"
    else:
        df = df.with_columns(
            [ema(pl.col("close"), fast).alias("_fast"), ema(pl.col("close"), slow).alias("_slow")]
        )
        col = "signal_ema"
    df = df.with_columns((pl.col("_fast") > pl.col("_slow")).cast(pl.Int8).alias(col))
    df = df.with_columns(pl.col(col).fill_null(0).alias(col))
    return df.drop(["_fast", "_slow"])


def signal_cci_long(
    df: pl.DataFrame, period: int = 39, entry: float = -64, exit_: float = 143
) -> pl.DataFrame:
    assert entry < exit_
    df = df.sort("timestamp")
    col = f"cci_{period}"
    if col not in df.columns:
        df = df.with_columns(cci(pl.col("high"), pl.col("low"), pl.col("close"), period))
    df = df.with_columns(
        [
            pl.when((pl.col(col).shift(1) < entry) & (pl.col(col) > entry))
            .then(1)
            .when(pl.col(col) > exit_)
            .then(0)
            .otherwise(None)
            .alias("_sig")
        ]
    )
    df = df.with_columns(pl.col("_sig").forward_fill().fill_null(0).alias("signal_cci"))
    return df.drop("_sig")
