# OPERACIÓN — Bot E2-A (Binance DEMO)

Bot en tiempo real que ejecuta la estrategia **E2-A PSO** (la ganadora del capítulo de
resultados) sobre **BTC/USDT en velas de 4 horas**, operando en **Binance Demo**
(dinero ficticio, órdenes reales del entorno demo).

- Entradas y salidas: órdenes de mercado.
- Solo compras (long-only), sin apalancamiento, sin cortos.
- Presupuesto de la prueba: **4.900 USDT** de la cuenta demo · 1.000 USDT por entrada · máx. 2 posiciones.
- El bot NO necesita pantalla ni panel: todo se ve en el log.

---

## 1. Requisitos

- Docker (Docker Desktop en Windows/macOS, o Docker Engine en Linux). Nada más.
- Conexión a internet.
- Las credenciales de la cuenta demo ya vienen incluidas en la imagen (`.env`).

## 2. Puesta en marcha (3 comandos)

**Opción A — imagen entregada (`e2a-demo-bot-2.0.2.tar`):**

```bash
docker load -i e2a-demo-bot-2.0.2.tar
mkdir -p runs
docker run -d --name e2a-demo-bot --restart unless-stopped --stop-timeout 90 \
  -v "$PWD/runs:/bot/runs" e2a-demo-bot:2.0.2
```

**Opción B — desde el código (necesita internet la primera vez, ~5 min de build):**

```bash
cd bot-demo
docker compose up -d --build      # levanta el bot con volumen persistente (un solo contenedor)
```

En ambos casos, a los ~30 segundos el log debe mostrar `estado=EJECUTANDO`.

## 3. ¿Cómo sé que está funcionando?

```bash
docker logs -f e2a-demo-bot          # flujo en vivo (Ctrl+C no lo detiene)
docker logs --tail 50 e2a-demo-bot   # últimas 50 líneas
```

Lo que verás (y lo que significa):

| Línea | Significado |
|---|---|
| `gate_ok paso=...` | Validaciones de arranque superadas (reloj, cuenta, filtros, datos, saldo). |
| `estado estado=EJECUTANDO` | El bot está operando (no es un modo de prueba). |
| `latido ... barras=600 senal_objetivo=0 ...` | **Cada 5 minutos**: sigue vivo; `senal_objetivo` 0=plano, 1=debe estar largo. |
| `senal_evaluada ... accion=HOLD cci=... sma_f=... sma_s=... vol_z=...` | **Cada 4 horas** (al cerrar cada vela): valores de los indicadores y decisión. |
| `patrimonio equity=...` | Cada minuto: valor de la prueba. |
| `fill_confirmado ...` | Se ejecutó una compra o venta (con precio y comisión reales del exchange). |
| `operacion_cerrada pnl=...` | Se cerró una operación completa con su resultado. |

> **Importante y normal:** la estrategia opera poco (≈4–8 veces por año, por diseño).
> Es esperable pasar **semanas sin operaciones**: mientras el `latido` siga apareciendo
> y `salud=SALUDABLE`, todo está bien. El bot solo entra cuando hay cruce de CCI con
> tendencia y volumen confirmados.

## 4. Comandos del operador

```bash
docker exec e2a-demo-bot python -m app.cli status              # resumen: estado, salud, equity, última señal
docker exec e2a-demo-bot python -m app.cli pause --reason "..."  # pausa entradas (sigue evaluando salidas)
docker exec e2a-demo-bot python -m app.cli resume              # reanuda entradas
docker exec e2a-demo-bot python -m app.cli close-position      # vende el inventario del bot (si hay)
docker exec e2a-demo-bot python -m app.cli stop                # parada ordenada del proceso
docker exec e2a-demo-bot python -m app.cli export              # exporta CSV/JSON/MD a runs/<id>/exports/
```

La **pausa es persistente**: si reinicias el contenedor, el bot arranca en
`ENTRADAS_PAUSADAS` hasta que hagas `resume`. Está pensado así (spec RF-REC-06).

## 5. Dónde queda la evidencia

Todo en `runs/e2a-demo-001/` (volumen montado):

```
runs/e2a-demo-001/
  audit.sqlite          # auditoría completa (señales, intenciones, órdenes, fills, salud, incidentes)
  state.json            # estado operativo + historial de transiciones
  control.json          # canal de comandos del CLI
  logs/bot.jsonl        # log estructurado (una línea JSON por evento)
  exports/              # orders.csv, fills.csv, trades.csv, equity.csv, signals.csv, events.csv,
                        # metrics.json, summary.md, run_manifest.json (con hashes)
  run_manifest.json     # identidad de la prueba: configuración, hashes, versiones, destinos
```

Para abrir la auditoría: `sqlite3 runs/e2a-demo-001/audit.sqlite` (o cualquier visor SQLite).

## 6. Avisos importantes

1. **Es DEMO**: el dinero es ficticio y las órdenes se cursan en `demo-api.binance.com`.
   El bot rechaza cualquier configuración que no sea un host oficial de Demo.
2. **Una sola instancia por cuenta**: dos bots en la misma cuenta demo se estorban.
   Si arrancas un segundo, se niega a operar (`escritor_unico_ocupado`) — es correcto.
3. **No edites `.env`** salvo para cambiar `BOT_RUN_ID` (eso inicia una prueba nueva y
   deja la anterior congelada). Si la clave API tuviera restricción por IP, quítala en
   la administración de API de Binance Demo.
4. **Si detienes con `docker stop`**, el bot cierra ordenadamente (puede tardar ~20 s).
   Usa `--stop-timeout 90` (ya está en `compose.yaml`).
5. **Errores visibles**: si la salud pasa a `DATOS_DEGRADADOS`, `SIN_CONEXION` o
   `ESTADO_INCIERTO`, el bot **bloquea entradas nuevas** y lo deja en el log. No sigue
   operando a ciegas.
6. La primera operación puede tardar semanas (ver §3). No es un fallo.

## 7. Solución de problemas

| Síntoma | Causa probable | Acción |
|---|---|---|
| `code=-2015` / `API-key` | Clave restringida por IP o inválida | Quitar restricción de IP en Binance Demo → API Management |
| `escritor_unico_ocupado` | Ya hay otro proceso con la misma prueba | `docker ps`; detén el duplicado |
| `gate_de_arranque_fallido` | Reloj desviado, saldo insuficiente, etc. | El log dice el motivo exacto; corregir y reiniciar |
| `SIN_CONEXION` persistente | Red/DNS del contenedor | `docker restart e2a-demo-bot` |
| No aparece nada nuevo | Frecuencia real de la estrategia (4H) | Esperar al cierre de vela; mirar el `latido` |
