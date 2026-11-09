"""
src/strategies/e2a_composite.py

Etapa 2 / E2-A — CCI + SMA + Volumen (fiel a notebooks/06, celdas 6 y 8).
Sistema compuesto long-only (0/1).

Roles:
- SMA = tendencia (sma_fast > sma_slow)
- CCI = momento de entrada (cruza arriba entry)
- Volumen = confirmacion de participacion (volume zscore > thr)

Logica:
- Entrada: tendencia + volumen OK y CCI cruza arriba entry -> 1
- Salida: CCI > exit o SMA rapida < SMA lenta -> 0

El stop ATR se elimino del proyecto (no se aplicaba en ningun backtest y
agregaba parametros muertos). Ver docs/ANEXO_METODOLOGICO.md.

Params:
- A1 (paper, reproduccion): CCI 20/-100/100, SMA 20/50, Vol 20/0.5
- A2 (TPE 150 trials BTC 4h, ganador): CCI 58/-3/186, SMA 18/221, Vol 40/0.58
  Ojo: varios params A2 quedaron cerca del limite del espacio -> candidato a E2-A.2 con rangos expandidos.
"""
from __future__ import annotations
import polars as pl
from src.features.technical import cci, sma

# A1 — params originales del paper (reproduccion academica)
E2A_A1: dict = {
    "cci_period": 20,
    "cci_entry": -100,
    "cci_exit": 100,
    "sma_fast": 20,
    "sma_slow": 50,
    "vol_window": 20,
    "vol_z_thr": 0.5,
}

# A2 — TPE 150 trials sobre BTC 4h (docs/experimento_02_plan.md)
E2A_A2_BEST: dict = {
    "cci_period": 58,
    "cci_entry": -3,
    "cci_exit": 186,
    "sma_fast": 18,
    "sma_slow": 221,
    "vol_window": 40,
    "vol_z_thr": 0.5815632644010449,
}


def volume_zscore(vol: pl.Expr, window: int) -> pl.Expr:
    mu = vol.rolling_mean(window_size=window, min_samples=window)
    sigma = vol.rolling_std(window_size=window, min_samples=window)
    return ((vol - mu) / sigma).alias(f"vol_z_{window}")


def signal_e2a_long(
    df: pl.DataFrame,
    cci_period: int = 20,
    cci_entry: float = -100,
    cci_exit: float = 100,
    sma_fast: int = 20,
    sma_slow: int = 50,
    vol_window: int = 20,
    vol_z_thr: float = 0.5,
) -> pl.DataFrame:
    assert sma_fast < sma_slow
    assert cci_entry < cci_exit
    df = df.sort("timestamp")
    df = df.with_columns(
        [
            cci(pl.col("high"), pl.col("low"), pl.col("close"), cci_period).alias("_cci"),
            sma(pl.col("close"), sma_fast).alias("_sma_f"),
            sma(pl.col("close"), sma_slow).alias("_sma_s"),
            volume_zscore(pl.col("volume"), vol_window).alias("_vz"),
        ]
    )
    df = df.with_columns(
        [((pl.col("_sma_f") > pl.col("_sma_s")) & (pl.col("_vz") > vol_z_thr)).alias("_trend_vol")]
    )
    df = df.with_columns(
        [
            pl.when(
                ((pl.col("_cci").shift(1) < cci_entry) & (pl.col("_cci") > cci_entry))
                & pl.col("_trend_vol")
            )
            .then(1)
            .when((pl.col("_cci") > cci_exit) | (pl.col("_sma_f") < pl.col("_sma_s")))
            .then(0)
            .otherwise(None)
            .alias("_sig")
        ]
    )
    df = df.with_columns(pl.col("_sig").forward_fill().fill_null(0).alias("signal_e2a"))
    return df.drop(["_cci", "_sma_f", "_sma_s", "_vz", "_trend_vol", "_sig"])
