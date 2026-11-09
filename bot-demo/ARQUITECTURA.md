# ARQUITECTURA — bot-demo

Ejecutor privado en tiempo real para la estrategia E2-A sobre Binance Demo.
Implementa la especificación funcional v2.0 con dos desviaciones documentadas
(ver `docs/ACEPTACION.md`).

## 1. Piezas

```
bot-demo/
  app/
    config.py            # configuración efectiva, destinos DEMO permitidos, fingerprint, secretos por entorno
    contracts.py         # tipos compartidos (RunState, Health, FillRecord, SignalDecision, EquityBreakdown)
    main.py              # supervisor: gates, estados, salud, patrimonio, control, cierre, export
    runner.py            # nodo NautilusTrader (SOLO DATOS) contra Binance DEMO
    cli.py               # CLI del operador (status/pause/resume/close/stop/export)
    strategy/
      e2a.py             # señal E2-A en numpy (equivalencia exacta con la investigación)
      live.py            # Strategy de Nautilus: barras 4H, evaluación, control, estado persistente
    execution/
      rest_executor.py   # órdenes de mercado por REST DEMO: intención→envío→fills→conciliación
    exchange/
      demo_rest.py       # cliente REST firmado (HMAC), filtros, sin reintentos ciegos en envíos
    accounting/
      ledger.py          # lotes FIFO, comisiones por activo, P&L, equity de la prueba
      metrics.py         # retornos diarios UTC, Sharpe/Sortino/Calmar/CAGR/DD, no-calculables con motivo
    supervision/
      state.py           # máquina de estados persistente (pausa sobrevive reinicios)
      lock.py            # escritor único (O_EXCL + heartbeat + PID muerto)
      control.py         # archivo de control atómico CLI→proceso
      health.py          # frescura (vela esperada vs cotización), bloqueo de entradas
      status.py          # estado compartido hilo nodo ↔ supervisor
    audit/
      db.py              # SQLite WAL: señales, intenciones, órdenes, fills, equity, salud, incidentes, trades
      logs.py            # JSONL + consola, con redacción de secretos
    reports/
      export.py          # CSV/JSON/MD con corte, esquema, hashes y escape anti-fórmulas
  config/
    bot.yaml             # configuración de operación
    smoke.yaml           # configuración de pruebas rápidas
  tests/                 # 104 pruebas (ver docs/ACEPTACION.md)
  scripts/
    acceptance_roundtrip.py  # CA-11: compra+venta reales en DEMO
```

## 2. Flujo

```
Binance DEMO (klines WS/REST)                     Binance DEMO (REST privado)
        │                                                  │
        ▼                                                  ▼
  NautilusTrader (solo datos)  ──►  E2ALiveStrategy  ──►  RestExecutor
        │  barras 4H cerradas          señal 0/1            intención→orden→fills
        │  quotes (frescura)           control/pausa        polling + conciliación
        ▼                                                  ▼
  RuntimeStatus  ──►  Supervisor (hilo aparte)  ──►  Ledger + AuditDB + Logger
        salud              gates, estados,                lotes/FIFO, SQLite, JSONL
        frescura           patrimonio, exports            exports CSV/JSON/MD
```

- **Hilo principal**: `node.run()` de Nautilus (la clase es *unsendable* en rc5).
- **Hilo supervisor**: salud cada 15 s, fills cada 10 s, conciliación cada 30 s,
  patrimonio cada 60 s, latido cada 5 min, control cada 5 s.
- **Parada**: `LiveNodeHandle.stop()` desde el supervisor → `node.run()` retorna → export final.

## 3. Estados

`BORRADOR → VALIDANDO → RECONCILIANDO → CALENTANDO → EJECUTANDO ⇄ ENTRADAS_PAUSADAS`
`→ CERRANDO → FINALIZADA | FINALIZADA_CON_RESIDUO`; `DETENIDO` (proceso sin gestionar),
`INTERRUMPIDA` (continuidad invalidada). La bandera de pausa persiste aunque el estado
vuelva a arrancar.

## 4. Garantías del spec implementadas

- Intención **persistida antes** de despachar, con clave idempotente `e2a-<run>-<acción>-<cierre de vela>`.
- Envíos de **un solo intento**: timeout/5xx → `UNKNOWN` + conciliación; nunca reenvío a ciegas.
- Solo **fills confirmados** alteran inventario y costo (idempotencia por `trade_id`).
- Comisiones por activo original (BTC/USDT) sin doble descuento; tercer activo → valoración incompleta declarada.
- Inventario ajeno o descuadres → **pausa + incidente** (nunca liquidación automática).
- Señales con **velas cerradas**; entrada no retroactiva tras caída; salida sí se ejecuta al reconectar.
- Frescura: vela esperada vs cotización por separado; sin datos → bloqueo de entradas.
- Escritor único verificable; pausa persistente; auditoría y exports reproducibles con hashes.

## 5. Operación

- Variante: `strategy_variant: PSO` (o `A2`) en `config/bot.yaml`.
- Presupuesto/entrada: `budget_usdt` / `entry_notional_usdt` (validado contra el saldo demo).
- Pruebas: `python -m pytest tests` (venv del bot) y, con el venv de investigación,
  `python -m pytest bot-demo/tests/test_strategy_equivalence.py` (equivalencia exacta).
- Imagen: `docker compose up -d --build` (un solo contenedor, con volumen persistente para `runs/`).
