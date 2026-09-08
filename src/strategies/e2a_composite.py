"""
src/strategies/e2a_composite.py

Etapa 2 / E2-A — CCI + SMA + Volumen + ATR (fiel a notebooks/06, celdas 6 y 8).
Sistema compuesto long-only (0/1).

Roles:
- SMA = tendencia (sma_fast > sma_slow)
- CCI = momento de entrada (cruza arriba entry)
- Volumen = confirmacion de participacion (volume zscore > thr)
- ATR = riesgo, stop dinamico por volatilidad (se aplica en backtest via src/backtesting/stops.py)

Logica:
- Entrada: tendencia + volumen OK y CCI cruza arriba entry -> 1
- Salida: CCI > exit o SMA rapida < SMA lenta -> 0

Params:
- A1 (paper, reproduccion): CCI 20/-100/100, SMA 20/50, Vol 20/0.5, ATR 14/2.0
- A2 (TPE 150 trials BTC 4h, ganador): CCI 58/-3/186, SMA 18/221, Vol 40/0.58, ATR 28/2.44
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
    "atr_period": 14,
    "atr_k": 2.0,
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
    "atr_period": 28,
    "atr_k": 2.444531512139522,
}


def volume_zscore(vol: pl.Expr, window: int) -> pl.Expr:
    mu = vol.rolling_mean(window_size=window, min_samples=window)
    sigma = vol.rolling_std(window_size=window, min_samples=window)
    return ((vol - mu) / sigma).alias(f"vol_z_{window}")


def atr(high: pl.Expr, low: pl.Expr, close: pl.Expr, period: int) -> pl.Expr:
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pl.max_horizontal(tr1, tr2, tr3)
    return tr.rolling_mean(window_size=period, min_samples=period).alias(f"atr_{period}")


def signal_e2a_long(
    df: pl.DataFrame,
    cci_period: int = 20,
    cci_entry: float = -100,
    cci_exit: float = 100,
    sma_fast: int = 20,
    sma_slow: int = 50,
    vol_window: int = 20,
    vol_z_thr: float = 0.5,
    atr_period: int = 14,
    atr_k: float = 2.0,
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
            atr(pl.col("high"), pl.col("low"), pl.col("close"), atr_period).alias("_atr"),
        ]
    )
    # Nota: la señal es 0/1 sin stop; el stop ATR trailing se aplica en backtest.
    # atr_k viaja en params para que backtest use el mismo (ver src/backtesting/stops.py).
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
    return df.drop(["_cci", "_sma_f", "_sma_s", "_vz", "_atr", "_trend_vol", "_sig"])
