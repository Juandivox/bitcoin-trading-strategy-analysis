# Binance Data Vision — Guía de descarga

## URLs exactas

Mensual:
```
https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2024-01.zip
https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-2024-01.zip.CHECKSUM
```

Diario:
```
https://data.binance.vision/data/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-2024-01-15.zip
```

Trades / aggTrades:
```
https://data.binance.vision/data/spot/monthly/trades/BTCUSDT/BTCUSDT-trades-2024-01.zip
https://data.binance.vision/data/spot/monthly/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2024-01.zip
```

Estructura local:
```
data/raw/spot/monthly/klines/BTCUSDT/1m/BTCUSDT-1m-*.zip
data/raw/spot/daily/klines/BTCUSDT/1m/BTCUSDT-1m-*.zip
```

## Intervalos disponibles

`1s 1m 3m 5m 15m 30m 1h 2h 4h 6h 8h 12h 1d` — este repo usa `1m` como base y resamplea al resto.

## Rango histórico BTCUSDT

- **Spot BTCUSDT listado:** 2017-08-17
- **Disponibilidad klines 1m:** desde 2017-08-17 (mensuales desde 2017-08, diarios completan huecos)
- **Hasta:** ayer (daily) / mes anterior completo (monthly)
- **Tamaño estimado:** ~100-120 archivos mensuales + ~30 diarios = ~8-12 GB ZIPs -> ~2-3 GB parquet 1m

## Proceso de publicación Binance

- Diarios: al día siguiente ~00:00 UTC
- Mensuales: primeros días del mes siguiente
- Si hoy es 2026-09-01, el mensual 2026-08 puede tardar 1-3 días en aparecer -> el downloader cae a diarios automáticamente y reporta `not_found_404` sin error.

## Checksums

Cada ZIP tiene `.CHECKSUM` con `sha256  filename`. `download.py` lo verifica si `--no-verify` no está activo.
