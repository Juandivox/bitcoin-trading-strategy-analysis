# Prueba de hipótesis — SMA vs E2-A A2 vs Buy & Hold

**Documento de apoyo — Trading BTC/USDT 4H**

**Ingeniería Financiera — UNAB**

**9 de noviembre de 2026**

> **Resumen en 3 ideas**
>
> 1. Los estimadores puntuales favorecen a SMA (Sharpe 1,124), seguida de A2 (0,826) y Buy & Hold (0,754), en retornos diarios.
> 2. **Ninguna de las diferencias de Sharpe es estadísticamente significativa**: todos los p-valores son mayores que 0,14, incluso antes de corregir por comparaciones múltiples.
> 3. La defensa de A2 no se apoya en un Sharpe estadísticamente superior, sino en su **drawdown mucho menor** (−27,5% vs −83,2% de BH) y en su consistencia.

---

# 1. La pregunta

¿La diferencia de Sharpe entre las tres estrategias es real o podría ser producto del azar?

Dicho de otra forma: si las tres estrategias tuvieran en realidad el mismo Sharpe, ¿qué probabilidad habría de observar diferencias como las que vemos?

---

# 2. Las tres estrategias

| Estrategia | Rol | Por qué se eligió |
|---|---|---|
| **SMA** | Mejor Sharpe | Es la de mayor Sharpe del universo (1,123 en 4H) |
| **E2-A A2** | Conservadora | Sharpe menor, pero mucho menos exposición y drawdown |
| **Buy & Hold** | Benchmark | Es la referencia: comprar y mantener |

Las tres se evalúan con el mismo motor, los mismos costos (15 pb) y el mismo período (2017-2026).

---

# 3. Los datos

- **Frecuencia:** retornos **diarios**, construidos componiendo las velas de 4 horas de cada día.
- **Período completo:** 3.303 días (2017-08-17 a 2026-09-01).
- **Holdout:** 609 días (2025-01-01 a 2026-09-01), el bloque que no se usó para seleccionar.
- **Tasa libre de riesgo:** 4% anual, prorrateada a 1/365 por día.

## Por qué retornos diarios y no 4H

1. **Menos ruido de microestructura.** A 4H todavía hay ruido; a diario se reduce.
2. **Es la frecuencia estándar** en los tests de Sharpe.
3. **El ranking no cambia:** SMA 1,124, A2 0,826, BH 0,754 en diario; SMA 1,123, A2 0,872, BH 0,749 en 4H.
4. **n es manejable:** 3.303 días, suficiente para estimar, aunque no para distinguir diferencias pequeñas.

El Sharpe oficial de la tesis es el de 4H. El diario se usa aquí como base de la prueba, y se reporta la diferencia.

---

# 4. Las hipótesis

Para cada par de estrategias:

```text
H0: Sharpe(i) = Sharpe(j)      (no hay diferencia)
H1: Sharpe(i) ≠ Sharpe(j)      (hay diferencia)
```

Se usan **tres comparaciones pareadas**:

1. SMA vs A2.
2. SMA vs BH.
3. A2 vs BH.

Se usa un contraste **de dos colas** porque no se asume de antemano qué estrategia es mejor; después se reporta la dirección del estimador.

Como se hacen tres comparaciones, se aplica la **corrección de Holm** para controlar los falsos positivos.

---

# 5. La metodología

## 5.1 El Sharpe

```text
exceso_t = r_t - rf/365
Sharpe   = media(exceso) / desviacion(exceso, ddof=1) * sqrt(365)
```

Es el retorno en exceso por unidad de volatilidad, anualizado. Un Sharpe de 1 significa que el exceso de retorno es igual a la volatilidad.

## 5.2 Test de Jobson-Korkie (1981), versión Memmel (2003)

**Qué hace:** compara dos Sharpe ratios que vienen de la misma serie de mercado, ajustando por la correlación entre las estrategias.

**Por qué no basta un t-test normal:** las estrategias no son independientes. SMA y BH se mueven juntos; si se ignorara la correlación, el error estándar sería incorrecto.

**Fórmula:**

```text
SR1 = media(exceso_1) / desv(exceso_1)     (diario, no anualizado)
SR2 = media(exceso_2) / desv(exceso_2)
rho = correlación entre exceso_1 y exceso_2
n   = número de días

var = (1/n) * [ 2(1-rho) + 0.5*(SR1^2 + SR2^2 - 2*SR1*SR2*rho^2) ]
z   = (SR1 - SR2) / sqrt(var)
p   = 2 * (1 - Phi(|z|))
```

**En palabras:** el numerador es la diferencia de Sharpe; el denominador mide cuánto puede variar esa diferencia por azar, teniendo en cuenta que las estrategias están correlacionadas. Si `z` es grande, la diferencia es difícil de explicar por azar.

**Supuestos:** retornos iid y aproximadamente normales. En cripto no se cumple del todo; por eso se complementa con bootstrap.

## 5.3 Bootstrap de bloques

**Qué hace:** remuestrea bloques de días (no días sueltos) para conservar la autocorrelación y los clusters de volatilidad, recalcula la diferencia de Sharpe 5.000 veces y obtiene un intervalo de confianza y un p-valor.

**Por qué bloques:** si se remuestrearan días sueltos, se rompería la dependencia temporal y el intervalo sería demasiado estrecho. Con bloques de 20 días (aproximadamente un mes) se preserva la estructura.

**Cómo se lee:** si el intervalo del 95% **incluye el cero**, la diferencia no es estadísticamente significativa al 5%.

**Ventaja:** no asume normalidad y es fácil de explicar: "resolvemos la historia muchas veces y vemos cuántas veces la diferencia se invierte".

## 5.4 Corrección de Holm

**Qué hace:** ajusta los p-valores cuando se hacen varias comparaciones.

**Por qué:** si haces 3 pruebas al 5%, la probabilidad de al menos un falso positivo no es 5%, sino mayor. Holm sube el listón de forma secuencial.

**Cómo se lee:** se compara el p-valor ajustado con 0,05, no el crudo.

## 5.5 Test t pareado (secundario)

**Qué hace:** compara el **retorno medio diario** de dos estrategias, no el Sharpe.

```text
d_t = r1_t - r2_t
t   = media(d) / (desv(d)/sqrt(n))
```

**Por qué es secundario:** ignora el riesgo. Una estrategia puede ganar más en promedio porque asume mucha más volatilidad. Se incluye solo para mostrar la diferencia y advertir por qué no basta.

---

# 6. Resultados

## 6.1 Descriptivos — período completo

| Estrategia | Sharpe | Vol. diaria | MaxDD | Skew | Kurtosis |
|---|---:|---:|---:|---:|---:|
| SMA | **1,124** | 2,420 % | −69,99 % | 0,83 | 11,06 |
| E2-A A2 | 0,826 | 0,823 % | **−27,55 %** | 2,49 | 53,40 |
| BH | 0,754 | 3,506 % | −83,19 % | −0,23 | 8,71 |

**Lectura:** SMA tiene el mayor Sharpe; A2 tiene la menor volatilidad y el menor drawdown; BH tiene el mayor riesgo. La kurtosis de A2 (53,4) indica colas muy gruesas: por eso el bootstrap es importante.

## 6.2 Correlaciones

| Par | Correlación |
|---|---:|
| SMA - A2 | 0,354 |
| SMA - BH | 0,690 |
| A2 - BH | 0,251 |

La correlación importa: SMA y BH comparten el 69% de su movimiento; A2 está más diversificada.

## 6.3 Jobson-Korkie — período completo

| Par | Diferencia de Sharpe | z | p-valor | p Holm |
|---|---:|---:|---:|---:|
| SMA - A2 | 0,298 | 0,79 | 0,431 | 0,861 |
| SMA - BH | 0,370 | 1,41 | 0,159 | 0,476 |
| A2 - BH | 0,072 | 0,18 | 0,860 | 0,861 |

**Ningún p-valor es menor que 0,05.** Ni siquiera el de SMA-BH, que es el más cercano (0,159).

## 6.4 Bootstrap — período completo

| Par | Diferencia | IC 95% | p-valor | p Holm |
|---|---:|---|---:|---:|
| SMA - A2 | 0,298 | [−0,479 ; 1,051] | 0,496 | 0,992 |
| SMA - BH | 0,370 | [−0,132 ; 0,853] | 0,145 | 0,436 |
| A2 - BH | 0,072 | [−0,722 ; 0,880] | 0,844 | 0,992 |

**Los tres intervalos incluyen el cero.** El de SMA-BH apenas lo incluye por abajo (−0,132), pero sigue incluyéndolo.

## 6.5 Holdout 2025-2026

| Estrategia | Sharpe | Vol. diaria | MaxDD |
|---|---:|---:|---:|
| SMA | 0,434 | 1,298 % | −21,32 % |
| E2-A A2 | 0,342 | 0,425 % | **−7,18 %** |
| BH | −0,134 | 2,284 % | −52,97 % |

| Par | Diferencia | IC 95% | p bootstrap | p Holm |
|---|---:|---|---:|---:|
| SMA - A2 | 0,092 | [−1,634 ; 2,093] | 0,935 | 1,000 |
| SMA - BH | 0,568 | [−0,437 ; 1,827] | 0,242 | 0,727 |
| A2 - BH | 0,476 | [−1,573 ; 2,522] | 0,584 | 1,000 |

En el holdout, con solo 609 días, los intervalos son enormes y nada es significativo. El ranking puntual se mantiene (SMA > A2 > BH), pero la incertidumbre es demasiado alta.

## 6.6 Figura: diferencia de Sharpe con intervalo de confianza

![Figura 1. Diferencia de Sharpe anualizado con intervalo de confianza del 95% (bootstrap de bloques). Todos los intervalos incluyen el cero, por lo que ninguna diferencia es estadísticamente significativa.](figs/hipotesis_ci.png)

## 6.7 Test t pareado — retornos diarios

| Par | Diferencia media diaria | t | p-valor |
|---|---:|---:|---:|
| SMA - A2 | +0,1068 % | 2,71 | **0,007** |
| SMA - BH | +0,0040 % | 0,09 | 0,928 |
| A2 - BH | −0,1028 % | −1,74 | 0,082 |

**Lectura:** SMA gana más por día que A2 (p=0,007), pero con casi tres veces más volatilidad diaria y un drawdown de −70% frente a −27,5%. A2 gana menos por día que BH (p=0,082), pero con un drawdown de −27,5% frente a −83,2%. **El retorno medio no es el criterio correcto para comparar estrategias de distinto riesgo.**

---

# 7. Interpretación

## 7.1 No hay diferencias estadísticamente significativas de Sharpe

Los tres p-valores del JK y del bootstrap son mayores que 0,05, y siguen siéndolo después de Holm. La conclusión estadística es:

> **No se puede rechazar la hipótesis de que las tres estrategias tengan el mismo Sharpe.**

Eso **no** significa que sean iguales. Significa que, con 3.303 días y esta volatilidad, la diferencia observada es compatible con el azar.

## 7.2 La diferencia es económica, pero no estadística

Los estimadores puntuales:

- SMA 1,124.
- A2 0,826.
- BH 0,754.

SMA supera a A2 en 0,298 y a BH en 0,370. Son diferencias **económicamente relevantes**, pero **estadísticamente no concluyentes**. La tesis debe decir las dos cosas: "los estimadores favorecen a SMA, pero la evidencia no permite afirmar que la diferencia sea real".

## 7.3 Por qué los intervalos son tan anchos

El error estándar de la diferencia de Sharpe depende de:

- La volatilidad de los retornos.
- La correlación entre las estrategias.
- El número de observaciones.

Con 9 años de datos diarios, el error estándar de la diferencia es del orden de 0,2-0,4. Para detectar una diferencia de 0,3 con 80% de potencia haría falta una muestra bastante más larga, o más activos, o una estrategia con mucha menos volatilidad. **No es un problema del test: es un problema de información.**

## 7.4 A2 vs BH: la defensa es el riesgo, no el Sharpe

La diferencia de Sharpe A2−BH es 0,072, con IC [−0,722 ; 0,880]. No es significativa. La diferencia de retorno medio es −0,1028% diario (A2 gana menos), también borderline.

Entonces, ¿por qué recomendar A2? Porque el criterio no es solo Sharpe:

- **MaxDD:** −27,55% vs −83,19%.
- **Ulcer:** 9,38 vs 47,13.
- **Peor año:** −22,4% vs −73,0%.
- **Exposición:** 9,3% vs 100%.
- **Win rate:** 76,92% vs 100% (pero con una sola operación en BH).

La tesis debe ser explícita: **A2 no es mejor que BH en Sharpe de forma estadísticamente significativa; es mejor en riesgo de caída.** Esa es una conclusión honesta y defendible.

## 7.5 SMA vs A2: el trade-off

La diferencia de Sharpe SMA−A2 es 0,298, con IC [−0,479 ; 1,051]. No es significativa. SMA gana más por día (t-test p=0,007), pero con un drawdown de −70% frente a −27,5%.

La elección depende de la tolerancia al riesgo:

- **SMA:** más Sharpe puntual y más retorno, pero drawdown profundo.
- **A2:** menos Sharpe puntual, pero drawdown mucho menor y más consistencia.

## 7.6 El holdout confirma la dirección, no la significancia

En 2025-2026 el ranking puntual se mantiene (SMA 0,434 > A2 0,342 > BH −0,134), pero con 609 días los intervalos son gigantes y nada es significativo. El holdout sirve para mostrar que la dirección no se invierte, no para probar superioridad.

## 7.7 La trampa del test t

El test t pareado dice que SMA gana más que A2 (p=0,007). Eso es cierto en promedio, pero **no ajusta por riesgo**. SMA tiene 2,42% de volatilidad diaria; A2, 0,823%. El mayor retorno de SMA es, en parte, compensación por asumir mucho más riesgo. Por eso el test principal es el de Sharpe, no el de retorno medio.

---

# 8. Limitaciones

1. **Sesgo de selección:** A2 fue seleccionada usando parte de los datos (los folds 2021-2024). Sus p-valores son optimistas. El holdout mitiga, pero no elimina el problema.
2. **Multiple testing:** se probaron 6 estrategias y 100 trials por estrategia. Holm corrige las 3 comparaciones, pero no todo el proceso de búsqueda.
3. **Colas gruesas y autocorrelación:** el JK asume iid normal. El bootstrap de bloques lo mitiga, pero no es perfecto.
4. **Frecuencia diaria:** el Sharpe oficial es 4H; la prueba usa diario. El ranking coincide, pero los valores no son idénticos.
5. **Un solo activo:** BTC/USDT. No se puede generalizar a otros mercados.
6. **Holdout corto:** 609 días. La potencia es baja.
7. **Sharpe inestable:** asume media y varianza constantes; en cripto no lo son.
8. **Significancia ≠ relevancia:** un resultado no significativo no prueba que las estrategias sean iguales; solo que no hay evidencia suficiente para distinguirlas.

---

# 9. Conclusión

- **Estadísticamente:** no se puede rechazar que SMA, A2 y BH tengan el mismo Sharpe. Todos los p-valores son mayores que 0,14; los intervalos de confianza incluyen el cero.
- **Económicamente:** los estimadores puntuales favorecen a SMA (1,124), luego A2 (0,826) y luego BH (0,754). La dirección es consistente en el período completo y en el holdout.
- **Para la tesis:** la recomendación de A2 se sostiene por **drawdown y consistencia**, no por un Sharpe estadísticamente superior. SMA se presenta como alternativa agresiva, también con evidencia estadística limitada.
- **Para el jurado:** la frase correcta es "la evidencia es sugestiva, no concluyente". No se debe afirmar que una estrategia es "estadísticamente mejor" con estos datos.

---

# 10. Reproducción

```text
python scripts/run_hypothesis_tests.py    # calcula JK, bootstrap, Holm y t-test
python scripts/make_hypothesis_figs.py    # figura de intervalos
python scripts/md_to_pdf_hipotesis.py     # este documento en PDF
```

Resultados detallados: `docs/tesis_resultados_v3/tablas/hipotesis.json`.

---

# 11. Glosario breve

| Término | Significado |
|---|---|
| **H0** | Hipótesis nula: no hay diferencia |
| **H1** | Hipótesis alternativa: hay diferencia |
| **p-valor** | Probabilidad de ver una diferencia así si H0 fuera cierta |
| **IC 95%** | Rango de valores compatibles con los datos al 95% |
| **Potencia** | Probabilidad de detectar una diferencia cuando existe |
| **Holm** | Corrección de p-valores para comparaciones múltiples |
| **Bootstrap** | Remuestreo para estimar la incertidumbre sin fórmulas |
| **JK** | Test de Jobson-Korkie para diferencias de Sharpe |
| **Significancia estadística** | La diferencia es difícil de explicar por azar |
| **Significancia económica** | La diferencia es lo bastante grande para importar |

---

# 12. Bibliografía

- Jobson, J. D., & Korkie, B. M. (1981). *Performance Hypothesis Testing with the Sharpe and Treynor Measures*. Journal of Finance.
- Memmel, C. (2003). *Performance Hypothesis Testing with the Sharpe Ratio*. Finance Letters.
- Efron, B., & Tibshirani, R. J. (1993). *An Introduction to the Bootstrap*. Chapman & Hall.
- Holm, S. (1979). *A Simple Sequentially Rejective Multiple Test Procedure*. Scandinavian Journal of Statistics.
- Sharpe, W. F. (1966). *Mutual Fund Performance*. Journal of Business.

---

> **Cierre:** la prueba no encuentra diferencias significativas de Sharpe. Eso no invalida la investigación: la obliga a ser honesta. La estrategia conservadora se defiende por su drawdown, no por su Sharpe; la agresiva, por su retorno, no por una superioridad estadística demostrada.
