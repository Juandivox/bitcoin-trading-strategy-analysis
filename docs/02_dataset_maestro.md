# Dataset Maestro 1m — Especificación

## Columnas (parquet `btcusdt_1m.parquet`)

### Crudas (del ZIP)
`open_time`, `open`, `high`, `low`, `close`, `volume`, `close_time`, `quote_volume`, `trade_count`, `taker_buy_base_volume`, `taker_buy_quote_volume`

### Limpias / Renombradas
`timestamp` (UTC), `volume` (BTC), `quote_volume` (USDT), `trade_count`, `taker_buy_volume`, `taker_buy_quote_volume`

### Derivadas (cleaner.py)
```
taker_sell_volume       = volume - taker_buy_volume
taker_sell_quote_volume = quote_volume - taker_buy_quote_volume
buy_ratio               = taker_buy_volume / volume
sell_ratio              = taker_sell_volume / volume
volume_delta            = taker_buy_volume - taker_sell_volume
cvd                     = cumsum(volume_delta)   # se recalcula tras resample
```

### Features (features/*.py)
`return_1m/5m/15m/60m/240m`, `log_return_*`, `gap_1m`, `volume_ma_20/60/240`, `volume_zscore`, `trade_count_ma_*`, `avg_trade_size`, `imbalance`, `delta_sum_20/60/240`, `cvd_ma_*`, `cvd_dev_*`, `realized_vol_60/240`, `atr_14`, `vwap_60`, `vwap_dist_60`, `sma_20/50/60/200`, `ema_*`, `rsi_14`, `macd_line/signal/hist`, `bb_upper/lower/mid/pct`

### Target (solo training)
`target_return_60m = close.shift(-60)/close -1`

## Validaciones en cleaner.py

- Deduplicación por `open_time_ms`
- OHLC: `high >= max(open,close,low)`, `low <= min(open,close,high)` (reporta, no elimina)
- Gaps >1m: reporta (mantenimientos Binance, no se imputa)
- Orden por `timestamp` UTC
- Normalización us->ms

## Resampleo

Ver `src/processing/resample.py`: OHLC correcto (first/max/min/last), volúmenes sumados, ratios recalculados, cvd recumsum.

## Ejemplo Polars + DuckDB

```python
import polars as pl, duckdb
df = pl.read_parquet("data/processed/btcusdt_1m.parquet")
# DuckDB sin cargar todo
con = duckdb.connect()
con.execute("SELECT date_trunc('month', timestamp) as m, avg(volume) FROM 'data/processed/btcusdt_1m.parquet' GROUP BY 1 ORDER BY 1")
```
