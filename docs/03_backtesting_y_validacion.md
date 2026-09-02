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
Implementado en `src/models/training.py:train_predict`.

### 3) Walk-forward rolling (alternativa)
Ventana deslizante de N años (ej. 3 años train -> 1 año test).

## Backtester — qué incluye y qué no

Incluye (obligatorio para ser creíble):
- Fees (0.10% taker) + slippage (5 bps o ATR-based)
- Turnover y costos acumulados
- Lag de ejecución (1 barra)
- Métricas: Sharpe, Sortino, Calmar, CAGR, max DD, win rate, profit factor, turnover, exposure

No incluye (futuro):
- Order book / market impact no lineal
- Funding (spot no aplica; para futuros sí)
- Latencia real

## Métricas — definiciones

- **Sharpe:** `mean(excess_ret)/std(excess_ret)*sqrt(P)` , P=525600 para 1m
- **Sortino:** igual pero std solo downside
- **Max DD:** `(equity - cummax(equity))/cummax(equity)` mínimo
- **Calmar:** `CAGR / |MaxDD|`
- **CAGR:** `(equity_final/equity_inicial)^(1/years)-1`
- **Profit factor:** `sum(gains)/sum(|losses|)`
- **Turnover:** `sum(|position.diff|)`

## Separación ML / Estrategia

```
Modelo predictivo:  X -> y_hat (expected_return)
Regla de trading:   y_hat > +th -> LONG, y_hat < -th -> SHORT, else FLAT
Backtest:           signal -> position(lag) -> PnL - costos -> métricas
Optimización:       busca threshold y params que maximicen Sharpe OOS (no in-sample)
```

Nunca optimizar el modelo mirando el test. El test solo se evalúa una vez.
