# Dossier de sustentación — Trading BTC/USDT 4H

**Documento de apoyo para la defensa del trabajo de grado**

**Ingeniería Financiera — UNAB**

**Versión 3 normalizada — 9 de noviembre de 2026**

---

## Cómo leer este documento

Este dossier está escrito para que **cualquier persona pueda entenderlo**, aunque no sepa programar ni haya estudiado finanzas. La estrategia es simple:

- Cada término técnico aparece **en negrita** y se explica la primera vez que se usa.
- Cada sección empieza con una idea en lenguaje simple y después entra en detalle.
- Las fórmulas están, pero siempre acompañadas de una frase que dice qué significan.
- Los números salen de los archivos de resultados, no de memoria.

Si solo tienes cinco minutos, lee el **Resumen en 5 ideas** y el **Glosario**. Si tienes una hora, lee las secciones 1 a 8. Si vas a la defensa, lee también las **Preguntas del profesor** (sección 11).

---

## Resumen en 5 ideas

1. **Qué se hizo:** se probaron nueve estrategias de compra/venta de Bitcoin sobre nueve años de datos, con costos reales, para ver cuál compensa mejor el riesgo.
2. **Cómo se midió:** con el **Sharpe** (retorno por unidad de riesgo) usando una tasa libre de riesgo del 4%, y con métricas por operación (no por vela).
3. **Cómo se eligieron los parámetros:** con **TPE** (un buscador inteligente) sobre cuatro años de validación y un año y medio de prueba final que nunca se tocó.
4. **Qué se encontró:** la **SMA** tiene el mejor Sharpe (1,123) pero un drawdown de −71%; **E2-A A2** tiene un Sharpe menor (0,872) pero un drawdown de −28% y un win rate de 77%.
5. **Qué se recomienda:** **E2-A A2** para un perfil conservador, y **SMA** como alternativa agresiva. No hay un ganador absoluto: hay un trade-off entre retorno y dolor.

---

# 1. La investigación en lenguaje simple

## 1.1 La pregunta

Imagina que tienes 10.000 dólares y quieres invertir en Bitcoin, pero no quieres comprar y esperar sin más. Quieres una **regla** que te diga cuándo estar dentro del mercado y cuándo salir a efectivo.

La pregunta es: **¿cuál de esas reglas ofrece la mejor relación entre lo que gana y lo que hace sufrir?**

## 1.2 Los datos

Se usaron velas de Bitcoin de los últimos nueve años:

- Desde el 17 de agosto de 2017 hasta el 1 de septiembre de 2026.
- En **velas de 4 horas** (explicadas en la sección 2).
- 19.800 velas en total.

Una **vela** es un resumen del precio en un intervalo. En vez de mirar cada segundo, miras bloques de 4 horas: el precio de apertura, el máximo, el mínimo y el cierre.

## 1.3 Las reglas

Cada estrategia es una **regla 0/1**:

- 1 = estoy dentro, comprado en Bitcoin.
- 0 = estoy fuera, en efectivo.

No hay posiciones cortas (no se apuesta a que el precio baje). Es **long-only**: solo se compra o se espera.

## 1.4 La medición

Para comparar reglas se usa el **Sharpe**, que responde a la pregunta: *¿cuánto gano por cada unidad de riesgo que acepto?*

Un Sharpe de 1 significa que el retorno extra sobre la tasa libre de riesgo es igual a la volatilidad. Un Sharpe de 0,5 significa que es la mitad. Un Sharpe de 3 sería excepcional (y sospechoso en una muestra larga).

## 1.5 El resultado

- **SMA:** gana mucho (57% anual) y tiene el mejor Sharpe (1,123), pero puede caer 71% desde un máximo.
- **E2-A A2:** gana menos (17% anual) pero cae solo 28% y acierta el 77% de las operaciones.
- **Las demás:** quedan en el medio o pierden.

## 1.6 La recomendación

Para un inversionista que sufre con las caídas, **A2**. Para uno que tolera caídas profundas y busca retorno, **SMA**.

---

# 2. Conceptos básicos (con analogías)

Esta sección explica todo lo que necesitas para entender el resto. Si ya conoces un término, puedes saltarlo.

## 2.1 Vela (candle)

**Qué es:** un resumen del precio en un intervalo de tiempo.

**Analogía:** es como una foto de 4 horas. En vez de ver la película completa, ves cuatro datos: cómo abrió, hasta dónde subió, hasta dónde bajó y cómo cerró.

**Por qué importa:** las estrategias no miran cada segundo; miran velas. Eso reduce el ruido y hace que la regla sea operable.

## 2.2 Señal 0/1

**Qué es:** una decisión binaria. 1 = dentro del mercado; 0 = fuera.

**Analogía:** es un interruptor de luz. No hay posiciones intermedias: o está encendido o apagado.

**Por qué importa:** simplifica el backtest y evita discutir tamaños de posición.

## 2.3 Long-only

**Qué es:** solo se compra o se espera. No se vende en corto.

**Analogía:** es como tener un billete de Bitcoin en el bolsillo: o lo tienes o tienes efectivo. No puedes ganar cuando el precio baja.

**Por qué importa:** el bot es spot (no futuros), y el mercado de Bitcoin tiene un sesgo alcista de largo plazo. Los cortos habrían cambiado la naturaleza del estudio.

## 2.4 Backtest

**Qué es:** reproducir una estrategia sobre el pasado para ver qué habría pasado.

**Analogía:** es como ver el replay de un partido y preguntar "¿qué habría pasado si este jugador hubiera tirado en el minuto 80?".

**Por qué importa:** es la única forma de comparar reglas sin arriesgar dinero real.

## 2.5 Look-ahead (mirar el futuro)

**Qué es:** usar información que en ese momento no existía.

**Analogía:** es hacer la apuesta del domingo después de leer el periódico del lunes.

**Por qué importa:** si la estrategia usa la señal de la misma vela en que opera, los resultados son falsos. Por eso el proyecto usa **lag = 1**: la posición de hoy usa la señal de ayer.

## 2.6 Costos: fee y slippage

**Qué es:**

- **Fee:** la comisión que cobra el exchange (10 puntos base = 0,10%).
- **Slippage:** la diferencia entre el precio que ves y el que consigues (5 puntos base = 0,05%).

**Analogía:** es como el roce del aire: aunque el coche tenga buen motor, el roce le quita velocidad.

**Por qué importa:** una estrategia que opera mucho puede parecer buena sin costos y perder con ellos. E2-C es el ejemplo: 294 operaciones y ~88% del capital pagado en costos.

## 2.7 Equity

**Qué es:** la curva de dinero. Empieza en 10.000 y va cambiando con cada operación.

**Analogía:** es el saldo de la cuenta, dibujado en el tiempo.

**Por qué importa:** el equity es lo que el inversionista vive; el Sharpe y el drawdown se calculan sobre él.

## 2.8 Drawdown (DD)

**Qué es:** la caída desde el punto más alto de la equity hasta el punto más bajo posterior.

**Analogía:** si tu cuenta llegó a 20.000 y bajó a 14.000, el drawdown es −30%.

**Por qué importa:** es la medida del dolor. Un Sharpe alto con un drawdown de −80% es difícil de aguantar en la vida real.

## 2.9 Volatilidad

**Qué es:** cuánto se mueve la curva, hacia arriba o hacia abajo.

**Analogía:** es la "nerviosidad" de la estrategia. Una curva tranquila tiene baja volatilidad; una que sube y baja mucho, alta.

**Por qué importa:** el Sharpe divide el retorno por la volatilidad. Más volatilidad, con el mismo retorno, baja el Sharpe.

## 2.10 Sharpe

**Qué es:** retorno en exceso por unidad de volatilidad.

```text
Sharpe = (retorno - tasa libre de riesgo) / volatilidad
```

**Analogía:** es como los kilómetros por litro de un coche: cuánto avanzas por unidad de combustible. Aquí, cuánto retorno sacas por unidad de riesgo.

**Cómo se lee:** 0,5 es aceptable; 1 es bueno; 2 es muy bueno; 3 es excepcional o sospechoso.

## 2.11 CAGR

**Qué es:** la tasa anual compuesta de crecimiento.

**Analogía:** si tu cuenta pasó de 10.000 a 41.621 en 9 años, no creció 316% cada año; creció 17,08% anual compuesto. El CAGR es esa tasa constante que produce el mismo resultado final.

**Por qué importa:** permite comparar estrategias de distinta duración.

## 2.12 Win rate, payoff y profit factor

- **Win rate:** porcentaje de operaciones ganadoras.
- **Payoff:** ganancia media dividida por pérdida media.
- **Profit factor (PF):** suma de ganancias dividida por suma de pérdidas.

**Analogía:** el win rate dice **cuántas veces** aciertas; el payoff, **cuánto** ganas cuando aciertas; el PF combina las dos cosas.

**Relación clave:**

```text
PF = Payoff * (Win rate / (1 - Win rate))
```

## 2.13 Exposición

**Qué es:** la fracción del tiempo que estás dentro del mercado.

**Analogía:** es el porcentaje del tiempo que pasas jugando; el resto estás mirando desde la banca.

**Por qué importa:** A2 está dentro solo el 9,3% del tiempo. Eso explica por qué gana menos que SMA, pero también por qué cae menos.

## 2.14 Optimización

**Qué es:** buscar los mejores parámetros de una regla.

**Analogía:** es como ajustar la receta de una torta: cuánta harina, cuánto azúcar, cuánto tiempo de horno. La optimización prueba combinaciones y se queda con la que mejor resultado da.

**Por qué importa:** los parámetros cambian mucho el resultado. A1 y A2 son la misma receta con distintos ingredientes.

## 2.15 Overfitting (sobreajuste)

**Qué es:** cuando la estrategia memoriza el pasado en vez de aprender un patrón que sirva en el futuro.

**Analogía:** es como memorizar las respuestas del examen de práctica. En el examen real, las preguntas cambian y fallas.

**Por qué importa:** es el riesgo principal de la optimización. Por eso se usan folds y un holdout.

## 2.16 IS, OOS y holdout

- **IS (in-sample):** los datos que usas para elegir.
- **OOS (out-of-sample):** los datos que no usaste para elegir.
- **Holdout:** el bloque final que nunca tocas hasta el veredicto.

**Analogía:** estudias con unos ejercicios (IS), haces un simulacro (OOS) y al final presentas el examen real (holdout). Si estudias con el examen real, el resultado no vale.

## 2.17 TPE y PSO

Dos formas de buscar parámetros:

- **TPE:** prueba combinaciones, aprende cuáles son buenas y malas, y se concentra en las buenas. Es como un chef que prueba y ajusta la receta.
- **PSO:** un grupo de "partículas" busca en el espacio y comparte la mejor posición encontrada. Es como una bandada de pájaros que busca comida.

**Por qué importa:** TPE es más eficiente con pocos intentos; PSO es más simple pero puede estancarse. En esta tesis se usa TPE para la selección oficial.

## 2.18 Tasa libre de riesgo (rf)

**Qué es:** lo que podrías ganar sin riesgo, por ejemplo comprando una letra del Tesoro de EE.UU.

**Analogía:** es el "suelo" de rentabilidad. Si tu estrategia no supera ese suelo, no vale la pena el riesgo.

**Por qué importa:** el Sharpe resta la rf. Con rf=4%, una estrategia tiene que ganar más que eso para aportar valor ajustado por riesgo.

---

# 3. Historia y origen de las estrategias

## 3.1 Las dos etapas

- **Etapa 1:** probar indicadores aislados (RSI, MACD, SMA, EMA, CCI) para ver cuáles sobreviven solos.
- **Etapa 2:** construir sistemas compuestos combinando esos indicadores.

Los nombres vienen de ahí: **E2** significa Etapa 2. La letra distingue la familia:

- **E2-A:** CCI + SMA + volumen.
- **E2-B:** machine learning (XGBoost, Random Forest, LightGBM), descartada.
- **E2-C:** SMA + MACD + RSI.

## 3.2 E2-A: la familia principal

E2-A nace de la combinación reportada en la literatura (Harsha & Rao, 2024): tendencia + volumen + momento.

```text
Entrada:  SMA rápida > SMA lenta          (tendencia)
          z-score de volumen > umbral     (participación)
          CCI cruza arriba de entry       (momento)
Salida:   CCI > exit   o   SMA rápida < SMA lenta
```

**En palabras:** solo compra si el mercado está en tendencia alcista, si hay volumen acompañando y si el momento gira al alza. Sale si el momento se agota o si la tendencia se rompe.

### A1: la reproducción del paper

A1 usa los parámetros publicados: CCI 20/−100/100, SMA 20/50, volumen 20/0,5. No se optimizó; es un control de validez externa.

**Resultado:** Sharpe −1,463, CAGR −2,92%, 30 operaciones, win rate 23,33%, PF 0,34. Pierde dinero.

**Por qué:** el CCI de entrada en −100 exige una caída extrema para comprar, y la SMA 20/50 es demasiado rápida para el régimen de Bitcoin. Entra tarde y sale mal. La idea del paper no se sostiene con sus propios parámetros en este mercado.

### A2: la versión optimizada

A2 mantiene la arquitectura y cambia los parámetros: CCI 58/−3/186, SMA 18/221, volumen 40/0,5816. Fue seleccionada con TPE-150 y confirmada con el TPE de la v3 con rf=4%: el optimizador devolvió exactamente los mismos valores.

**Resultado:** Sharpe 0,872, CAGR 17,08%, MaxDD −27,93%, 39 operaciones, win rate 76,92%, PF 3,17.

**Por qué funciona mejor:** el CCI de entrada en −3 compra en un giro de momento mucho más temprano, la SMA lenta de 221 (unos 37 días) capta el régimen de fondo y el umbral de volumen más alto filtra señales débiles.

## 3.3 E2-B: el experimento de machine learning

E2-B probó XGBoost, Random Forest y LightGBM para predecir la probabilidad de subida. Se descartó porque:

- El accuracy era bajo (alrededor de 0,40).
- El trading con umbral de probabilidad no superaba a las reglas simples.
- Añadía complejidad y riesgo de sobreajuste sin mejorar el Sharpe.

No forma parte del universo final. Se menciona para explicar por qué existe la letra C: se evaluaron tres familias (A, B y C).

## 3.4 E2-C: la composición de ganadoras

E2-C combina las ganadoras de la etapa 1 con roles:

```text
Entrada:  SMA rápida > SMA lenta          (régimen)
          MACD cruza arriba de su señal   (gatillo)
          RSI < 70                        (filtro)
Salida:   se rompe el régimen   o   MACD cruza abajo   o   RSI >= 70
```

Parámetros fijos: SMA 20/150, RSI 14/70, MACD 12/26/9.

**Resultado:** Sharpe −0,262, CAGR −1,79%, MaxDD −51,08%, 294 operaciones, win rate 35,03%, PF 0,99.

**Por qué pierde:** 294 operaciones × 30 pb ida y vuelta ≈ 88% del capital pagado en costos. Además, el MACD genera muchas señales falsas, el RSI la saca temprano de las tendencias y el régimen la deja fuera de buenos tramos. Es un control negativo: combinar las ganadoras individuales no garantiza una buena compuesta.

## 3.5 Las tres versiones del trabajo

| Versión | Métrica | Optimizador | Universo | Qué aportó |
|---|---|---|---|---|
| v1 | rf=0, Sortino, por vela | TPE | 10 estrategias | Primer capítulo de resultados |
| v2 | rf=0, Sortino, por vela | PSO sobre IS70 | 13 estrategias | Variante PSO y split 70/30 |
| **v3** | **rf=4%, por operación** | **TPE walk-forward** | **9 estrategias** | **Normalización y recomendación** |

La v3 no es una versión más "bonita": es la que elimina las inconsistencias de las anteriores (rf=0, Sortino mal definido, ATR que no se aplicaba, protocolos de selección distintos).

---

# 4. Datos y pipeline

## 4.1 La fuente

Binance Data Vision publica klines históricas en ZIP mensuales y diarios. El proyecto descarga, verifica el checksum SHA256 y consolida.

- Serie base: 1 minuto, 4.747.519 velas.
- Serie de análisis: 4 horas, 19.800 velas.
- Rango: 2017-08-17 04:00 UTC a 2026-09-01 20:00 UTC.

## 4.2 La limpieza

`src/processing/cleaner.py`:

- Lee los ZIP.
- Normaliza timestamps: desde 2025-01-01, Binance publica microsegundos (16 dígitos) en vez de milisegundos (13). Sin normalizar, las fechas caen en el año 55.000.
- Deduplica por `open_time`.
- Valida OHLC y detecta huecos.
- Escribe el parquet maestro.

Se detectaron 34 huecos reales de más de 1 minuto; no se imputan. Representan menos del 0,2% de las velas.

## 4.3 El resampleo

`src/processing/resample.py` agrega 1m a 4h:

- Open: primero.
- High: máximo.
- Low: mínimo.
- Close: último.
- Volumen: suma.
- Ratios de compra/venta y CVD: recalculados después del resampleo.

## 4.4 Por qué 4H

1. **Es la frecuencia de decisión de la estrategia y del bot.** Medir el Sharpe sobre retornos de 1 minuto de una posición que solo cambia cada 4 horas mide ruido que nunca se opera.
2. **Evita el ruido de microestructura.** A 1 minuto hay bid-ask bounce y prints obsoletos que distorsionan la volatilidad.
3. **Un solo timeframe, un solo P.** Se elimina el riesgo de mezclar 525.600 (1m) con 2.190 (4h).
4. **Coincide con el bot.** El ejecutor opera en 4H.

---

# 5. Metodología

## 5.1 De la señal a la posición

```text
r_t        = close_t / close_{t-1} - 1
posicion_t = senal_{t-1}                  (lag = 1)
bruto_t    = posicion_t * r_t
turnover_t = |posicion_t - posicion_{t-1}|
costo_t    = turnover_t * (fee + slippage)
neto_t     = bruto_t - costo_t
equity_t   = 10.000 * producto(1 + neto_t)
```

**En palabras:**

1. Se calcula cuánto cambió el precio de una vela a la siguiente.
2. La posición de hoy es la señal de ayer (lag = 1), para no mirar el futuro.
3. Si estás dentro, ganas o pierdes ese cambio; si estás fuera, ganas 0.
4. Se resta el costo de entrar o salir.
5. El capital se compone vela a vela.

## 5.2 El Sharpe

```text
rf_vela  = rf_anual / P
exceso_t = neto_t - rf_vela
Sharpe   = media(exceso) / desviacion(exceso, ddof=1) * sqrt(P)
```

- `rf_anual = 0,04`.
- `P = 2.190` para 4H.
- `P` se deduce del espaciado mediano entre timestamps.
- La tasa es obligatoria en el código: no existe un `rf = 0` implícito.
- `std` muestral (`ddof=1`), equivalente a `STDEV.S` en Excel.

**Ejemplo con A2:**

```text
media(exceso) = 0,0000586919
desviacion    = 0,0031489676
sqrt(2190)    = 46,7974
Sharpe        = 0,0000586919 / 0,0031489676 * 46,7974 = 0,872
```

## 5.3 Métricas por operación

Una operación va desde la entrada (0→1) hasta la salida (1→0), incluyendo el costo de salida.

- **Win rate:** ganadoras / total.
- **Profit factor:** suma de ganancias / |suma de pérdidas|.
- **Retorno medio:** promedio del retorno compuesto de cada operación.
- **Duración media:** velas o días dentro de la operación.

No se usan métricas por vela para acierto: con 91% de velas planas en A2, el win rate por vela subestima el desempeño.

## 5.4 Lo que se eliminó y por qué

- **Sortino:** no se usaba para decidir y la implementación anterior era no estándar.
- **Stop ATR:** viajaba en los parámetros, pero ningún backtest lo aplicaba. Mantenerlo sugería un mecanismo de riesgo que no existía.
- **Variantes PSO y overlays TP/SL del universo principal:** el PSO usaba otro protocolo y los TP/SL son variantes de riesgo del benchmark, no estrategias distintas. Quedan como anexo.

---

# 6. Universo de estrategias

## 6.1 Tabla de parámetros

| Estrategia | Entrada | Salida | Parámetros |
|---|---|---|---|
| Buy & Hold | Siempre long | Nunca | — |
| RSI | RSI cruza arriba de 45 | RSI ≥ 50 | periodo 20 |
| MACD | MACD cruza arriba de su señal | Cruza abajo | 26 / 89 / 20 |
| SMA | SMA rápida > lenta | SMA rápida < lenta | 19 / 247 |
| EMA | EMA rápida > lenta | EMA rápida < lenta | 77 / 115 |
| CCI | CCI cruza arriba de −75 | CCI > 150 | periodo 36 |
| E2-A A1 | Tendencia + volumen + CCI cruza −100 | CCI > 100 o SMA 20 < 50 | 20/50, vol 20/0,5 |
| E2-A A2 | Tendencia + volumen + CCI cruza −3 | CCI > 186 o SMA 18 < 221 | 18/221, vol 40/0,58 |
| E2-C | SMA 20 > 150, MACD cruza arriba, RSI < 70 | Sin régimen, MACD abajo o RSI ≥ 70 | 20/150, 14/70, 12/26/9 |

## 6.2 Descripción de cada una

**Buy & Hold:** compra BTC al inicio y lo mantiene. Es el benchmark: mide si la estrategia supera a simplemente holdear.

**RSI:** compra cuando el RSI sale de sobreventa (cruza 45) y vende cuando llega a 50. Es un indicador de reversión a la media; en un activo con tendencia, se queda corto en los tramos alcistas.

**MACD:** compra cuando el MACD cruza arriba de su señal y vende en el cruce contrario. Es un seguidor de tendencia, pero genera muchas señales falsas en mercados laterales.

**SMA:** dentro si la media móvil rápida (19) supera a la lenta (247). Es el seguidor de tendencia más simple y el que mejor captura el drift alcista secular de Bitcoin.

**EMA:** igual que SMA, pero con medias exponenciales (77/115). Reacciona más rápido, aunque con más ruido.

**CCI:** compra cuando el CCI cruza arriba de −75 y vende arriba de 150. Es un oscilador de momento; aislado tiende a atrapar rebotes que se agotan.

**E2-A A1:** la reproducción del paper. CCI 20/−100/100, SMA 20/50, volumen 20/0,5.

**E2-A A2:** la versión optimizada y recomendada. CCI 58/−3/186, SMA 18/221, volumen 40/0,5816.

**E2-C:** SMA régimen + MACD gatillo + RSI filtro, con parámetros fijos de la etapa 1.

## 6.3 Los tres roles del universo

- **Optimizadas (6):** RSI, MACD, SMA, EMA, CCI y E2-A A2. Seleccionadas con TPE 100 trials, folds 2021-2024, rf=4% y holdout.
- **Fijas de referencia (2):** E2-A A1 (paper) y E2-C (composición de ganadoras). No se optimizaron en la v3.
- **Benchmark (1):** Buy & Hold.

---

# 7. Selección de parámetros

## 7.1 Por qué optimizar

Cada estrategia tiene parámetros: cuántos días mirar, qué nivel de entrada, qué umbral de volumen. Cambiarlos cambia el resultado. Optimizar es buscar la combinación que mejor se comporta.

El riesgo es el **sobreajuste**: encontrar parámetros que funcionan de maravilla en el pasado pero fallan en el futuro.

## 7.2 TPE: el chef que prueba

TPE (Tree-structured Parzen Estimator) es un optimizador bayesiano creado por Bergstra, Bardenet, Bengio y Kégl (NIPS 2011).

**Analogía:** es como un chef que prueba la sopa. Al principio prueba al azar; luego se da cuenta de que las pruebas con más sal y menos agua saben mejor, y concentra sus pruebas en esa región. No prueba todas las combinaciones: aprende de las que ya hizo.

**Cómo funciona:**

1. Prueba unos puntos al azar.
2. Separa los resultados en buenos y malos.
3. Construye dos densidades: `l(x)` para los buenos y `g(x)` para los malos.
4. Propone el siguiente punto que maximiza `l(x)/g(x)`.

**Por qué se usa:** maneja parámetros enteros y decimales, es eficiente con 100 intentos y está implementado en Optuna con semilla reproducible.

## 7.3 PSO: la bandada de pájaros

PSO (Particle Swarm Optimization) es una metaheurística de Kennedy y Eberhart (1995).

**Analogía:** es una bandada de pájaros buscando comida. Cada pájaro recuerda dónde encontró la mejor comida y también mira dónde la encontró el grupo. Se mueve combinando su memoria con la del grupo.

```text
v <- w*v + c1*r1*(pbest - x) + c2*r2*(gbest - x)
x <- x + v
```

**Por qué se usó en la v2:** era simple de implementar en numpy y estaba citado en la literatura de trading. Pero la v2 cambió dos cosas a la vez: el algoritmo (TPE → PSO) y el protocolo (folds + holdout → un solo split 70/30). Eso hizo imposible saber cuál de las dos explicaba el resultado.

## 7.4 Folds y holdout: estudiar, simular y examinar

**Analogía:**

- **Folds:** estudias con unos ejercicios y haces un simulacro con otros. Repites con varios simulacros.
- **Holdout:** el examen final. No lo ves hasta el último día.

```text
2017 ---------- 2020 | 2021 | 2022 | 2023 | 2024 | 2025 -------- 2026
     entrenamiento   test   test   test   test      HOLDOUT
                     \______ folds de validacion ____/
```

Los folds son OOS respecto de su ventana de entrenamiento, pero se usan para elegir: son **validación**. El holdout es el único bloque que no participa de ninguna selección: es el **test final**.

## 7.5 El protocolo de la v3

- **Folds:** test 2021, 2022, 2023 y 2024.
- **Objetivo:** mediana del Sharpe OOS entre los cuatro folds, con rf=4%.
- **Warmup global:** los indicadores se calculan sobre toda la historia y luego se recorta el fold.
- **Regla de validez:** exposición ≥ 0,5%, al menos 5 operaciones, no perder con PF<1, MaxDD ≥ −50%. Fold inválido → −5,0.
- **Holdout:** 2025-01-01 a 2026-09-01, nunca usado en la selección.
- **Presupuesto:** 100 trials por estrategia, semilla 42.
- **Warm start:** el TPE arranca desde la selección anterior.

## 7.6 Por qué mediana y no promedio

Un solo año excepcional no debe dominar la selección. La mediana exige que el candidato sea razonable en la mayoría de los años, no solo en el mejor.

## 7.7 El 2,045 de la v2

El capítulo anterior citaba "mediana del Sharpe OOS entre folds = 2,045" para A2. Ese número no es comparable con el Sharpe del período completo:

- Se calculó con rf=0.
- Recalculaba los indicadores dentro de cada fold, sin warmup global.
- El fold 2022 tenía solo 3 operaciones y la regla de validez lo marcaba inválido con −5,0.
- La mediana de [1,79, −5,0, 2,31, 3,10] da 2,047, que redondeado es 2,045.

Con el protocolo actual (rf=4%, warmup global), la mediana de A2 es **1,567** y su Sharpe FULL es **0,872**.

## 7.8 Resultado de la re-selección

| Estrategia | Mediana OOS vieja | Mediana OOS nueva | Holdout viejo | Holdout nuevo |
|---|---:|---:|---:|---:|
| RSI | 0,519 | 1,036 | 0,353 | −0,662 |
| MACD | 1,266 | 1,337 | −0,393 | −0,009 |
| SMA | 1,567 | **1,729** | 0,053 | **0,435** |
| EMA | 1,260 | 1,606 | −0,294 | 0,121 |
| CCI | 0,935 | 0,988 | −0,453 | −0,268 |
| E2-A A2 | 1,567 | **1,567** | 0,339 | **0,339** |

- **A2 no cambió:** el TPE con rf=4% devolvió exactamente los mismos parámetros.
- **SMA mejoró en las tres dimensiones.**
- **RSI empeoró:** mejoró los folds pero su holdout cayó a −0,662.

## 7.9 El PSO con rf=4% como contraejemplo

| | IS70 | OOS30 | FULL | MaxDD |
|---|---:|---:|---:|---:|
| PSO v2 (rf=0) | 1,526 | 0,699 | 1,326 | −50,34 % |
| PSO v3 (rf=4%) | 1,550 | **−0,105** | 1,182 | −40,11 % |
| E2-A A2 | 1,567 | **1,412** | 0,872 | −27,93 % |

La re-optimización mejoró el in-sample en +0,024 y destruyó el forward en −0,804. Es evidencia de sobreajuste. Por eso el PSO queda fuera del universo normalizado.

---

# 8. Resultados

## 8.1 Riesgo y retorno (FULL)

| Estrategia | Sharpe | CAGR | Vol anual | MaxDD | Duración DD | Ulcer | Calmar |
|---|---:|---:|---:|---:|---:|---:|---:|
| **SMA** | **1,123** | **57,48 %** | 46,54 % | −70,96 % | 422 d | 34,38 | **0,810** |
| EMA | 1,065 | 53,37 % | 46,63 % | −66,72 % | 422 d | 34,24 | 0,800 |
| MACD | 0,924 | 42,72 % | 45,19 % | −60,05 % | 604 d | 25,75 | 0,711 |
| **E2-A A2** | 0,872 | 17,08 % | **14,74 %** | **−27,93 %** | **314 d** | **9,38** | 0,612 |
| BH | 0,749 | 37,48 % | 68,17 % | −83,91 % | 361 d | 47,13 | 0,447 |
| CCI | 0,248 | 2,89 % | 53,85 % | −87,04 % | 838 d | 52,79 | 0,033 |
| RSI | 0,209 | 5,49 % | 33,59 % | −57,43 % | 751 d | 20,93 | 0,096 |
| E2-C | −0,262 | −1,79 % | 16,77 % | −51,08 % | 2 056 d | 30,05 | −0,035 |
| E2-A A1 | −1,463 | −2,92 % | 4,68 % | −28,83 % | 3 187 d | 19,21 | −0,101 |

**Cómo leer:** SMA gana en Sharpe, CAGR y Calmar. A2 gana en drawdown, duración del drawdown y Ulcer. No hay dominancia.

## 8.2 Operativa y consistencia

| Estrategia | Trades | Win rate | PF | Retorno medio | Payoff | Duración media | Exposición | Peor año | Años positivos |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SMA | 66 | 33,33 % | **4,41** | **13,23 %** | **8,83** | 26 d | 51,8 % | −54,9 % | 6/8 |
| EMA | 57 | 35,09 % | 3,68 | 12,26 % | 6,81 | 30 d | 51,7 % | −51,3 % | 5/8 |
| MACD | 285 | 37,19 % | 1,73 | 1,49 % | 2,92 | 6 d | 50,6 % | −39,1 % | 6/8 |
| **E2-A A2** | **39** | **76,92 %** | 3,17 | 4,11 % | 0,95 | 8 d | **9,3 %** | **−22,4 %** | 6/8 |
| BH | 1 | 100,00 % | — | 1 677,59 % | — | 3 300 d | 100,0 % | −73,0 % | 5/8 |
| CCI | 118 | 75,42 % | 1,29 | 0,94 % | 0,42 | 16 d | 57,2 % | −65,6 % | 6/8 |
| RSI | 361 | 69,25 % | 1,22 | 0,20 % | 0,54 | 2 d | 23,1 % | −27,0 % | 5/8 |
| E2-C | 294 | 35,03 % | 0,99 | −0,01 % | 1,84 | 1 d | 9,9 % | −22,0 % | 4/8 |
| E2-A A1 | 30 | 23,33 % | 0,34 | −0,87 % | 1,11 | 1 d | 1,0 % | −7,5 % | 1/8 |

**Dos perfiles opuestos:**

- **SMA:** gana solo el 33% de las veces, pero cuando gana, gana muchísimo (payoff 8,83).
- **A2:** gana el 77% de las veces, pero su ganancia media es menor que su pérdida media (payoff 0,95). Acierta mucho, pero con wins pequeños.

## 8.3 Por temporadas de halving

| Estrategia | C16 | C20 | C24 | FULL |
|---|---:|---:|---:|---:|
| BH | 0,684 | 1,052 | 0,316 | 0,749 |
| SMA | 1,036 | 1,413 | 0,749 | 1,123 |
| MACD | 1,265 | 0,874 | 0,440 | 0,924 |
| E2-A A2 | 1,003 | 0,680 | **1,327** | 0,872 |
| E2-C | 0,184 | −0,279 | −1,063 | −0,262 |

En C24, el ciclo lateral, A2 es la única con Sharpe alto (1,327) y drawdown de un dígito (−8,82%). SMA y MACD se desinflan; E2-C pierde.

## 8.4 In-sample vs out-of-sample

| Estrategia | IS70 | OOS30 |
|---|---:|---:|
| BH | 0,800 | 0,631 |
| SMA | 1,154 | 1,119 |
| MACD | 0,986 | 0,773 |
| E2-A A2 | 0,762 | **1,412** |
| E2-C | −0,027 | −1,057 |

A2 mejora fuera de muestra; SMA se mantiene; MACD cae; E2-C colapsa.

## 8.5 Robustez: peor Sharpe entre seis ventanas

| Estrategia | Peor Sharpe |
|---|---:|
| SMA | 0,749 |
| E2-A A2 | 0,680 |
| EMA | 0,544 |
| MACD | 0,440 |
| BH | 0,316 |
| CCI | −0,308 |
| RSI | −0,853 |
| E2-C | −1,063 |
| E2-A A1 | −2,162 |

Solo SMA y A2 tienen un peor caso superior a 0,6.

## 8.6 Sensibilidad a la tasa libre de riesgo

| Estrategia | rf=0% | rf=3,8% | rf=4% | rf=5% |
|---|---:|---:|---:|---:|
| BH | 0,808 | 0,752 | 0,749 | 0,734 |
| SMA | 1,209 | 1,127 | 1,123 | 1,101 |
| EMA | 1,151 | 1,069 | 1,065 | 1,044 |
| MACD | 1,013 | 0,929 | 0,924 | 0,902 |
| E2-A A2 | 1,144 | 0,886 | 0,872 | 0,804 |
| RSI | 0,328 | 0,214 | 0,209 | 0,179 |
| CCI | 0,322 | 0,251 | 0,248 | 0,229 |
| E2-C | −0,024 | −0,251 | −0,262 | −0,322 |
| E2-A A1 | −0,609 | −1,421 | −1,463 | −1,677 |

La conclusión es estable en todo el rango: SMA y A2 superan al Buy & Hold con cualquier tasa entre 0% y 5%.

## 8.7 Retorno anual de A2 y SMA

| Año | E2-A A2 | SMA |
|---|---:|---:|
| 2021 | 49,3 % | 134,2 % |
| 2022 | −22,4 % | −53,2 % |
| 2023 | 28,7 % | 111,7 % |
| 2024 | 43,1 % | 108,0 % |
| 2025 | 5,8 % | 12,7 % |

A2 tiene un perfil mucho más estable: su peor año es −22,4%, frente a −53,2% de SMA.

## 8.8 Figuras

![Figura 1. Equity del período completo en escala logarítmica. La escala log permite comparar crecimientos muy distintos; A2 crece menos, pero con una curva mucho más suave.](figs/v3_fig01_equity_full.png)

![Figura 2. Equity por temporada de halving. En C24, el ciclo lateral, A2 es la única que mantiene una curva ascendente y estable.](figs/v3_fig02_equity_temporadas.png)

![Figura 3. Drawdown del período completo. La línea de A2 es la más superficial; la de BH y SMA, las más profundas.](figs/v3_fig03_drawdown_full.png)

![Figura 4. Sharpe por temporada. SMA y MACD dominan los ciclos alcistas; A2 domina el ciclo lateral.](figs/v3_fig04_barras_sharpe.png)

![Figura 5. Sensibilidad del Sharpe a la tasa libre de riesgo. El ranking no cambia entre 0% y 5%.](figs/v3_fig05_sensibilidad_rf.png)

![Figura 6. Rentabilidad vs riesgo. Cada burbuja es una estrategia; el eje horizontal es el MaxDD y el vertical el CAGR. A2 está arriba a la derecha: buen retorno con poco drawdown.](figs/dossier_riesgo_retorno.png)

![Figura 7. Retorno por año calendario de A2 y SMA. A2 tiene pérdidas y ganancias más pequeñas; SMA es mucho más volátil.](figs/dossier_anual.png)

![Figura 8. Dos perfiles: win rate vs payoff. SMA está arriba a la izquierda (pocos aciertos, ganancias grandes); A2 abajo a la derecha (muchos aciertos, ganancias pequeñas).](figs/dossier_perfil.png)

![Figura 9. Sharpe antes y después de la normalización. La caída se explica casi toda por la tasa libre de riesgo, no por un deterioro de las estrategias.](figs/dossier_sharpe_antes_despues.png)

![Figura 10. Convergencia del PSO con rf=4%. Mejora el in-sample, pero el resultado no se sostiene fuera de muestra.](figs/v3_fig06_pso_convergencia.png)

---

# 9. Decisiones tomadas y por qué

| Decisión | Alternativa descartada | Por qué se tomó | Consecuencia |
|---|---|---|---|
| Analizar en 4H | 1m | Frecuencia de decisión, menos microestructura, un solo P | 19.800 velas, métricas estables |
| rf = 4% | rf=0 o 3,8% | T-Bill ago-2026 ~3,8%; 4% redondo y conservador | Sharps más bajos y comparables |
| Métricas por operación | Por vela | 91% de velas planas en A2 | Win rate 76,9% vs 53,3% |
| Eliminar Sortino | Mantenerlo | No se usaba y estaba mal definido | Menos métricas, menos confusión |
| Eliminar ATR | Mantenerlo | Nunca se aplicó en el backtest | E2-A es 0/1 pura |
| TPE walk-forward | PSO split único | Evalúa en 4 años y exige holdout | A2 estable; PSO sobreajusta |
| 100 trials | 80/150 | Mismo presupuesto para las 6 | Comparación justa |
| Warm start | Búsqueda fría | Evita que el TPE pierda un punto conocido | A2 se mantiene |
| Recomendar A2 | SMA | Menor drawdown y mayor consistencia | Perfil conservador defendible |
| PSO a anexo | Universo principal | Protocolo distinto y OOS negativo | Menos confusión |
| Bot en PSO | A2 | Cambio pendiente | Inconsistencia declarada |

## 9.1 Antes y después del Sharpe

| Estrategia | Antes (rf=0) | Después (rf=4%) | Δ total | Por rf | Por params |
|---|---:|---:|---:|---:|---:|
| SMA | 1,244 | 1,123 | −0,121 | −0,086 | −0,035 |
| EMA | 1,152 | 1,065 | −0,087 | −0,087 | 0,000 |
| MACD | 0,960 | 0,924 | −0,036 | −0,088 | +0,052 |
| E2-A A2 | 1,144 | 0,872 | −0,271 | −0,271 | 0,000 |
| BH | 0,808 | 0,749 | −0,059 | −0,059 | 0,000 |
| CCI | 0,264 | 0,248 | −0,017 | −0,075 | +0,058 |
| RSI | 0,432 | 0,209 | −0,224 | −0,108 | −0,116 |
| E2-C | −0,024 | −0,262 | −0,239 | −0,239 | 0,000 |
| E2-A A1 | −0,609 | −1,463 | −0,854 | −0,854 | 0,000 |

La caída por rf es exactamente `rf / volatilidad anual`:

- A1: 0,04 / 0,0468 = 0,854.
- A2: 0,04 / 0,1474 = 0,271.
- BH: 0,04 / 0,6817 = 0,059.

Por eso las estrategias de baja volatilidad pierden más Sharpe al introducir la tasa.

---

# 10. Métricas explicadas

## 10.1 Sharpe

**Qué es:** retorno en exceso por unidad de volatilidad total.

**Analogía:** kilómetros por litro, pero con riesgo en vez de combustible.

**Cómo se lee:** 0,5 aceptable; 1 bueno; 2 muy bueno; 3 excepcional o sospechoso.

## 10.2 Sortino

**Qué es:** igual que el Sharpe, pero el denominador es la desviación a la baja.

**Analogía:** solo cuenta los baches del camino, no las subidas.

**Por qué se eliminó:** no se usaba para decidir y la implementación anterior era no estándar.

## 10.3 Calmar

**Qué es:** CAGR / |MaxDD|.

**Analogía:** retorno anual por unidad de peor caída.

**Cómo se lee:** SMA 0,810; A2 0,612. No dice nada de la frecuencia ni duración de las caídas.

## 10.4 MaxDD

**Qué es:** peor caída desde un máximo de equity.

**Analogía:** la distancia desde la cima hasta el valle más profundo.

**Cómo se lee:** A2 −27,93%; SMA −70,96%; BH −83,91%.

## 10.5 Ulcer

**Qué es:** raíz del promedio de los drawdowns al cuadrado.

**Analogía:** mide el "dolor acumulado", no solo la caída máxima.

**Cómo se lee:** A2 9,38; SMA 34,38; BH 47,13.

## 10.6 Profit factor

**Qué es:** ganancias / |pérdidas|.

**Analogía:** cuántos dólares ganas por cada dólar que pierdes.

**Cómo se lee:** >1 gana; >1,5 bueno; >2 muy bueno.

## 10.7 Payoff

**Qué es:** ganancia media / |pérdida media|.

**Analogía:** cuánto ganas cuando aciertas comparado con cuánto pierdes cuando fallas.

**Cómo se lee:** SMA 8,83; A2 0,95. Un payoff menor que 1 puede ser rentable si el win rate es alto.

## 10.8 Win rate

**Qué es:** operaciones ganadoras / total.

**Analogía:** porcentaje de tiros que entran.

**Cómo se lee:** SMA 33,33%; A2 76,92%. No es suficiente por sí solo.

## 10.9 Retorno medio

**Qué es:** promedio del retorno compuesto de cada operación.

**Analogía:** cuánto gana una operación típica.

**Cómo se lee:** SMA 13,23%; A2 4,11%; E2-C −0,01%.

## 10.10 Exposición

**Qué es:** fracción del tiempo dentro del mercado.

**Analogía:** porcentaje del tiempo que pasas jugando.

**Cómo se lee:** A2 9,3%; SMA 51,8%; BH 100%.

## 10.11 Turnover

**Qué es:** suma de |Δposición|.

**Analogía:** cuánto entra y sale el capital.

**Cómo se lee:** SMA 131; A2 78; E2-C 588.

## 10.12 CAGR y volatilidad

**CAGR:** crecimiento anual compuesto. **Volatilidad:** desviación de los retornos por vela, anualizada con `sqrt(2190)`.

---

# 11. Preguntas que podría hacer el profesor

**1. ¿Por qué 4H y no 1 minuto?**
Porque es la frecuencia de decisión y la que opera el bot. A 1 minuto se mide ruido de microestructura que nunca se opera y se viola más el supuesto de independencia que exige `sqrt(P)`.

**2. ¿Por qué rf = 4% y no 0?**
La T-Bill a 3 meses promedió ~3,80% en agosto de 2026. Se usa 4% por ser redondo y ligeramente conservador. Con rf=0 el Sharpe de A2 sería 1,144; con 4%, 0,872.

**3. ¿Por qué el Sharpe de A2 es solo 0,87?**
Porque el período completo incluye 2022 (−22,4%) y 2025-2026 (+5,8%). En 2024 solo, A2 tuvo Sharpe 3,19. El 0,87 es el número honesto de nueve años, no el de un año bueno.

**4. ¿Por qué no usa Sortino?**
Se eliminó porque no se usaba para decidir y la implementación anterior no era estándar. Si se reporta, debe ser con la fórmula correcta y una nota.

**5. ¿Por qué TPE y no PSO?**
Porque el protocolo de TPE es walk-forward con holdout. PSO se usó en la v2 con un solo split 70/30 y sobreajustó: mejoró el in-sample +0,024 y cayó −0,804 fuera de muestra.

**6. ¿Qué es el holdout?**
El bloque 2025-2026 que no participa de ninguna selección. Es el único test realmente virgen.

**7. ¿Los folds no son out-of-sample?**
Sí, respecto de su ventana de entrenamiento, pero se usan para elegir: son validación. El test final es el holdout.

**8. ¿Por qué recomienda A2 si SMA tiene mejor Sharpe?**
Porque el criterio de la tesis es riesgo conservador: A2 tiene drawdown −27,93% vs −70,96%, peor año −22,4% vs −54,9% y win rate 76,92% vs 33,33%. SMA gana en Sharpe, Calmar y retorno; es la alternativa agresiva.

**9. ¿A2 no está sobreajustada?**
No cambió al re-optimizar con rf=4% y su OOS30 es 1,412, mejor que su IS70 0,762. No muestra degradación fuera de muestra.

**10. ¿Por qué A1 pierde si es la estrategia del paper?**
Porque los parámetros del paper (CCI −100, SMA 20/50) no generalizan a BTC 4H. A2 demuestra que la arquitectura sí puede funcionar con otros parámetros.

**11. ¿Por qué E2-C pierde?**
Porque hace 294 operaciones y paga ~88% del capital en costos; además, el MACD y el RSI se estorban. Es un control negativo: combinar ganadoras no garantiza una buena compuesta.

**12. ¿No hay look-ahead?**
No: la posición usa la señal de la vela anterior (lag=1). Los indicadores se calculan con datos pasados y el holdout no participa de la selección.

**13. ¿Los costos son realistas?**
Se usan 10 pb de fee taker + 5 pb de slippage por lado. Es conservador para BTC/USDT en Binance. No se modela impacto de mercado ni liquidez.

**14. ¿Por qué long-only?**
Porque el bot es spot y no opera cortos. Además, el mercado de Bitcoin tiene un sesgo alcista secular; los cortos habrían cambiado la naturaleza del estudio.

**15. ¿Cuántas operaciones hay? ¿Alcanza para inferencia?**
A2 tiene 39 operaciones en nueve años. Es una limitación: el win rate y el PF tienen intervalos de confianza amplios. Por eso se reportan también el Sharpe (19.800 velas) y el OOS.

**16. ¿No hay multiple testing?**
Sí es una limitación. Se probaron 6 estrategias con 100 trials cada una. El holdout y la mediana de folds mitigan el problema, pero no lo eliminan. Un deflated Sharpe sería el siguiente paso.

**17. ¿Por qué el bot sigue en PSO?**
Porque el cambio de variante es una decisión operativa pendiente. La tesis recomienda A2; el bot se ajustará después. Está declarado como inconsistencia.

**18. ¿Qué pasa si cambio la rf a 5%?**
A2 baja a 0,804 y SMA a 1,101; el ranking no cambia. La conclusión es robusta entre 0% y 5%.

**19. ¿Por qué el Sharpe de la v2 era 1,144 y ahora 0,872?**
Porque la v2 usaba rf=0. La diferencia de 0,271 es exactamente `4% / 14,74%`. No cambió la estrategia; cambió la métrica.

**20. ¿Qué haría con más tiempo?**
Ampliar el espacio del TPE (los bordes), probar walk-forward con ventanas móviles, incluir costos por volumen, modelar stops intra-vela y evaluar una cartera A2+SMA.

**21. ¿Por qué el 2,045 de la v2 no aparece ahora?**
Porque era la mediana de folds con rf=0, warmup por fold y un fold inválido con −5,0. Con el protocolo actual, la mediana de A2 es 1,567.

**22. ¿Cómo se reproduce?**
Con `run_tpe_v3.py`, `run_resultados.py` y `md_to_pdf_v3.py`. El `manifest.json` guarda commit, hash de configuración, rf, timeframe y universo.

---

# 12. Limitaciones y trabajo futuro

## 12.1 Limitaciones

- **Pocas operaciones en A2:** 39 en nueve años. La inferencia sobre win rate y PF es limitada.
- **Holdout usado para comparar selecciones:** el 2025-2026 se usó para comparar los parámetros viejos y nuevos; ya no es completamente virgen para esa comparación.
- **Bordes del TPE:** CCI salida en 150 y SMA lenta en 247 quedaron en los límites del espacio.
- **Sin stops intra-vela:** todo se evalúa a cierre de vela de 4H.
- **Un solo activo:** BTC/USDT; no se prueba diversificación.
- **Costos fijos:** no se modela impacto de mercado ni liquidez.
- **Multiple testing:** 6 estrategias × 100 trials; el holdout mitiga, pero no elimina el riesgo.
- **Bot en PSO:** la tesis recomienda A2, pero el bot sigue en PSO.

## 12.2 Trabajo futuro

- Ampliar el espacio de búsqueda del TPE.
- Implementar walk-forward con ventanas móviles y deflated Sharpe.
- Modelar stops intra-vela y costos por volumen.
- Evaluar una cartera combinada A2 + SMA.
- Alinear el bot con la estrategia recomendada.
- Probar el marco en otros activos.

---

# 13. Glosario

| Término | Definición simple |
|---|---|
| **Backtest** | Simulación de una estrategia sobre datos históricos |
| **Benchmark** | Referencia contra la que se compara; aquí, Buy & Hold |
| **CAGR** | Crecimiento anual compuesto |
| **Calmar** | CAGR / |MaxDD| |
| **Drawdown** | Caída desde un máximo de equity |
| **EMA** | Media móvil exponencial |
| **Exposición** | Fracción del tiempo dentro del mercado |
| **Fold** | Ventana de entrenamiento y su año de test |
| **Holdout** | Bloque final que no participa de la selección |
| **IS** | In-sample: datos usados para elegir |
| **Lag** | Desplazamiento de la señal para evitar look-ahead |
| **MaxDD** | Peor drawdown del período |
| **OOS** | Out-of-sample: datos no usados para esa elección |
| **Payoff** | Ganancia media / pérdida media |
| **PF** | Profit factor: ganancias / pérdidas |
| **PSO** | Particle Swarm Optimization |
| **rf** | Tasa libre de riesgo anual |
| **Sharpe** | Retorno en exceso / volatilidad total |
| **SMA** | Media móvil simple |
| **Sortino** | Retorno en exceso / desviación a la baja |
| **TPE** | Tree-structured Parzen Estimator |
| **Turnover** | Suma de cambios de posición |
| **Ulcer** | Raíz del promedio de drawdowns al cuadrado |
| **Volatilidad** | Desviación de los retornos, anualizada |
| **Walk-forward** | Validación con ventanas que avanzan |
| **Win rate** | Operaciones ganadoras / total |

---

# 14. Reproducción y archivos

```text
python scripts/run_tpe_v3.py          # re-seleccion TPE con rf=4%
python scripts/run_resultados.py      # tablas, figuras y manifiesto
python scripts/md_to_pdf_v3.py        # capitulo en PDF
python scripts/md_to_pdf_dossier.py   # este dossier en PDF
python scripts/make_dossier_figs.py   # figuras adicionales
```

Archivos clave:

- `configs/strategies.yaml` — rf, timeframe, costos y parámetros `v3_selection`.
- `src/backtesting/engine.py` — motor.
- `src/backtesting/metrics.py` — métricas.
- `scripts/run_tpe_v3.py` — selección.
- `scripts/run_resultados.py` — resultados.
- `docs/tesis_resultados_v3/CAPITULO_RESULTADOS_v3.md` — capítulo.
- `docs/tesis_resultados_v3/tablas/` — tablas.
- `docs/tesis_resultados_v3/figs/` — figuras.
- `docs/tesis_resultados_v3/manifest.json` — trazabilidad.

---

# 15. Bibliografía

- Bergstra, J., Bardenet, R., Bengio, Y., & Kégl, B. (2011). *Algorithms for Hyper-Parameter Optimization*. NIPS 2011. Origen del TPE.
- Akiba, T., Sano, S., Yanase, T., Ohta, T., & Koyama, M. (2019). *Optuna: A Next-generation Hyperparameter Optimization Framework*. KDD 2019. Implementación usada.
- Kennedy, J., & Eberhart, R. (1995). *Particle Swarm Optimization*. IEEE ICNN. Origen del PSO.
- Sharpe, W. F. (1966). *Mutual Fund Performance*. Journal of Business. Origen del ratio de Sharpe.
- Sortino, F. A., & Price, L. N. (1994). *Performance Measurement in a Downside Risk Framework*. Journal of Investing. Origen del Sortino.
- Young, T. W. (1991). *Calmar Ratio: A Smoother Tool*. Futures Magazine. Origen del Calmar.
- Harsha, & Rao (2024). Referencia de la estrategia CCI + SMA + volumen, citada en el capítulo de resultados.
- Binance. *Binance Data Vision — Public Spot Data*. https://data.binance.vision

---

# 16. Checklist para la defensa

- [ ] Saber explicar qué es una vela, una señal 0/1 y el lag=1.
- [ ] Saber por qué se usa 4H y no 1m.
- [ ] Saber por qué rf=4% y qué pasa con 0% o 5%.
- [ ] Saber la diferencia entre Sharpe, Sortino y Calmar.
- [ ] Saber por qué A2 se recomienda aunque SMA tenga mejor Sharpe.
- [ ] Saber qué es el holdout y por qué no es lo mismo que OOS30.
- [ ] Saber por qué el 2,045 de la v2 no es comparable con el 0,872 actual.
- [ ] Saber por qué A1 y E2-C pierden.
- [ ] Saber qué es el sobreajuste y cómo se detectó en el PSO.
- [ ] Tener a mano el PDF del capítulo y este dossier.

---

> **Cierre:** la investigación queda con un protocolo único, una métrica única y un universo de nueve estrategias. La recomendación es E2-A A2 para un perfil conservador; SMA queda como alternativa agresiva. Las decisiones están documentadas, los resultados son reproducibles y las limitaciones están declaradas.
