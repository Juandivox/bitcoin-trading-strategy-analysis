# Resultados v3 (4H, rf=4%, universo normalizado)

- Dataset: `data\processed\btcusdt_4h.parquet` — 19,800 velas, 2017-08-17 04:00:00+00:00 -> 2026-09-01 20:00:00+00:00
- Timeframe: **4h** (P = 2,190 velas/anio)
- Tasa libre de riesgo: **4.00% anual** (0.000018 por vela)
- Costos: 10 bps fee + 5 bps slippage | lag = 1
- Commit: `5881279` | config hash: `7fa9500cd69a0d97`
- Universo: BH, RSI, MACD, SMA, EMA, CCI, E2A_A1, E2A_A2, E2C
- Seleccion: TPE 100 trials | mediana Sharpe OOS folds 2021-2024 | rf=4% | warmup global | 5 trades/fold

## Sharpe por temporada

| Estrategia | C16 | C20 | C24 | FULL |
|---|---:|---:|---:|---:|
| BH | 0.684 | 1.052 | 0.316 | 0.749 |
| RSI | 0.202 | 0.837 | -0.853 | 0.209 |
| MACD | 1.265 | 0.874 | 0.440 | 0.924 |
| SMA | 1.036 | 1.413 | 0.749 | 1.123 |
| EMA | 1.086 | 1.320 | 0.544 | 1.065 |
| CCI | -0.308 | 0.874 | 0.190 | 0.248 |
| E2A_A1 | -2.162 | -1.375 | -1.251 | -1.463 |
| E2A_A2 | 1.003 | 0.680 | 1.327 | 0.872 |
| E2C | 0.184 | -0.279 | -1.063 | -0.262 |

## Operaciones (FULL)

| Estrategia | Trades | Win rate | Profit factor | Retorno medio | Duracion media (velas) |
|---|---:|---:|---:|---:|---:|
| BH | 1 | 100.00% | — | 1677.59% | 19799.0 |
| RSI | 361 | 69.25% | 1.22 | 0.20% | 12.7 |
| MACD | 285 | 37.19% | 1.73 | 1.49% | 35.1 |
| SMA | 66 | 33.33% | 4.41 | 13.23% | 155.3 |
| EMA | 57 | 35.09% | 3.68 | 12.26% | 179.7 |
| CCI | 118 | 75.42% | 1.29 | 0.94% | 95.9 |
| E2A_A1 | 30 | 23.33% | 0.34 | -0.87% | 6.7 |
| E2A_A2 | 39 | 76.92% | 3.17 | 4.11% | 47.2 |
| E2C | 294 | 35.03% | 0.99 | -0.01% | 6.7 |

> Nota: `profit_factor` se calcula POR OPERACION.

## Archivos

- `tablas/metricas_por_periodo.csv` — 9 estrategias x 6 periodos
- `tablas/sensibilidad_rf.csv` — Sharpe para rf = 0%, 3,8%, 4% y 5%
- `figs/v3_fig01..05` — equity FULL, temporadas, drawdown, barras y sensibilidad
- `manifest.json` — commit, hash de config, rf, timeframe, universo y protocolo
- `tablas/tpe_v3.json` — re-seleccion TPE (anexo metodologico)
- `tablas/pso_v3.json` — PSO con rf=4% (anexo, contraejemplo de sobreajuste)
