# Backtesting y Validación Temporal

## Por qué NO random split

En series financieras, `train_test_split(shuffle=True)` mezcla futuro y pasado -> leakage -> Sharpe inflado -> fracaso en vivo.

## Esquemas válidos

### 1) Fixed split (simple)
```
Train: 2018-01-01 -> 2022-12-31
Valid: 2023-01-01 -> 2023-12-31
Test:  2024-01-01 -> 2024-12-31
OOS:   2025-01-01 -> hoy
```

### 2) Walk-forward expanding (recomendado, en configs/data.yaml)
```
Fold 1: Train 2018-2020 -> Test 2021
Fold 2: Train 2018-2021 -> Test 2022
Fold 3: Train 2018-2022 -> Test 2023
Fold 4: Train 2018-2023 -> Test 2024
OOS:    2025-... (nunca tocado hasta decisión final)
```
Cada fold evalúa las estrategias rule-based (trend / mean-reversion) en el año siguiente (expanding window). El OOS 2025-2026 nunca se toca hasta el final.

### 3) Walk-forward rolling (alternativa)
Ventana deslizante de N años (ej. 3 años train -> 1 año test).

## Backtester — qué incluye y qué no

Incluye (obligatorio para ser creíble):
- Fees (0.10% taker) + slippage (5 bps o ATR-based)
- Turnover y costos acumulados
- Lag de ejecución (1 barra)
- Métricas: Sharpe (con tasa libre de riesgo), Calmar, CAGR, max DD, win rate y profit factor por operación, turnover, exposure

No incluye (futuro):
- Order book / market impact no lineal
- Funding (spot no aplica; para futuros sí)
- Latencia real

## Métricas — definiciones canónicas

Todo el análisis se calcula sobre velas de **4H** (19.800 velas, 2017-08-17 → 2026-09-01).
La implementación vive en un único sitio: `src/backtesting/metrics.py`.

### Retorno y equity

```
r_t        = close_t / close_{t-1} - 1
posición_t = señal_{t-lag}          (lag = 1, sin look-ahead)
bruto_t    = posición_t * r_t
costo_t    = |posición_t - posición_{t-1}| * (fee + slippage)
ret_neto_t = bruto_t - costo_t
equity_t   = capital_inicial * Π(1 + ret_neto_t)
```

### Sharpe (con tasa libre de riesgo)

```
Rf_vela  = rf_anual / P
exceso_t = ret_neto_t - Rf_vela
Sharpe   = mean(exceso) / std(exceso, ddof=1) * sqrt(P)
```

- `rf_anual = 0.04` (T-Bill 3M de EE.UU.; ver `docs/ANEXO_METODOLOGICO.md`).
- `P` NO se escribe a mano: se deduce del espaciado **mediano** entre timestamps
  (`periods_per_year`). Así 1m → 525.600 y 4h → 2.190 sin riesgo de mezclar escalas.
- `rf_annual` es obligatorio en la API: no existe un `rf=0` implícito.

| Temporalidad | P (velas/año) |
|---|---:|
| 1 minuto | 525.600 |
| 1 hora | 8.760 |
| **4 horas** | **2.190** |
| 1 día | 365 |

`std(R - Rf) = std(R)` cuando `Rf` es constante; por eso da igual calcular la
desviación sobre el exceso o sobre el retorno bruto.

### Métricas por operación

Una operación va desde la entrada (0→1) hasta la salida (1→0), incluyendo el
costo de salida.

- **Win rate:** operaciones ganadoras / operaciones totales.
- **Profit factor:** suma de ganancias / |suma de pérdidas|. Sin pérdidas → `—`.
- **Retorno medio por operación** y **duración media** (en velas).

### Resto

- **Max DD:** `(equity - cummax(equity))/cummax(equity)` mínimo.
- **Calmar:** `CAGR / |MaxDD|`.
- **CAGR:** `(equity_final/equity_inicial)^(1/años)-1`, con `años = n_velas / P`.
- **Turnover:** `sum(|Δposición|)`.
- **Sortino:** eliminado del proyecto (no se reporta).

## Flujo estrategia -> backtest

```
Señal long-only (etapa 1: RSI/MACD/SMA/EMA/CCI; etapa 2: E2-A / E2-C / BH) -> LONG/FLAT
Backtest:         signal -> position(lag) -> PnL - costos -> métricas
Optimización:     TPE (mediana OOS Sharpe) o NSGA-II (Pareto); params que maximicen Sharpe OOS (no in-sample)
```

Nunca optimizar mirando el test. El test solo se evalúa una vez.
