"""
src/ingestion/binance.py

Utilidades para construir URLs de Binance Data Vision,
parsear klines spot y manejar el cambio de milisegundos -> microsegundos (2025-01-01).

Referencia oficial: https://data.binance.vision  (data/spot/monthly|daily/klines)
Docs: https://github.com/binance/binance-public-data
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import zipfile
from pathlib import Path
from typing import Literal

import polars as pl

# ---------------------------------------------------------------------------
# Constantes y schemas
# ---------------------------------------------------------------------------
BASE_URL = "https://data.binance.vision"

# Schema crudo tal como viene en el CSV dentro del ZIP de klines (sin header).
# 12 columnas: https://binance-docs.github.io/apidocs/spot/en/#kline-candlestick-data
KLINE_COLUMNS = [
    "open_time",              # 0
    "open",                   # 1
    "high",                   # 2
    "low",                    # 3
    "close",                  # 4
    "volume",                 # 5  base asset (BTC)
    "close_time",             # 6
    "quote_volume",           # 7  quote asset (USDT)
    "trade_count",            # 8  number of trades
    "taker_buy_base_volume",  # 9
    "taker_buy_quote_volume", # 10
    "ignore",                 # 11
]

KLINE_DTYPES = {
    "open_time": pl.Int64,
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Float64,
    "close_time": pl.Int64,
    "quote_volume": pl.Float64,
    "trade_count": pl.Int64,
    "taker_buy_base_volume": pl.Float64,
    "taker_buy_quote_volume": pl.Float64,
    "ignore": pl.String,
}

# Cutoff donde Binance cambia a microsegundos para SPOT klines/trades
MICROSECONDS_CUTOFF = dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)
MICROSECONDS_CUTOFF_MS = int(MICROSECONDS_CUTOFF.timestamp() * 1000)
MICROSECONDS_CUTOFF_US = int(MICROSECONDS_CUTOFF.timestamp() * 1_000_000)


# ---------------------------------------------------------------------------
# URL builders
# ---------------------------------------------------------------------------
def build_kline_url(
    symbol: str = "BTCUSDT",
    interval: str = "1m",
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
    market: Literal["spot"] = "spot",
) -> str:
    """
    Construye URL para klines mensuales o diarios.

    Mensual:  https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2024-01.zip
    Diario:   https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2024-01-15.zip
    CHECKSUM: misma URL + .CHECKSUM
    """
    base = f"{BASE_URL}/data/{market}"
    if day is not None:
        assert year is not None and month is not None
        date_str = f"{year:04d}-{month:02d}-{day:02d}"
        return f"{base}/daily/klines/{symbol}/{interval}/{symbol}-{interval}-{date_str}.zip"
    else:
        assert year is not None and month is not None
        date_str = f"{year:04d}-{month:02d}"
        return f"{base}/monthly/klines/{symbol}/{interval}/{symbol}-{interval}-{date_str}.zip"


def build_trades_url(
    symbol: str = "BTCUSDT",
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
    market: Literal["spot"] = "spot",
    kind: Literal["trades", "aggTrades"] = "trades",
) -> str:
    """URLs para trades / aggTrades historicos."""
    base = f"{BASE_URL}/data/{market}"
    if day is not None:
        date_str = f"{year:04d}-{month:02d}-{day:02d}"
        return f"{base}/daily/{kind}/{symbol}/{symbol}-{kind}-{date_str}.zip"
    else:
        date_str = f"{year:04d}-{month:02d}"
        return f"{base}/monthly/{kind}/{symbol}/{symbol}-{kind}-{date_str}.zip"


def checksum_url(zip_url: str) -> str:
    return zip_url + ".CHECKSUM"


# ---------------------------------------------------------------------------
# Timestamp normalizacion (milisegundos vs microsegundos)
# ---------------------------------------------------------------------------

def _is_expr(x) -> bool:
    return isinstance(x, pl.Expr)


def normalize_timestamp_series(s: pl.Series | pl.Expr) -> pl.Series | pl.Expr:
    """
    Normaliza columna de timestamps que puede venir en ms o us.

    Regla robusta (no depende solo de fecha del archivo, por si hay re-procesos):
      - Si valor > 1e14 => microsegundos (us) -> /1000 -> ms
      - Si valor > 1e12 y < 1e14 => milisegundos (ms) -> tal cual

    Acepta tanto pl.Series (para tests / uso directo) como pl.Expr (para with_columns).
    Retorna mismo tipo en milisegundos normalizado.
    """
    # Heuristica: timestamps en us son ~1.7e15, en ms ~1.7e12
    if _is_expr(s):
        # uso dentro de DataFrame.with_columns: pl.col("open_time")
        return (
            pl.when(s > 10_000_000_000_000)  # > 1e13 => claramente microsegundos
            .then(s // 1000)
            .otherwise(s)
        )
    else:
        # s es pl.Series -> normalizacion eager
        # vectorizado sin pl.when (que retorna Expr)
        # usamos list comprehension (rapido para series de tamano moderado en test) o numpy where
        import numpy as np

        arr = s.to_numpy()
        # arr es int64
        normalized = np.where(arr > 10_000_000_000_000, arr // 1000, arr)
        return pl.Series(s.name, normalized, dtype=pl.Int64)


def to_datetime_utc(ms_series: pl.Series | pl.Expr) -> pl.Series | pl.Expr:
    """Convierte serie/expr en ms -> datetime UTC (polars)."""
    ms_norm = normalize_timestamp_series(ms_series)
    if _is_expr(ms_norm):
        return (ms_norm * 1_000_000).cast(pl.Datetime("ns", "UTC"))
    else:
        return (ms_norm * 1_000_000).cast(pl.Datetime("ns", "UTC")).alias(ms_series.name)


# ---------------------------------------------------------------------------
# ZIP / CSV parsing
# ---------------------------------------------------------------------------

def read_kline_zip(
    zip_path: str | Path,
    add_derived: bool = True,
) -> pl.DataFrame:
    """
    Lee un ZIP de klines descargado de Binance y retorna DataFrame normalizado.

    Derivadas (si add_derived=True):
      taker_sell_volume = volume - taker_buy_base_volume
      taker_sell_quote_volume = quote_volume - taker_buy_quote_volume
      buy_ratio  = taker_buy_base_volume / volume
      sell_ratio = 1 - buy_ratio
      volume_delta = taker_buy_base_volume - taker_sell_volume = 2*taker_buy - volume
      timestamp  (UTC) normalizado
    """
    zip_path = Path(zip_path)
    with zipfile.ZipFile(zip_path, "r") as zf:
        # Binance ZIP contiene un unico CSV sin header
        inner = zf.namelist()[0]
        with zf.open(inner) as f:
            raw = f.read()

    df = pl.read_csv(
        io.BytesIO(raw),
        has_header=False,
        new_columns=KLINE_COLUMNS,
        schema_overrides=KLINE_DTYPES,
    )

    # Normalizar timestamps
    df = df.with_columns([
        normalize_timestamp_series(pl.col("open_time")).alias("open_time_ms"),
        normalize_timestamp_series(pl.col("close_time")).alias("close_time_ms"),
    ])
    df = df.with_columns([
        (pl.col("open_time_ms") * 1_000_000).cast(pl.Datetime("ns", "UTC")).alias("timestamp"),
        (pl.col("close_time_ms") * 1_000_000).cast(pl.Datetime("ns", "UTC")).alias("close_timestamp"),
    ])

    if add_derived:
        df = df.with_columns([
            (pl.col("volume") - pl.col("taker_buy_base_volume")).alias("taker_sell_volume"),
            (pl.col("quote_volume") - pl.col("taker_buy_quote_volume")).alias("taker_sell_quote_volume"),
        ])
        df = df.with_columns([
            (pl.col("taker_buy_base_volume") / pl.col("volume")).alias("buy_ratio"),
            ((pl.col("volume") - pl.col("taker_buy_base_volume")) / pl.col("volume")).alias("sell_ratio"),
            (pl.col("taker_buy_base_volume") - pl.col("taker_sell_volume")).alias("volume_delta"),
            # alternativa: (2*col - volume) deberia dar identico
        ])
        # Alias mas cortos esperados por el dataset maestro
        df = df.rename({
            "taker_buy_base_volume": "taker_buy_volume",
            "taker_buy_quote_volume": "taker_buy_quote_volume",
            "volume": "volume",
            "quote_volume": "quote_volume",
            "trade_count": "trade_count",
        })

    return df


def verify_checksum(zip_path: Path, checksum_path: Path | None = None, checksum_text: str | None = None) -> bool:
    """
    Verifica SHA256 del ZIP contra el .CHECKSUM oficial.
    El .CHECKSUM contiene: "<sha256>  <filename>"
    """
    if checksum_text is None:
        assert checksum_path is not None and checksum_path.exists(), "Debe proveer checksum_text o checksum_path existente"
        checksum_text = checksum_path.read_text().strip()
    expected = checksum_text.split()[0].strip().lower()
    sha = hashlib.sha256()
    with open(zip_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192 * 1024), b""):
            sha.update(chunk)
    actual = sha.hexdigest().lower()
    return actual == expected


# ---------------------------------------------------------------------------
# Helpers para trades / aggTrades (para extension futura)
# ---------------------------------------------------------------------------
TRADES_COLUMNS = ["trade_id", "price", "quantity", "quote_quantity", "timestamp", "is_buyer_maker", "is_best_match"]
AGGTRADES_COLUMNS = ["agg_trade_id", "price", "quantity", "first_trade_id", "last_trade_id", "timestamp", "is_buyer_maker", "is_best_match"]


def is_buyer_maker_to_side(is_buyer_maker: bool | int) -> str:
    """
    isBuyerMaker = false -> buyer was taker -> market BUY (agresion compradora)
    isBuyerMaker = true  -> seller was taker -> market SELL
    """
    return "SELL" if bool(is_buyer_maker) else "BUY"
