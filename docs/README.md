# docs/

Documentación del pipeline:

- `00_pipeline.md` — documento maestro (leer primero)
- `01_binance_data_vision.md` — URLs, intervalos, checksums, publicación
- `02_dataset_maestro.md` — especificación de columnas y validaciones
- `03_backtesting_y_validacion.md` — walk-forward, métricas, separación ML/estrategia
- `ANEXO_METODOLOGICO.md` — fórmula canónica del Sharpe, tasa libre de riesgo y reproducibilidad
- `tesis_resultados_v3/` — resultados canónicos (4H, rf=4%) generados por `scripts/run_resultados.py`
  - `CAPITULO_RESULTADOS_v3.md` — capítulo de resultados vigente (PDF: `scripts/md_to_pdf_v3.py`)
- `tesis_resultados/` y `tesis_resultados_v2/` — snapshots históricos (rf=0, Sortino, métricas por vela).
  **No se regeneran**: la fuente vigente es v3.

Todo el código referencia estos docs en comentarios (`src/ingestion/binance.py:1`, etc.).
