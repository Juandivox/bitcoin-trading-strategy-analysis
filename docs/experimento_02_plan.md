# Experimento 02 - Resultados Completos
Fecha: 2026-09-02T00:59:13.569003  |  TIMEFRAME=4h  |  Fees 10bps+5bps = 15bps por lado / 30bps round trip  |  Long-only, lag 1  |  Capital 10,000
Datos: 2017-08-17 04:00:00+00:00 -> 2026-09-01 20:00:00+00:00 (19,800 velas 4h)

## Mejor Estrategia
**Ganador Sharpe (pooled): SMA** | **Ganador Calmar: SMA**
- Buy & Hold: Sharpe 0.81 CAGR 37.5% MaxDD -83.9%
- SMA: Sharpe 1.24 CAGR 60.0% MaxDD -74.0%
- E2-A: Sharpe 1.14 CAGR 17.1% MaxDD -27.9%

## E2-A 150 trials - Median OOS Fold Sharpe vs Pooled OOS Sharpe
- Trials 150 | Median OOS Fold Sharpe (TPE objetivo): 2.045
- Best params: `{'cci_period': 58, 'cci_entry': -3, 'cci_exit': 186, 'sma_fast': 18, 'sma_slow': 221, 'vol_window': 40, 'vol_z_thr': 0.5815632644010449, 'atr_period': 28, 'atr_k': 2.444531512139522}`
- Params cerca limite: CCI 58/10-60, entry -3, exit 186, ATR 28 -> proponer E2-A.2 con rangos expandidos
- SMA slow 221 converge con SMA solo 228 (~36d) -> region estable 220-230

## E2-B Trading (XGB vs RF vs LGB)
- XGB bal_acc 0.398 LogLoss 0.895 Brier 0.147 (mejor proba) vs RF 0.430/1.038/0.164
- Trading: thr P(Long)>0.60 optimizado en inner val, variantes P(up)-P(down) y meta-labeling. Ganador por Sharpe trading, no accuracy.

## E2-C
- SMA=regimen, MACD=trigger, RSI=filtro <OB. TPE vs NSGA-II 80 trials.

## Benchmarks Normalizados (10k)
| Estrategia | Initial | Final | Total Return | CAGR | Sharpe | MaxDD |
|---|---|---|---|---|---|---|
| Buy & Hold | 10,000 | 178021 | 1680.2% | - | - | - |

## Halvings regimen
| Estrategia | 2017-20 | 2020-24 | 2024- |
| SMA |  |  |  |

## Walk-Forward
- Outer IS 3y->OOS 1y + HOLDOUT development. ATR 14/k2.0 comun Caso A, 02b optimiza ATR. Fees 15bps por lado.
    System    Sharpe  CAGR Net     MaxDD       PF  Trades  Exposure OOS positive folds
Buy & Hold  0.807818  0.375022 -0.839060      NaN       0  1.000000                  -
       RSI  0.432336  0.096921 -0.479461 1.068814     164  0.214596                3/4
       SMA  1.243989  0.600454 -0.739633 1.126688     109  0.518182                3/4
      E2-A  1.143669  0.170846 -0.279268 1.277086      39  0.092929                3/4
        RF  0.000000  0.000000  0.000000 0.000000       0  0.000000              full*
       XGB -1.071609 -0.031517 -0.275460 0.457131      81  0.005758              full*
       LGB -0.738561 -0.079702 -0.593812 0.723235     300  0.022627              full*
  E2-C TPE  0.819864  0.177071 -0.320499 1.153598     234  0.143737                3/4