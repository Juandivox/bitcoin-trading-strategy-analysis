# ACEPTACIÓN — evidencia de pruebas (spec v2.0)

Fecha de verificación: **2026-09-23/24** · Equipo: Windows 11 + Docker Desktop 29.7.2 ·
Cuenta: Binance Demo (SPOT, HMAC) · Estrategia: **E2-A PSO** (BTC/USDT, 4H, long-only).

**Veredicto:** el producto ejecuta la estrategia en tiempo real contra Binance Demo,
con órdenes reales del entorno demo verificadas end-to-end (compra + venta), auditoría,
conciliación, estados, pausa persistente, exports y parada ordenada. Las pruebas
automatizadas suman **104** (92 en el entorno del bot + 12 de equivalencia con la
investigación). Quedan pendientes declarados al final.

---

## 1. Etapa A — viabilidad del adaptador (resultado)

| Elemento | Resultado verificado |
|---|---|
| Versión fijada | `nautilus_trader==2.0.0rc5` (única línea con `BinanceEnvironment.DEMO`; la estable 1.231.0 no la tiene) |
| Entorno | `BinanceEnvironment.DEMO` + `spot_market_data_mode=Json`; hosts oficiales `demo-api.binance.com`, `demo-stream.binance.com` |
| Datos | Conecta y carga 599 velas 4H históricas + quotes en vivo desde Demo |
| Autenticación de cuenta | `GET /api/v3/account` OK (`canTrade=true`, `permissions=[SPOT]`) |
| **Hallazgo 1** | El WS API privado de Demo **rechaza claves HMAC** (`code=-2028`); el cliente de ejecución de Nautilus no puede conectar el canal privado con las claves de la cuenta |
| **Hallazgo 2** | `use_ws_trading=False` no evita el requisito del canal privado en Spot |
| Decisión | NautilusTrader queda como **motor de datos/señales**; la ejecución va por **REST propio** (HMAC), verificado con órdenes reales. Desviación documentada (§6) |
| Sin fallback silencioso | No se usó dry-run, Testnet ni producción: todo ocurre en Demo |

## 2. Pruebas automatizadas

```
Entorno del bot (bot-demo/.venv, Python 3.13.14):
  92 passed, 1 skipped in 6.08s        (tests/: estrategia, REST+mock, ledger, métricas, supervisión, integración)
Entorno de investigación (repo .venv, con polars):
  12 passed in 6.18s                   (test_strategy_equivalence.py)
```

Cobertura destacada:

- **Equivalencia exacta** de la señal numpy del bot vs. la implementación de investigación
  (`signal_e2a_long` polars) sobre **19.800 velas reales**, ambas variantes (PSO y A2),
  incluyendo prueba incremental con ventanas móviles y bordes de calentamiento.
- **Fixtures económicos del spec §18** (comisión en quote y en activo base) con valores
  exactos `Decimal("97.90")` / `Decimal("97.8011")` y sin doble descuento.
- **Cliente REST**: firma HMAC, `-1022` con firma manipulada, `floor_to_step` nunca hacia
  arriba, **un solo intento** en envíos (contador del mock), `AmbiguousResult` + recuperación
  por `query_order`, `-2010`, reintentos acotados de lecturas, desfase de reloj.
- **Supervisión**: transiciones válidas/ inválidas, pausa que sobrevive reinicios,
  control file tolerante a corrupción, frescura (vela de 4H no obsoleta por falta de cierre
  reciente), `should_block_entries`.
- **Integración del supervisor** con exchange simulado: gates, residuo declarado, inventario
  ajeno → pausa + incidente, recuperación de fills tras “reinicio”, snapshot de patrimonio,
  control pause/resume/export, segundo escritor rechazado (exit 75), corrida completa con
  parada limpia.

## 3. CA-11 — compra y venta reales en DEMO (autorizada)

Evidencia de `scripts/acceptance_roundtrip.py` (capa de ejecución del bot):

```
COMPRA 25 USDT → FILLED  order_id=67301498057  0.00029000 BTC @ 84272.01  comisión 0.00000029 BTC
VENTA neta     → FILLED  order_id=67301501219  0.00028000 BTC @ 84272.00  comisión 0.02359616 USDT
USDT libre: 5000.00000000 → 4999.13368094
BTC libre:  0 → 0.00000971 (residuo bajo el step 0.00001, declarado y excluido)
P&L realizado: -0.04721874 USDT (solo comisiones)   ·   equity (base 100): 99.95196206
comisiones por activo: {BTC: 0.00000029, USDT: 0.02359616}
RESULTADO: PASS
```

## 4. Verificación en Docker (imagen `e2a-demo-bot:2.0.0`, 563 MB)

| Prueba | Resultado |
|---|---|
| `docker compose up -d --build` (un solo contenedor) | Contenedor `EJECUTANDO`, `salud=SALUDABLE`, 600 velas, señal evaluada |
| Log de arranque | gates OK (reloj 0.75 s, cuenta, filtros step 0.00001 / min 5 USDT, datos, persistencia, órdenes ajenas, presupuesto) |
| `senal_evaluada` | `HOLD objetivo=0 cci=-89.12 sma_f=83817.45 sma_s=77746.55 vol_z=-0.7981` |
| Residuo de la cuenta | 0.00000971 BTC declarado y excluido del presupuesto |
| Trades ajenos (histórico de la cuenta) | Ignorados y registrados como `trade_ajeno_ignorado` |
| CLI `status/pause/resume` | `ack` correcto; transiciones visibles en `state.json` |
| `docker compose stop` | SIGTERM → nodo detenido → `estado=DETENIDO` → `export_final` (9 archivos) → **exit 0** |
| Reinicio con el mismo `run_id` | `prueba_existente_reanudada`; la auditoría continúa (misma prueba) |
| Reinicio con pausa previa | Arranca en `ENTRADAS_PAUSADAS` (“arranque con pausa persistida”) — RF-REC-06 |

## 5. Criterios de aceptación del spec

Cubiertos con prueba o evidencia: CA-01 (versión fijada), CA-02 (hosts DEMO únicos;
cualquier otro destino se rechaza al cargar la configuración), CA-03 (credenciales
obligatorias y validadas sin filtrar secretos), CA-04 (auth + lectura de saldo),
CA-05 (presupuesto > disponible ⇒ no arranca), CA-06 (inventario/órdenes ajenas ⇒
conflicto visible + pausa, sin liquidación), CA-07/CA-08/CA-09 (fuente Demo, calentamiento,
calidad y frescura), CA-10 (equivalencia), CA-11 (compra/venta reales),
CA-13/CA-14 (fills parciales/duplicados), CA-15/CA-16 (ambigüedad y recuperación),
CA-17 (filtros/mínimos sin aumentar importe), CA-18/CA-19 (comisiones por activo),
CA-20/CA-21 (pausa con posición; sin stops inventados), CA-22/CA-23 (fills durante caída;
sin entradas retroactivas), CA-25/CA-26/CA-27 (cierre, residuo, parada),
CA-28/CA-29 (reinicio misma prueba; segundo proceso rechazado), CA-31 (cambio de
configuración ⇒ huella distinta en manifiesto), CA-32 (fallo de persistencia ⇒ bloqueo),
CA-34/CA-35/CA-36 (exportación, métricas no calculables, cobertura).

**Pendientes declarados:** CA-12 (validación con endpoint `/order/test` — no aplica a
órdenes de mercado ejecutadas), CA-24 (pérdida del canal privado: no hay canal privado;
se cubre con el estado de conciliación degradada), CA-30 (reset de Demo: se detecta como
discrepancia de inventario ⇒ incidente), CA-33 (restauración de backup antiguo: guía en
`OPERACION.md`, no automatizado), CA-37 (inspección de red/logs: los logs se redactan y
los destinos se validan en código), **CA-38 (prueba continua de 72 h)**: no ejecutada;
recomendada antes de la evaluación definitiva.

## 6. Desviaciones documentadas respecto al spec v2.0

1. **Ejecución por REST propio en lugar del cliente de ejecución de NautilusTrader.**
   Causa: el WS API privado de Binance Demo rechaza HMAC (`-2028`) y la cuenta usa HMAC;
   la alternativa era crear claves Ed25519 (acción manual del usuario) — se optó por REST
   tras consulta. Se conservan todas las garantías del spec (intención previa, sin reintentos
   ciegos, fills confirmados, conciliación) y NautilusTrader sigue siendo el motor de
   datos/señales. Ruta de mejora: crear una API key Ed25519 y reactivar
   `BinanceExecutionClient` (el código del nodo ya está preparado para añadirlo).
2. **Sin Redis (eliminado en la v2.1 del spec).** rc5 no expone backend Redis de caché
   en Python y el contenedor quedaba sin uso (0 claves, ninguna referencia en el código),
   así que se retiró del stack. La persistencia efectiva es el volumen (`audit.sqlite` +
   `state.json` + `strategy_state.json`) y la conciliación de arranque contra el exchange;
   el ensayo de reinicio (§4) demuestra la recuperación sin Redis.
3. **Sin canal privado en tiempo real.** Los fills se confirman por polling REST (10 s) y
   conciliación (30 s); para una estrategia de 4 h no tiene impacto práctico. La salud
   degrada a `ESTADO_INCIERTO` si la conciliación falla.

## 7. Reproducir la aceptación

```bash
cd bot-demo
docker compose up -d --build                 # o: docker load + docker run (OPERACION.md)
docker logs -f e2a-demo-bot                  # observar gates → EJECUTANDO → latido
python -m app.cli --runs-dir runs status     # (con el venv del bot) estado y salud
python scripts/acceptance_roundtrip.py --quote 25   # CA-11 (coloca órdenes demo reales)
python -m pytest tests -q                    # 92 pruebas del bot
# y con el venv de investigación:
python -m pytest bot-demo/tests/test_strategy_equivalence.py -q   # 12 pruebas de equivalencia
```
