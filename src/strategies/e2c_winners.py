"""
src/strategies/e2c_winners.py

Etapa 2 / E2-C — SMA + RSI + MACD con roles (fiel a notebooks/06, celda 20).
Combina las ganadoras de Etapa 1. Long-only (0/1).

Roles (sin redundancia SMA+EMA):
- SMA = regimen de tendencia (sma_fast > sma_slow -> solo LONG permitido, si no FLAT)
- MACD = trigger de momentum (cruce arriba de Signal)
- RSI = filtro de sobreextension (rsi < overbought)

Logica:
- Entrada: regimen & macd_up & rsi_ok -> 1
- Salida: sin regimen o MACD cruza abajo o rsi >= overbought -> 0
"""
from __future__ import annotations
import polars as pl
from src.features.technical import rsi, macd, sma


def signal_e2c_long(
    df: pl.DataFrame,
    sma_fast: int = 20,
    sma_slow: int = 150,
    rsi_period: int = 14,
    rsi_ob: float = 70,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_sig: int = 9,
) -> pl.DataFrame:
    assert sma_fast < sma_slow
    assert macd_fast < macd_slow
    df = df.sort("timestamp")
    df = df.with_columns(
        [
            sma(pl.col("close"), sma_fast).alias("_sma_f"),
            sma(pl.col("close"), sma_slow).alias("_sma_s"),
            rsi(pl.col("close"), rsi_period).alias("_rsi"),
        ]
    )
    ml, sl, _h = macd(pl.col("close"), macd_fast, macd_slow, macd_sig)
    df = df.with_columns([ml.alias("_ml"), sl.alias("_sl")])
    df = df.with_columns(
        [
            ((pl.col("_sma_f") > pl.col("_sma_s"))).alias("_regime"),
            ((pl.col("_ml").shift(1) < pl.col("_sl").shift(1)) & (pl.col("_ml") > pl.col("_sl"))).alias(
                "_macd_up"
            ),
            (pl.col("_rsi") < rsi_ob).alias("_rsi_ok"),
        ]
    )
    df = df.with_columns(
        [
            pl.when(pl.col("_regime") & pl.col("_macd_up") & pl.col("_rsi_ok"))
            .then(1)
            .when(
                (~pl.col("_regime"))
                | (
                    (pl.col("_ml").shift(1) > pl.col("_sl").shift(1))
                    & (pl.col("_ml") < pl.col("_sl"))
                )
                | (pl.col("_rsi") >= rsi_ob)
            )
            .then(0)
            .otherwise(None)
            .alias("_sig")
        ]
    )
    df = df.with_columns(pl.col("_sig").forward_fill().fill_null(0).alias("signal_e2c"))
    return df.drop(
        ["_sma_f", "_sma_s", "_rsi", "_ml", "_sl", "_regime", "_macd_up", "_rsi_ok", "_sig"]
    )
