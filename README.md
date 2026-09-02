# Bitcoin Trading Research — UNAB

Pipeline reproducible para descargar **BTCUSDT Spot 1m completo (2017→hoy)** desde **Binance Data Vision**, construir dataset maestro con order-flow, features, y backtester con costos + validación walk-forward. Para tesis: *Análisis del comportamiento de Bitcoin mediante estrategias de trading (riesgo-rendimiento).*

> **Docs:** `docs/00_pipeline.md` es el documento maestro. Todo está documentado allí.

## Quickstart

```bash
pip install -r requirements.txt

# 1) Descarga histórica (8 workers, verifica SHA256, maneja microsegundos 2025)
python -m src.ingestion.download --symbol BTCUSDT --interval 1m --start 2017-08-17 --workers 8

# 2) Consolidar ZIPs -> Parquet 1m
python -m src.processing.cleaner --raw-dir data/raw --processed data/processed

# 3) (Opcional) Resamplear
python -m src.processing.resample --input data/processed/btcusdt_1m.parquet --timeframes 5m,15m,1h,4h,1d

# 4) Features (también vía notebooks)
python -c "import polars as pl; from src.features import build_features; df=pl.read_parquet('data/processed/btcusdt_1m.parquet'); df=build_features(df); df.write_parquet('data/features/btcusdt_1m_features.parquet'); print(df.shape)"

# 5) Backtest ejemplo
# ver notebooks/04_results.ipynb
```

## Estructura

```
bitcoin-trading-research/
├── data/raw|processed|features
├── notebooks/01_exploration.ipynb ... 04_results.ipynb
├── src/ingestion|processing|features|strategies|models|backtesting|evaluation
├── configs/data.yaml, strategies.yaml
├── docs/00_pipeline.md (+ 01,02,03)
└── requirements.txt
```

## Stack

Polars · NumPy · DuckDB · scikit-learn · XGBoost/LightGBM · matplotlib · Jupyter · (MLflow opcional)

## Notas clave

- **Sin API key.** URLs: `https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/...zip`
- **Microsegundos 2025:** `src/ingestion/binance.py` normaliza `us -> ms` automáticamente.
- **No random split:** walk-forward en `configs/data.yaml` y `src/models/training.py`.
- **Backtester con fees+slippage:** `src/backtesting/engine.py` (lag=1, sin look-ahead).

## Referencias

Binance Data Vision, binance-public-data, Veloso et al. (2025), Omran (2023).
