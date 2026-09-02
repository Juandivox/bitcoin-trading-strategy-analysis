# AGENTS — Guía Operativa Completa (Stack, Arquitectura y Script de Ingestión)

> **Repo:** `E:\bitcoin-trading-research` (`github: Juandivox/bitcoin-trading-strategy-analysis`, branch `main`)
> **Propósito:** Investigación UNAB — análisis de Bitcoin vía estrategias de trading con criterio riesgo-rendimiento, backtesting riguroso y optimización IA.
> Este documento es la **única fuente de verdad para agentes y futuros scripts**: qué stack usar, cómo está organizada la arquitectura, y cómo se pobló `data/` el 2026-09-01/02.

---

## 1. Stack (versiones pinneadas en `requirements.txt:1`)

```
Python 3.10+  (probado en 3.13.2, polars 1.44.1, pyarrow 25.0.1)
│
├── Core ETL / Datos
│   ├── polars>=1.0          # DataFrames columnares, 10-20x más rápido que pandas; lee/escribe Parquet zstd, rolling/window
│   ├── numpy>=1.24          # Operaciones vectoriales, soporte sklearn/xgboost
│   ├── pyarrow>=14          # Backend Parquet para polars.to_pandas()
│   ├── duckdb>=0.10         # SQL sobre Parquet sin cargar en RAM (memory_limit 4GB, threads 4 en configs/data.yaml:87)
│   ├── requests>=2.31       # Descargas HTTP Data Vision
│   ├── tqdm>=4.66           # Barras progreso paralelas
│   └── pyyaml>=6.0          # Carga configs/*.yaml
│
├── Machine Learning
│   ├── scikit-learn>=1.4    # Baseline RF, TimeSeriesSplit, métricas
│   ├── xgboost>=2.0         # Modelo principal (n_estimators 500, lr 0.05)
│   └── lightgbm>=4.0        # Alternativa GBM
│
├── Visualización / Notebooks
│   ├── matplotlib>=3.8      # Equity, drawdown, distribuciones
│   ├── jupyter>=1.0 + ipykernel>=6.0  # notebooks 01..04
│   └── (opcional) mlflow>=2.0, optuna>=3.5  # tracking + optimización hiperparámetros
│
└── Dev
    ├── pytest (implícito vía tests/test_bincance_timestamps.py:1)
    └── git
```

**Instalación:**
```bash
pip install -r requirements.txt
# Si workdir != repo root, exponer paquete:
set PYTHONPATH=E:\bitcoin-trading-research   # PowerShell: $env:PYTHONPATH="E:\bitcoin-trading-research"
```

**Por qué este stack (decisiones):**
- **Polars > Pandas:** 4.7M filas × 17 cols → 418 MB parquet; Polars lee en ~0.8s vs Pandas ~6s; rolling `mean/std/ewm` nativo sin `talib`.
- **Parquet zstd > CSV:** 10x compresión, tipado, particionable, leíble por DuckDB sin RAM.
- **DuckDB:** permite `SELECT ... FROM 'data/processed/btcusdt_1m.parquet' WHERE year=2024` sin `pl.read_parquet` completo.
- **XGBoost/LightGBM > DL inicial:** tabular + <5M filas, mejor baseline, menos overfit que LSTM sin features de order-flow.

---

## 2. Arquitectura Completa

```
E:\bitcoin-trading-research\
│
├── AGENTS.md                          # ← este archivo (guía operativa)
├── README.md                          # Quickstart user-facing
├── .gitignore                         # excluye data/raw/*.zip, *.parquet grandes, __pycache__
├── requirements.txt
│
├── configs/
│   ├── data.yaml                      # Fuente, rango, columnas maestras, validación walk-forward
│   └── strategies.yaml                # Params estrategias, fees/slippage, métricas, optimización
│
├── data/                              # No commitear ZIPs/parquets >100MB (ver .gitignore)
│   ├── raw/                           # ZIPs originales Binance (mensual + diario)
│   │   └── spot/{monthly,daily}/klines/BTCUSDT/1m/BTCUSDT-1m-*.zip
│   ├── processed/                     # Parquet limpios 1m (+ resamples 5m/1h/1d)
│   │   ├── btcusdt_1m.parquet         # 4,747,519 × 17 (417.9 MB) ← dataset maestro
│   │   ├── btcusdt_5m.parquet         # (generado por resample.py si se ejecuta)
│   │   └── btcusdt_1d.parquet
│   └── features/                      # Parquet con features + target
│       └── btcusdt_1m_features.parquet # 4,747,519 × 82 (2.3 GB)
│
├── docs/
│   ├── 00_pipeline.md                 # Documento maestro (leer primero)
│   ├── 01_binance_data_vision.md      # URLs, checksums, publicación, rangos
│   ├── 02_dataset_maestro.md          # Schema parquet, validaciones, ejemplo DuckDB
│   ├── 03_backtesting_y_validacion.md # Por qué no random split, walk-forward, métricas
│   ├── README.md
│   └── Analizar el comportamiento...md # Propuesta tesis (movida de raíz en commit 5f99a2e)
│
├── notebooks/
│   ├── 01_exploration.ipynb           # Valida parquet, gaps, OHLC, volumen
│   ├── 02_volume_analysis.ipynb       # Order-flow, buy_ratio, CVD, imbalance
│   ├── 03_features.ipynb              # Construye features, verifica no leakage
│   └── 04_results.ipynb               # Compara estrategias, backtest con costos
│
├── src/
│   ├── __init__.py
│   │
│   ├── ingestion/                     # ← Fuentes
│   │   ├── binance.py                 # URLs, schemas KLINE_COLUMNS:12, normalize_timestamp_series, read_kline_zip, verify_checksum
│   │   └── download.py                # download_one (HEAD→GET, retry, SHA256) + download_range (mensual+diaria, ThreadPool 8)
│   │
│   ├── processing/                    # ← Limpieza
│   │   ├── cleaner.py                 # discover_zips → concat → dedup open_time_ms → valida OHLC/gaps → Parquet
│   │   └── resample.py                # 1m → 5m/15m/1h/4h/1d (OHLC first/max/min/last, volúmenes sum, recalcula ratios/cvd)
│   │
│   ├── features/                      # ← Ingeniería (sin leakage)
│   │   ├── __init__.py                # build_features(df, horizon=60) → pipeline
│   │   ├── price.py                   # return_1/5/15/60, log_return, gap, target_return_60m (=P_{t+60}/P_t-1)
│   │   ├── volume.py                  # buy_ratio, imbalance, volume_ma/zscore, avg_trade_size
│   │   ├── cvd.py                     # volume_delta, cvd=cumsum(delta), cvd_ma/dev, divergencias
│   │   ├── volatility.py              # realized_vol, true_range, atr_14, vwap
│   │   └── technical.py               # sma/ema, rsi, macd, bbands, sma_diff
│   │
│   ├── strategies/                    # ← Señales {-1,0,1} (sin look-ahead)
│   │   ├── trend_following.py         # SMA crossover (20/60) + filtro ATR
│   │   └── mean_reversion.py          # RSI + Bollinger
│   │
│   ├── models/                        # ← ML separado de estrategia
│   │   ├── training.py                # walk_forward_splits, prepare_xy, train_predict (xgboost/lightgbm/rf), to_trading_signal (threshold)
│   │   └── prediction.py              # save/load pickle, predict()
│   │
│   ├── backtesting/                   # ← Motor aislado
│   │   ├── engine.py                  # backtest(df, lag=1) → position, strategy_ret, equity, bh_equity
│   │   ├── costs.py                   # apply_costs (fixed_bps vs atr_based)
│   │   └── metrics.py                 # sharpe/sortino/calmar/cagr/max_drawdown/win_rate/profit_factor/summarize
│   │
│   └── evaluation/
│       ├── statistics.py              # compare_strategies()
│       └── plots.py                   # plot_equity, plot_drawdown (matplotlib)
│
└── tests/
    ├── __init__.py
    └── test_bincance_timestamps.py    # ms intacto, µs→ms, build_kline_url
```

**Flujo de datos (DAG):**

```
Binance Data Vision (ZIPs)
        ↓  download.py (ThreadPool, SHA256)
data/raw/spot/{monthly,daily}/klines/BTCUSDT/1m/*.zip
        ↓  cleaner.py (read_kline_zip → normalize_timestamp_series → dedup → validate)
data/processed/btcusdt_1m.parquet  (maestro 1m, UTC, order-flow derivado)
        ├─→ resample.py  →  data/processed/btcusdt_{5m,1h,1d}.parquet
        └─→ features/build_features  →  data/features/btcusdt_1m_features.parquet
                                        (82 cols: 65 features + 17 base + target)
                ↓
        ┌───────┴────────┐
   strategies/         models/training.py (walk-forward folds de configs/data.yaml)
   (SMA/RSI)           → prediction → to_trading_signal (threshold ±0.001)
        └───────┬────────┘
         backtesting/engine.py (lag=1, fees 0.10% + slippage 5bps)
                ↓
         evaluation/statistics + plots → notebooks/04_results
```

**Convenciones:**
- `timestamp` siempre `Datetime(ns, UTC)` apertura de vela; `close_timestamp` = `timestamp + interval -1ms`.
- Derivadas order-flow **siempre** recalculadas post-resample: `taker_sell = volume - taker_buy`, `buy_ratio = taker_buy/volume`, `volume_delta = 2*taker_buy - volume`, `cvd = cumsum(delta)`.
- `target_return_60m` nunca entra en `feature_cols` (ver `price.py:add_target`).
- Todo `rolling_*` y `ewm_*` usa `min_samples` para evitar filas con NaN al inicio.

---

## 3. Configuración Central

**`configs/data.yaml:1`** — única fuente de verdad para ingestión:
```yaml
binance: {base_url: https://data.binance.vision, symbol: BTCUSDT, market: spot, interval: 1m, start_date: 2017-08-17}
download: {concurrent_workers: 8, retries: 5, timeout_s: 60, checksum_verify: true}
timestamp: {cutoff_microseconds: 2025-01-01}  # ver §5
paths: {raw_dir: data/raw, processed_dir: data/processed, features_dir: data/features}
validation: {method: walk_forward, folds: [2018-2020→2021, 2018-2021→2022, 2018-2022→2023, 2018-2023→2024], oos: [2025-01-01, null]}
duckdb: {memory_limit: 4GB, threads: 4}
```

**`configs/strategies.yaml:1`** — parámetros reproducibles:
```yaml
strategies: {trend_following: {fast_ma:20, slow_ma:60, atr_period:14, atr_multiplier:1.5}, mean_reversion: {rsi:14/30/70, bb:20/2.0}, ml_threshold: {model: xgboost, target: return_60m, threshold_long:0.001, threshold_short:-0.001}}
backtest: {initial_capital:10000, fees: {maker:0.001, taker:0.001}, slippage: {bps:5, model: fixed_bps}, execution: {lag:1}, position: {allow_short:true}}
metrics: [pnl, equity_curve, cagr, sharpe, sortino, calmar, max_drawdown, win_rate, profit_factor, turnover]
```

Cambiar un parámetro aquí → todos los scripts/notebooks lo leen vía `yaml.safe_load(open("configs/..."))`.

---

## 4. Script de Ingestión Documentado (Ejecución Real 2026-09-01/02)

**Módulos:** `src/ingestion/binance.py:1` + `src/ingestion/download.py:1`

**Comando primario ejecutado:**
```bash
PYTHONPATH=E:\bitcoin-trading-research python -m src.ingestion.download --symbol BTCUSDT --interval 1m --start 2017-08-17 --workers 8
# salida: [download] BTCUSDT 1m  2017-08-17 -> 2026-09-01  |  110 archivos  |  workers=8
# progreso: Descargando: 100%|##########| 110/110 [00:44<00:00, 2.49file/s]
# resultado: downloaded=109 skipped=0 not_found=1 (2026-08 mensual) failed=0
```

**Incidencia `2026-08` mensual 404:** `…/BTCUSDT-1m-2026-08.zip` → `404` (mensuales se publican con días de retraso). La lógica `monthly → daily` solo descargó `2026-09-01`. Fallback manual:
```python
for d in 2026-08-01 .. 2026-08-31:
  download_one(f"https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-{d}.zip",
               Path(f"data/raw/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-{d}.zip"), session)
# 31/31 downloaded
```

**Limpieza/consolidación:**
```bash
python -m src.processing.cleaner --raw-dir data/raw --processed data/processed
# [cleaner] 140 ZIPs encontrados. Parseando...
# [cleaner] 34 gaps >1m detectados
# [cleaner] OK -> data\processed\btcusdt_1m.parquet  |  filas=4,747,519  |  rango=2017-08-17 04:00:00+00:00 -> 2026-09-01 23:59:00+00:00  |  438.2 MB
```

**Features:**
```bash
python -c "from src.features import build_features; import polars as pl; df=pl.read_parquet('data/processed/btcusdt_1m.parquet'); df=build_features(df, horizon=60).write_parquet('data/features/btcusdt_1m_features.parquet')"
# btcusdt_1m_features.parquet: 4,747,519 x 82 (418 MB → 2.3 GB)
```

### Artefactos generados

| Ruta | ZIPs/Filas | Tamaño |
|------|-----------|--------|
| `data/raw/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2017-08.zip … 2026-07.zip` | 108 mensuales | ~218 MB |
| `data/raw/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2026-08-01.zip … 2026-09-01.zip` | 32 diarios | ~4 MB |
| `data/processed/btcusdt_1m.parquet` | 4,747,519 × 17 | 417.9 MB |
| `data/features/btcusdt_1m_features.parquet` | 4,747,519 × 82 | 2.3 GB |

**Conteo anual:**
```
2017 196544 (desde 2017-08-17 04:00 UTC)
2018 521624 | 2019 523836 | 2020 525788 | 2021 524607 | 2022 525600 | 2023 525520 | 2024 527040 | 2025 525600 | 2026 351360
total 4,747,519 / esperado 4,756,080 → faltantes 8,561 (0.18%, gaps reales Binance, no imputados)
```

---

## 5. Detalle Crítico: Microsegundos 2025-01-01

> Desde `2025-01-01`, SPOT klines/trades vienen en **µs (16 dígitos, `1735689600000000`)**, no ms (13 dígitos). Sin normalización, fechas caen en año 55k.

**Implementación `src/ingestion/binance.py:119`:**
```python
MICROSECONDS_CUTOFF = datetime(2025,1,1, tzinfo=UTC)

def normalize_timestamp_series(s: pl.Series | pl.Expr):
    if isinstance(s, pl.Expr):
        return pl.when(s > 10_000_000_000_000).then(s // 1000).otherwise(s)  # para with_columns
    else:
        arr = s.to_numpy()
        return pl.Series(s.name, np.where(arr > 1e13, arr // 1000, arr), dtype=pl.Int64)  # eager
```
Uso: `df.with_columns(normalize_timestamp_series(pl.col("open_time")).alias("open_time_ms"))` → luego `*1_000_000).cast(Datetime("ns","UTC"))`.

**Testeado:** `tests/test_bincance_timestamps.py:1` + validación post-carga `2025-01-01 00:00:00+00:00 close=93610.93`.

---

## 6. Dataset Maestro — Schema (`docs/02_dataset_maestro.md:1`)

**12 cols crudas del CSV (sin header):** `open_time, open, high, low, close, volume (BTC), close_time, quote_volume (USDT), trade_count, taker_buy_base_volume, taker_buy_quote_volume, ignore`

**17 cols parquet `btcusdt_1m.parquet`:**
`timestamp(UTC), open_time_ms, close_timestamp, open, high, low, close, volume, quote_volume, trade_count, taker_buy_volume, taker_buy_quote_volume, taker_sell_volume (=volume-taker_buy), taker_sell_quote_volume, buy_ratio, sell_ratio, volume_delta (=taker_buy-taker_sell =2*taker_buy-volume)`

**65 features adicionales en `btcusdt_1m_features.parquet`:** `return_1/5/15/60/240, log_return_*, gap_1m, volume_ma_20/60/240, volume_zscore, trade_count_ma, avg_trade_size, imbalance, cvd/cvd_ma_20/60/240/delta_sum, realized_vol_60/240, true_range/atr_14, _typical/vwap_60, sma_20/50/60/200, ema_*, rsi_14, macd_line/signal/hist, bb_mid/upper/lower/pct, sma_diff + target_return_60m`

---

## 7. Validación y Backtesting (`docs/03_backtesting_y_validacion.md:1`)

**Prohibido:** `train_test_split(shuffle=True)` → leakage.

**Walk-forward expanding (configs/data.yaml:77):**
```
Train 2018-2020 → Test 2021
Train 2018-2021 → Test 2022
Train 2018-2022 → Test 2023
Train 2018-2023 → Test 2024
OOS 2025-01-01 → hoy (nunca tocado hasta decisión final)
```
Consumido por `src/models/training.py:train_predict()`.

**Backtester `src/backtesting/engine.py:1`:**
```python
position_t = signal_{t-lag}  # lag=1
_turnover = |position.diff|
_cost = _turnover * (fee_bps + slippage_bps)/10000  # 10bps + 5bps
strategy_ret = position * (close/close.shift(1)-1) - _cost
equity = initial_capital * (1+strategy_ret).cum_prod()
```
Métricas en `src/backtesting/metrics.py:1`: `cagr`, `sharpe/sortino` (P=525600 para 1m crypto 24/7), `max_drawdown`, `calmar`, `win_rate`, `profit_factor`, `turnover`.

**Separación ML:** `FEATURES → TARGET(y_t=P_{t+60}/P_t-1) → TRAIN → PRED(expected_return) → TRADING RULE(>|0.001| → LONG/SHORT) → BACKTEST`.

---

## 8. Instrucciones para Agentes / Futuros Scripts

```bash
# No re-descargar (resume)
python -m src.ingestion.download --start 2017-08-17 --workers 8          # skipped_exists si ZIP existe
python -m src.ingestion.download --start 2017-08-17 --overwrite         # fuerza + re-verifica SHA256

# Incremental al día de hoy
python -m src.ingestion.download --start 2017-08-17
python -m src.processing.cleaner

# Cargar en scripts
import polars as pl
df = pl.read_parquet("data/processed/btcusdt_1m.parquet")                 # 418 MB, rápido
df = pl.read_parquet("data/features/btcusdt_1m_features.parquet")        # 2.3 GB, con target
df = build_features(pl.read_parquet("data/processed/btcusdt_1m.parquet")) # on-the-fly

# DuckDB sin RAM
import duckdb
duckdb.sql("SELECT date_trunc('month', timestamp) as m, avg(volume) FROM 'data/processed/btcusdt_1m.parquet' GROUP BY 1 ORDER BY 1").show()

# Resampleo
python -m src.processing.resample --input data/processed/btcusdt_1m.parquet --timeframes 5m,15m,1h,4h,1d
```

**Reglas de oro:**
1. Todo script debe `import yaml; cfg = yaml.safe_load(open("configs/data.yaml"))` — no hardcodear `symbol/interval`.
2. `PYTHONPATH=E:\bitcoin-trading-research` si `python -m src...` falla con `ModuleNotFoundError: src`.
3. Verificar `timestamp` es `Datetime(ns, UTC)` antes de filtrar (`pl.datetime(2025,1,1, tzinfo=UTC)`, no string).
4. Documentar cada corrida en `docs/` si cambia `start`, `interval` o lógica µs.

---

## 9. Referencias y Docs Internos

- `docs/00_pipeline.md:1` — pipeline maestro y stack resumido
- `docs/01_binance_data_vision.md:1` — URLs, `.CHECKSUM`, publicación mensual/diaria
- `docs/02_dataset_maestro.md:1` — schema, validaciones OHLC/gaps, ejemplo DuckDB
- `docs/03_backtesting_y_validacion.md:1` — walk-forward vs fixed, fórmulas métricas
- Binance Data Vision: https://data.binance.vision
- Binance Public Data: https://github.com/binance/binance-public-data
- Binance Kline docs: https://binance-docs.github.io/apidocs/spot/en/#kline-candlestick-data

---
*AGENTS v2 — 2026-09-02 — cubre stack, arquitectura, configs, ingestión real y reglas. Mantener sincronizado con `requirements.txt`, `configs/*.yaml` y `src/`.*
