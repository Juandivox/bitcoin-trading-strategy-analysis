# Anexo metodológico — métricas, tasa libre de riesgo y reproducibilidad

> Documento de una página para acompañar la defensa. Toda la implementación
> vive en `src/backtesting/metrics.py`; el generador de resultados es
> `scripts/run_resultados.py` y su salida es `docs/tesis_resultados_v3/`.

## 1. Serie de datos y temporalidad

- Fuente: Binance Spot, klines de BTC/USDT.
- Serie base: 1 minuto (2017-08-17 → 2026-09-01), usada **solo** para reconstruir.
- Serie de análisis: **4 horas**, 19.800 velas. Es la frecuencia a la que la
  estrategia decide y a la que opera el bot.
- `P = 2.190` velas por año (365 días × 24 h / 4 h).

**Por qué 4H y no 1m.** El Sharpe se anualiza con `√P`, un supuesto que exige
retornos aproximadamente iid. A 1 minuto hay ruido de microestructura y
autocorrelación que violan ese supuesto con más fuerza; además, la posición de
una estrategia 4H solo cambia cada 4 horas, así que medirla sobre retornos de
1 minuto es medir ruido que nunca se opera. Se usa una sola temporalidad para
todo el análisis: un solo `P`, una sola fórmula, sin riesgo de mezclar escalas.

## 2. Rentabilidad

```
r_t        = close_t / close_{t-1} - 1
posición_t = señal_{t-1}                 (lag = 1, sin look-ahead)
bruto_t    = posición_t * r_t
costo_t    = |posición_t - posición_{t-1}| * (fee + slippage)
ret_neto_t = bruto_t - costo_t
equity_t   = 10.000 * Π(1 + ret_neto_t)
```

Costos: 10 pb de fee (taker) + 5 pb de slippage por lado; se cobran solo en la
vela en que cambia la posición. `CAGR = (equity_final/equity_inicial)^(1/años)-1`
con `años = n_velas / P`.

## 3. Ratio de Sharpe

```
Rf_vela  = rf_anual / P
exceso_t = ret_neto_t - Rf_vela
Sharpe   = mean(exceso) / std(exceso, ddof=1) * sqrt(P)
```

- `rf_anual = 0.04` (4,00%).
- `rf_anual` es **obligatorio** en el código: si no se pasa, la función lanza
  error. No existe un `rf = 0` implícito.
- Cuando `Rf` es constante, `std(R - Rf) = std(R)`; por eso da idéntico calcular
  la desviación sobre el exceso o sobre el retorno bruto.
- `P` se deduce del espaciado **mediano** entre timestamps, no se escribe a
  mano. Un guardrail aborta la corrida si `P` no coincide con el timeframe del
  config.

### Elección de la tasa

En **agosto de 2026** (inicio del proyecto) la T-Bill a 3 meses de EE.UU.
promedió **≈ 3,80% anual**, con un rango diario de 3,69%–3,84% (U.S. Treasury,
H.15 *Daily Treasury Bill Rates*; serie DTB3 de FRED).

Se adopta **4,00%** por tres razones:

1. Es un número redondo y fácil de explicar.
2. Es ligeramente **conservador** frente al 3,80% observado: exigir más tasa
   hace más difícil que la estrategia luzca bien.
3. Aplicarlo constante a 2017–2026 es **más exigente** que la realidad, porque
   entre 2020 y 2021 la tasa estuvo cerca de 0%. Si la estrategia sobrevive con
   4% constante, el resultado es robusto.

La tabla `docs/tesis_resultados_v3/tablas/sensibilidad_rf.csv` repite el Sharpe
para `rf = 0%, 3,8%, 4% y 5%`, de modo que el jurado puede ver cuánto depende el
resultado de esta elección.

## 4. Métricas por operación

Una operación va desde la entrada (`0 → 1`) hasta la salida (`1 → 0`),
incluyendo el costo de salida (se cobra en la vela de salida).

- **Win rate:** operaciones ganadoras / total de operaciones.
- **Profit factor:** suma de ganancias / |suma de pérdidas|. Si no hay pérdidas
  se reporta `—`, no infinito.
- **Retorno medio por operación** y **duración media** en velas.

No se reportan métricas por vela para acierto: con ~91% de velas planas en
E2-A, el win rate por vela subestima el desempeño real (53% vs 77% por
operación en el periodo completo).

## 5. Reproducibilidad

```
python scripts/run_resultados.py            # rf del config (4%)
python scripts/run_resultados.py --rf 0.038 # sensibilidad puntual
```

Cada corrida escribe `manifest.json` con: commit de git, hash de
`configs/strategies.yaml`, timeframe, `P`, `rf`, costos, lag, rango de fechas y
número de velas. Los parámetros de E2-A PSO están **congelados** en
`configs/strategies.yaml` (`e2a_pso_frozen`): la v3 no re-optimiza, solo cambia
el reporte.

## 6. Qué no incluye

- Impacto de mercado no lineal ni order book.
- Funding (no aplica a spot).
- Latencia real de ejecución.
- **El stop ATR se eliminó del proyecto.** No se aplicaba en ningún backtest y
  agregaba parámetros muertos; se retiró de la firma de la estrategia, de
  `src/backtesting/stops.py` y de la configuración del bot. E2-A es una señal
  0/1 pura (CCI + SMA + volumen).
