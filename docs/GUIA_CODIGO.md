# Guía del código — cómo funciona el proyecto

**Documento de apoyo — Trading BTC/USDT 4H**

> Versión simplificada para entender el flujo completo: datos, señales, backtest, métricas, selección de parámetros, resultados y bot. No reemplaza al capítulo de resultados; lo explica por dentro.

---

## 1. La idea en una frase

El proyecto descarga velas de Bitcoin, construye estrategias que solo pueden estar **dentro (1)** o **fuera (0)** del mercado, las prueba sobre datos históricos con costos reales, mide su desempeño ajustado por riesgo y elige los parámetros con un protocolo que evita el autoengaño.

---

## 2. Mapa del repositorio

```text
configs/
  data.yaml          -> fuente de datos, rutas, validacion
  strategies.yaml    -> costos, rf, universo y parametros v3

data/
  raw/               -> ZIP originales de Binance
  processed/
    btcusdt_1m.parquet   -> serie base (4.7M velas)
    btcusdt_4h.parquet   -> serie de analisis (19,800 velas)

src/
  ingestion/         -> descarga desde Binance Data Vision
  processing/        -> limpieza y resampleo 1m -> 4h
  features/          -> indicadores tecnicos (RSI, MACD, SMA, ...)
  strategies/        -> senales 0/1 long-only
  backtesting/       -> motor, costos y metricas
  evaluation/        -> comparacion entre estrategias

scripts/
  run_tpe_v3.py      -> re-seleccion de parametros con TPE
  run_resultados.py  -> tablas, figuras y manifiesto
  run_pso_v3.py      -> anexo: PSO con rf=4%
  md_to_pdf_v3.py    -> capitulo en PDF
  md_to_pdf_guia.py  -> esta guia en PDF

tests/               -> 30 tests de investigacion
bot-demo/            -> ejecutor en Binance Demo (92 tests)
docs/                -> capitulos, anexos y resultados
```

---

## 3. Flujo de datos

```text
Binance Data Vision (ZIP mensuales y diarios, velas de 1 minuto)
        |
        v
src/ingestion/download.py      descarga + checksum SHA256
        |
        v
src/processing/cleaner.py      limpia, deduplica y valida OHLC
        |
        v
data/processed/btcusdt_1m.parquet     4.7 millones de velas
        |
        v
src/processing/resample.py     agrega 1m -> 4h
        |
        v
data/processed/btcusdt_4h.parquet     19,800 velas (serie de analisis)
        |
        v
estrategias (src/strategies)   convierten velas en senales 0/1
        |
        v
backtest (src/backtesting)     posicion, costos y equity
        |
        v
metricas (src/backtesting/metrics.py)   Sharpe, MaxDD, Calmar, por operacion
```

**Por qué 4H y no 1 minuto:** la estrategia decide cada 4 horas y el bot opera cada 4 horas. Medir el Sharpe sobre retornos de 1 minuto de una posición que solo cambia cada 4 horas mide ruido que nunca se opera. Además, con una sola temporalidad hay un solo número de velas por año y no se mezclan escalas.

La serie de 1 minuto se conserva solo como fuente auditable para reconstruir la de 4 horas.

---

## 4. De una estrategia a una señal

### 4.1 Señales 0/1

Todas las estrategias son **long-only**: la señal vale 1 (dentro) o 0 (fuera). No hay posiciones cortas. Cada módulo de `src/strategies/` recibe un DataFrame de velas y devuelve una columna nueva con la señal.

### 4.2 Ejemplo: E2-A

E2-A combina tres condiciones:

```text
SMA rapida > SMA lenta          -> tendencia alcista
CCI cruza arriba de entry       -> momento de entrada
z-score de volumen > umbral     -> participacion confirma
```

Si las tres se cumplen, la señal pasa a 1. Si el CCI supera el nivel de salida o la SMA rápida cae por debajo de la lenta, la señal pasa a 0.

A1 usa los parámetros del paper; A2 usa los parámetros seleccionados con TPE. La arquitectura es la misma; cambian los números.

### 4.3 Las 9 estrategias del universo

| Estrategia | Qué hace |
|---|---|
| Buy & Hold | Siempre dentro; benchmark |
| RSI | Compra cuando el RSI cruza hacia arriba el nivel de sobreventa; sale en 50 |
| MACD | Compra cuando el MACD cruza arriba de su señal; sale en el cruce contrario |
| SMA | Dentro si la SMA rápida supera a la lenta |
| EMA | Igual que SMA, con medias exponenciales |
| CCI | Compra cuando el CCI cruza hacia arriba el nivel de entrada; sale arriba del nivel de salida |
| E2-A A1 | CCI + SMA + volumen, parámetros del paper |
| E2-A A2 | Misma arquitectura, parámetros TPE |
| E2-C | SMA régimen + MACD gatillo + RSI filtro, parámetros fijos |

---

## 5. El motor de backtest

El motor está en `src/backtesting/engine.py` y tiene seis pasos:

```text
r_t        = close_t / close_{t-1} - 1
posicion_t = senal_{t-1}                  (lag = 1)
bruto_t    = posicion_t * r_t
costo_t    = |posicion_t - posicion_{t-1}| * (fee + slippage)
ret_neto_t = bruto_t - costo_t
equity_t   = 10,000 * producto(1 + ret_neto_t)
```

**El lag = 1 es clave:** la posición de hoy usa la señal de ayer. Si se usara la señal de hoy, se estaría operando con información del futuro (look-ahead) y los resultados serían falsos.

**Los costos** son 10 pb de fee taker más 5 pb de slippage por lado (15 pb). Se cobran solo en la vela en que cambia la posición: al entrar y al salir.

**El equity** se compone vela a vela: 10.000 USDT iniciales multiplicados por el producto de todos los retornos netos.

---

## 6. Las métricas

### 6.1 Sharpe con tasa libre de riesgo

```text
rf_vela  = rf_anual / P
exceso_t = ret_neto_t - rf_vela
Sharpe   = media(exceso) / desviacion(exceso) * sqrt(P)
```

- `rf_anual = 0.04` (4%).
- `P = 2,190` velas por año para 4H.
- `P` se deduce del espaciado mediano entre timestamps; no se escribe a mano.
- La tasa es obligatoria en el código: no existe un `rf = 0` implícito.

### 6.2 Métricas por operación

Una operación va desde la entrada (0 a 1) hasta la salida (1 a 0), incluyendo el costo de salida.

- **Win rate:** operaciones ganadoras / total.
- **Profit factor:** suma de ganancias / valor absoluto de las pérdidas.
- **Retorno medio** y **duración media** por operación.

No se usan métricas por vela para acierto: con cerca del 91% de velas planas en E2-A, el win rate por vela subestima el desempeño.

### 6.3 Otras

- **MaxDD:** peor caída desde un máximo de equity.
- **Calmar:** CAGR / |MaxDD|.
- **CAGR:** crecimiento anual compuesto.
- **Exposición:** fracción del tiempo dentro del mercado.

---

## 7. Cómo se eligen los parámetros

### 7.1 TPE

TPE es un optimizador bayesiano. Construye dos densidades de probabilidad sobre el espacio de parámetros: una con los trials buenos y otra con los malos. El siguiente punto que prueba es el que maximiza la razón entre ambas. En palabras: busca donde hay alta densidad de buenos resultados y baja de malos.

Se usa porque maneja espacios mixtos (enteros y flotantes con rangos distintos) y es eficiente con pocos trials.

### 7.2 Folds y holdout

```text
2017 ---------- 2020 | 2021 | 2022 | 2023 | 2024 | 2025 -------- 2026
     entrenamiento   test   test   test   test      HOLDOUT
                     \______ folds de validacion ____/
```

- En cada fold, el candidato se evalúa en un año que no usó para calibrar ese fold.
- El objetivo es la **mediana** de los cuatro Sharpes OOS, con rf = 4%.
- El **holdout 2025-2026** no participa de la selección: es el test final.

Se usa mediana y no promedio para que un solo año excepcional no domine la selección.

### 7.3 Regla de validez

Un fold es válido si tiene exposición mayor o igual a 0.5%, al menos 5 operaciones, no pierde con profit factor menor a 1 y su drawdown no supera el 50%. Si es inválido, puntúa -5.0.

### 7.4 Resultado de la re-selección

- **E2-A A2 no cambió:** el TPE con rf = 4% devolvió exactamente los mismos parámetros.
- **SMA, EMA, MACD y CCI mejoraron** su holdout.
- **RSI empeoró:** mejoró los folds pero su holdout cayó.

---

## 8. Cómo se generan los resultados

```text
python scripts/run_tpe_v3.py
        -> docs/tesis_resultados_v3/tablas/tpe_v3.json
        -> parametros seleccionados (se copian a configs/strategies.yaml)

python scripts/run_resultados.py
        -> 11 CSV + 6 figuras + RESUMEN.md + manifest.json

python scripts/md_to_pdf_v3.py
        -> C:\Users\jugev\Desktop\CAPITULO_RESULTADOS_V3_BTC_Trading.pdf
```

El `manifest.json` guarda el commit de git, el hash de la configuración, el timeframe, el número de velas, la rf, los costos, el lag y el protocolo de selección. Es la trazabilidad de la corrida.

---

## 9. El bot

`bot-demo/` es un ejecutor en **Binance Demo** (no producción). Usa NautilusTrader para datos y señales, y un ejecutor REST propio para las órdenes, porque Binance Demo rechaza claves HMAC en su WebSocket privado.

- Estrategia por defecto: variante PSO.
- La tesis recomienda A2; el cambio de variante queda pendiente.
- `bot-demo/.env` no se versiona (credenciales).
- `bot-demo/runs/` y `runs-docker/` no se versionan (estado de ejecución).
- Tests: 92 (1 skipped).

---

## 10. Cómo correr todo

```text
# Investigacion
python scripts/run_tpe_v3.py          # re-seleccion (minutos)
python scripts/run_resultados.py      # tablas y figuras
python scripts/md_to_pdf_v3.py        # capitulo en PDF

# Tests de investigacion
python -m pytest tests/

# Tests del bot (con su propio entorno)
bot-demo\.venv\Scripts\python.exe -m pytest bot-demo\tests
```

---

## 11. Dónde tocar cada cosa

| Quiero cambiar... | Archivo |
|---|---|
| Tasa libre de riesgo o timeframe | `configs/strategies.yaml` |
| Costos, lag o capital inicial | `configs/strategies.yaml` |
| Parámetros seleccionados de las 9 estrategias | `configs/strategies.yaml` (`v3_selection`) |
| La lógica de una señal | `src/strategies/*.py` |
| El motor de backtest | `src/backtesting/engine.py` |
| Las métricas | `src/backtesting/metrics.py` |
| El protocolo de selección | `scripts/run_tpe_v3.py` |
| Las tablas y figuras | `scripts/run_resultados.py` |
| El capítulo | `docs/tesis_resultados_v3/CAPITULO_RESULTADOS_v3.md` |
| El bot | `bot-demo/app/` |

---

## 12. Glosario

| Término | Significado |
|---|---|
| IS | In-sample: datos usados para elegir parámetros |
| OOS | Out-of-sample: datos no usados para esa elección |
| Fold | Una ventana de entrenamiento y su año de test |
| Holdout | Bloque final que no participa de ninguna selección |
| Sharpe | Retorno en exceso por unidad de volatilidad |
| MaxDD | Peor caída desde un máximo de equity |
| Calmar | CAGR dividido por el MaxDD |
| Profit factor | Ganancias sobre pérdidas |
| Lag | Desplazamiento de la señal para evitar look-ahead |
| rf | Tasa libre de riesgo anual |
| TPE | Optimizador bayesiano basado en densidades |
| PSO | Optimizador de enjambre de partículas |

---

> **Resumen para llevarse:** los datos se construyen una vez, las señales son 0/1, el motor aplica lag y costos, las métricas usan rf = 4%, los parámetros se eligen con TPE sobre folds y se validan en un holdout, y los resultados se generan con un solo script reproducible.
