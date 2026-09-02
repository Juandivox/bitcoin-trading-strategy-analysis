# docs/

Documentación del pipeline:

- `00_pipeline.md` — documento maestro (leer primero)
- `01_binance_data_vision.md` — URLs, intervalos, checksums, publicación
- `02_dataset_maestro.md` — especificación de columnas y validaciones
- `03_backtesting_y_validacion.md` — walk-forward, métricas, separación ML/estrategia

Todo el código referencia estos docs en comentarios (`src/ingestion/binance.py:1`, etc.).
