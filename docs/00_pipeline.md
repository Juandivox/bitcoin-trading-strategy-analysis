# Pipeline Bitcoin Trading Research — Documentación Maestra

> **Objetivo:** dataset 1m de BTCUSDT Spot (Binance) desde 2017-08-17 hasta hoy, con order-flow, features, backtester con costos y validación temporal correcta (walk-forward, no random split). Para entrenar bots de trading y tesis UNAB.

---

## 1. Arquitectura

```
bitcoin-trading-research/
├── data/
│   ├── raw/          # ZIPs originales de Binance Vision (mensual + diario)
│   ├── processed/    # Parquet maestros 1m,5m,... (cleaned + resampled)
│   └── features/     # Dataset con features + target (listo para ML)
├── notebooks/
│   ├── 01_exploration.ipynb
│   ├── 02_volume_analysis.ipynb
│   ├── 03_features.ipynb
│   └── 04_results.ipynb
├── src/
│   ├── ingestion/    # binance.py, download.py
│   ├── processing/   # cleaner.py, resample.py
│   ├── features/     # price, volume, cvd, volatility, technical
│   ├── strategies/   # trend_following, mean_reversion
│   ├── models/       # training, prediction
│   ├── backtesting/  # engine, costs, metrics
│   └── evaluation/   # statistics, plots
├── configs/
│   ├── data.yaml
│   └── strategies.yaml
├── docs/             # <-- estás aquí
└── tests/
```

---

## 2. Fuente de datos — Binance Data Vision

**Sin API key. Sin rate limit. Gratis. Oficial.**

- **URL base:** `https://data.binance.vision`
- **Endpoint klines:** `data/spot/monthly|daily/klines/BTCUSDT/1m/BTCUSDT-1m-YYYY-MM.zip`
- **Trades/aggTrades:** `data/spot/monthly|daily/trades|aggTrades/BTCUSDT/...` (para CVD real si se desea extender)
- **Checksum:** cada ZIP tiene `.CHECKSUM` (SHA256) verificado por `download.py`
- **Publicación:** mensuales al inicio del mes siguiente, diarios al día siguiente.

### 2.1 Qué contiene cada vela (12 columnas crudas)

| # | Campo | Tipo | Utilidad |
|---|-------|------|----------|
| 0 | `open_time` | int (ms o us) | timestamp apertura |
| 1 | `open` | float | apertura |
| 2 | `high` | float | máximo |
| 3 | `low` | float | mínimo |
| 4 | `close` | float | cierre |
| 5 | `volume` | float | BTC negociados |
| 6 | `close_time` | int | timestamp cierre |
| 7 | `quote_volume` | float | USDT negociados |
| 8 | `trade_count` | int | n° operaciones |
| 9 | `taker_buy_base_volume` | float | BTC comprado agresivamente (taker buy) |
| 10 | `taker_buy_quote_volume` | float | USDT usado en compras agresivas |
| 11 | `ignore` | string | ignorar |

Esto es **mucho más que OHLCV**: permite order-flow sin procesar cada trade.

### 2.2 Derivadas de order-flow (dataset maestro)

```
taker_sell_btc     = volume_btc - taker_buy_btc
taker_sell_usdt    = volume_usdt - taker_buy_usdt
buy_ratio          = taker_buy_btc / volume_btc
sell_ratio         = 1 - buy_ratio
volume_delta       = taker_buy_btc - taker_sell_btc = 2*taker_buy_btc - volume_btc
cvd                = cumsum(volume_delta)   # cumulative volume delta
imbalance          = volume_delta / volume  # [-1, 1]
```

### 2.3 Trades vs klines vs aggTrades (Cuándo usar cada uno)

| Fuente | Granularidad | `isBuyerMaker` | Uso recomendado |
|--------|--------------|----------------|-----------------|
| **Klines 1m** | 1m (derivada) | implícito (taker_buy) | **Dataset inicial** (este repo). Suficiente para la mayoría de bots. |
| **aggTrades** | agrupado | sí | Medio: reconstruir CVD con menos filas que trades. |
| **Trades** | tick | sí (`false`→ market BUY, `true`→ market SELL) | Máxima precisión, pero 10-100x más datos. Para CVD tick-perfect. |

**Recomendación pipeline:** `Klines 1m + aggTrades` antes de ir a trades individuales. Este repo empieza con klines 1m; aggTrades se puede añadir en `src/ingestion/binance.py:build_trades_url`.

---

## 3. Detalle crítico: microsegundos desde 2025-01-01

> ⚠️ **Desde 2025-01-01, los timestamps spot vienen en microsegundos (us), no milisegundos (ms).**

- Antes: `1735689600000` (ms, 13 dígitos)
- Después: `1735689600000000` (us, 16 dígitos)

**Si no se maneja, las fechas caen en año 55.000.**

**Solución en `src/ingestion/binance.py`:**

```python
# Heurística robusta + cutoff
MICROSECONDS_CUTOFF = datetime(2025,1,1, tzinfo=UTC)

def normalize_timestamp_series(s: pl.Series) -> pl.Series:
    return pl.when(s > 10_000_000_000_000).then(s // 1000).otherwise(s)
```

- Convierte todo a **ms normalizado** y luego a `Datetime(ns, UTC)`.
- También se usa fecha del archivo como fallback (`open_time > cutoff => us`).
- Verificado con tests en `tests/test_bincance_timestamps.py`.

---

## 4. Dataset maestro (1m base)

**Parquet:** `data/processed/btcusdt_1m.parquet` (generado por `cleaner.py`)

| Columna | Origen | Descripción |
|---------|--------|-------------|
| `timestamp` | `open_time` normalizado | UTC, apertura de vela |
| `open/high/low/close` | raw | OHLC |
| `volume` | raw | BTC |
| `quote_volume` | raw | USDT |
| `trade_count` | raw | int |
| `taker_buy_volume` | raw | BTC taker buy |
| `taker_buy_quote_volume` | raw | USDT taker buy |
| `taker_sell_volume` | derivado | `volume - taker_buy` |
| `taker_sell_quote_volume` | derivado | `quote_volume - taker_buy_quote` |
| `buy_ratio/sell_ratio` | derivado | proporción |
| `volume_delta` | derivado | `taker_buy - taker_sell` |
| `cvd` | derivado | `cumsum(volume_delta)` |
| `return_1m/5m/15m/60m` | feature | `close/close.shift(n)-1` (price.py) |
| `realized_volatility` | feature | `std(log_ret)*sqrt(n)` |
| `volume_ma/zscore` | feature | media móvil y z-score |
| `imbalance` | feature | `delta/volume` |
| `vwap` | feature | `(HLC3*vol).rolling_sum / vol.sum` |
| `rsi/macd/bb/at r` | feature | technical.py |
| `target_return_60m` | target | `P_{t+60}/P_t -1` (solo training, nunca feature) |

**Resampleo:** `resample.py` agrega correctamente a 5m,15m,1h,4h,1d (sum para volúmenes, first/max/min/last para OHLC, recalcula ratios).

---

## 5. Cómo descargar (reproducible)

### 5.1 Opción rápida (CLI del repo)

```bash
pip install -r requirements.txt

# Descarga completa desde 2017-08-17 hasta hoy (mensual + diario, 8 workers, verifica SHA256)
python -m src.ingestion.download --symbol BTCUSDT --interval 1m --start 2017-08-17 --workers 8

# Solo 2024 en adelante (para prueba rápida)
python -m src.ingestion.download --symbol BTCUSDT --interval 1m --start 2024-01-01 --workers 4
```

Estructura resultante:

```
data/raw/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2017-08.zip
...
data/raw/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2026-08-31.zip
```

### 5.2 Descarga manual (URL directa)

```
https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2024-01.zip
https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2026-08-31.zip
```

Cada ZIP tiene su `.CHECKSUM`: `https://...zip.CHECKSUM`

### 5.3 Script oficial Binance (alternativa)

Binance mantiene `binance-public-data` con `download-kline.py`:

```bash
git clone https://github.com/binance/binance-public-data.git
python binance-public-data/python/download-kline.py -s BTCUSDT -i 1m -startDate 2017-08-17 -endDate 2026-09-01
```

Nuestro `download.py` es equivalente pero con checksum, retries y paralelismo.

---

## 6. Pipeline completo (comandos)

```bash
# 1) Descargar
python -m src.ingestion.download --start 2017-08-17

# 2) Limpiar y consolidar -> Parquet 1m
python -m src.processing.cleaner --raw-dir data/raw --processed data/processed

# 3) Resamplear (opcional)
python -m src.processing.resample --input data/processed/btcusdt_1m.parquet --timeframes 5m,15m,1h,4h,1d

# 4) Features + target (en notebook o script)
python -c "
import polars as pl
from src.features import build_features
df = pl.read_parquet('data/processed/btcusdt_1m.parquet')
df = build_features(df, horizon=60)
df.write_parquet('data/features/btcusdt_1m_features.parquet')
print(df.shape)
"

# 5) Entrenar (walk-forward) y backtest
# ver notebooks/04_results.ipynb y src/models/training.py + src/backtesting/engine.py
```

---

## 7. Validación temporal (NO random split)

> **Random train/test split = leakage temporal. Prohibido en trading.**

### 7.1 Esquema fijo recomendado

```
2018 ────────── 2022 │ TRAIN
2023 ─────────────── │ VALIDATION
2024 ─────────────── │ TEST
2025-2026 ────────── │ OUT OF SAMPLE (OOS)
```

### 7.2 Walk-forward (más defendible académicamente)

```
Train        Test
2018-2020 -> 2021
2018-2021 -> 2022
2018-2022 -> 2023
2018-2023 -> 2024
```

Configurado en `configs/data.yaml:validation.folds` y consumido por `src/models/training.py:train_predict`.

Cada fold entrena con todo el pasado y evalúa en el año siguiente (expanding window). El OOS 2025-2026 nunca se toca hasta el final.

---

## 8. Backtester (separado del modelo)

**Motor:** `src/backtesting/engine.py:backtest`

Recibe:

```
timestamp, signal (-1/0/1), price (close), position (con lag)
```

Calcula:

```
PnL, fees, slippage, turnover, equity curve, drawdown,
Sharpe, Sortino, Calmar, CAGR, win_rate, profit_factor
```

**Costos (críticos):**

- `fee = 0.10%` taker (Binance spot sin BNB) — `configs/strategies.yaml:backtest.fees`
- `slippage = 5 bps` fijo o `atr_based` — sin esto, muchas estrategias parecen rentables y no lo son.

**Ejecución sin look-ahead:**

```python
position_t = signal_{t-lag}   # lag=1 => ejecuta en siguiente vela
ret_t = position_{t-1} * (price_t/price_{t-1} -1) - turnover*cost
```

---

## 9. ML — separación explícita FEATURES → TARGET → TRADING RULE

```
FEATURES        TARGET              TRAINING   PREDICTION   TRADING RULE   BACKTEST
return_1m  ─┐                ┌─> XGBoost ─┐
return_5m   │  y_t=P_{t+60}/P_t-1  │         │ expected=+0.0032
volume_zscore + ─>  y_t  ──> TRAIN ─> PRED ─> threshold ─> LONG/SHORT/FLAT ─> BT
CVD         │                │         │ expected=-0.0015
RSI/MACD   ─┘                └────────┘
```

- **Target:** `y_t = Close_{t+60}/Close_t -1` (retorno 60m futuro)
- **Threshold:** `|expected_return| > 0.001` (0.10%) para filtrar ruido
- **Modelo:** XGBoost / LightGBM / RF (ver `src/models/training.py`)
- La **estrategia** (threshold) está separada del **modelo predictivo** — metodológicamente importante.

---

## 10. Stack

```
Python 3.10+
├── Polars      (ETL veloz, parquet, rolling)
├── NumPy
├── DuckDB      (queries sobre parquet sin cargar todo en RAM)
├── scikit-learn
├── XGBoost / LightGBM
├── matplotlib  (plots equity/drawdown)
├── Jupyter
└── MLflow (opcional, para tracking)
```

Ver `requirements.txt` para versiones pinneadas.

---

## 11. Referencias

- Binance Data Vision: https://data.binance.vision
- Binance Public Data (scripts oficiales): https://github.com/binance/binance-public-data
- Binance API Kline docs: https://binance-docs.github.io/apidocs/spot/en/#kline-candlestick-data
- Veloso et al. (2025) — halving cycles y volatilidad BTC
- Omran (2023) — PSO para optimización BTC

---

## 12. Próximos pasos

- [ ] `python -m src.ingestion.download --start 2017-08-17` (descarga ~8-12 GB en ZIPs, ~2-3 GB parquet)
- [ ] `python -m src.processing.cleaner`
- [ ] Ejecutar `notebooks/01_exploration.ipynb` → validar gaps, OHLC, volumen
- [ ] Añadir `aggTrades` si se quiere CVD tick-perfect (usar `build_trades_url` + `isBuyerMaker`)
- [ ] Definir folds walk-forward definitivos en `configs/data.yaml`
