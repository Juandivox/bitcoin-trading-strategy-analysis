"""Tests para normalizacion de timestamps ms->us."""
import polars as pl
from src.ingestion.binance import normalize_timestamp_series

def test_normalize_milliseconds_untouched():
    s = pl.Series("open_time", [1_700_000_000_000, 1_735_689_600_000])  # ms
    out = normalize_timestamp_series(s)
    assert out.to_list() == [1_700_000_000_000, 1_735_689_600_000]

def test_normalize_microseconds_converted():
    s = pl.Series("open_time", [1_700_000_000_000_000, 1_735_689_600_000_000])  # us
    out = normalize_timestamp_series(s)
    assert out.to_list() == [1_700_000_000_000, 1_735_689_600_000]

def test_url_builder():
    from src.ingestion.binance import build_kline_url
    assert build_kline_url("BTCUSDT","1m",2024,1) == "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2024-01.zip"
    assert build_kline_url("BTCUSDT","1m",2024,1,15) == "https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2024-01-15.zip"
