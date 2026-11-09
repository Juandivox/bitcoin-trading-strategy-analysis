"""Prueba de aceptación CA-11 (autorizada): compra + venta controladas en Binance DEMO.

Usa la MISMA capa de ejecución del bot (RestExecutor) contra la cuenta DEMO real:
compra ~25 USDT de BTC a mercado, espera fills confirmados, vende la cantidad neta y
concilia contra el exchange. Deja evidencia en runs/<run_id>/ (auditoría + export).

Uso:  python scripts/acceptance_roundtrip.py [--quote 25]
"""
from __future__ import annotations

import argparse
import sys
import time
from decimal import Decimal
from pathlib import Path

BOT_ROOT = Path(__file__).resolve().parents[1]
if str(BOT_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_ROOT))

from app.accounting.ledger import Ledger  # noqa: E402
from app.audit.db import AuditDB  # noqa: E402
from app.audit.logs import Logger  # noqa: E402
from app.config import BotConfig, Secrets  # noqa: E402
from app.exchange.demo_rest import DemoRESTClient, floor_to_step  # noqa: E402
from app.execution.rest_executor import RestExecutor  # noqa: E402
from app.main import load_env_file  # noqa: E402
from app.reports.export import export_run  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quote", default="25", help="notional de la compra en USDT")
    parser.add_argument("--config", default=str(BOT_ROOT / "config" / "bot.yaml"))
    args = parser.parse_args()

    load_env_file(BOT_ROOT / ".env")
    run_id = f"acceptance-roundtrip-{time.strftime('%Y%m%d-%H%M%S')}"
    cfg = BotConfig.load(args.config, run_id=run_id)
    secrets = Secrets.from_env()
    cfg.ensure_dirs()

    logger = Logger("acceptance", jsonl_path=cfg.logs_dir / "acceptance.jsonl",
                    secrets=[secrets.api_key, secrets.api_secret])
    audit = AuditDB(cfg.db_path)
    ledger = Ledger(cfg.symbol)
    rest = DemoRESTClient(base_url=cfg.demo_rest_base, api_key=secrets.api_key, api_secret=secrets.api_secret)
    executor = RestExecutor(cfg, rest, audit, logger, ledger)

    print(f"[aceptación] run_id={run_id} destino={cfg.demo_rest_base}")
    offset = rest.sync_time()
    print(f"[aceptación] reloj: offset={offset} ms")
    filters = rest.get_filters(cfg.symbol)
    print(f"[aceptación] filtros: step={filters.step_size} min_notional={filters.min_notional}")

    account = rest.account()
    balances = {b["asset"]: b for b in account.get("balances", [])}
    usdt0 = Decimal(str(balances.get("USDT", {}).get("free", "0")))
    btc0 = Decimal(str(balances.get("BTC", {}).get("free", "0")))
    print(f"[aceptación] saldo inicial: USDT libre={usdt0} BTC libre={btc0}")

    quote = Decimal(args.quote)
    if quote < filters.min_notional:
        print(f"[aceptación] FALLO: {quote} < min_notional {filters.min_notional}")
        return 1
    if usdt0 < quote:
        print(f"[aceptación] FALLO: USDT libre {usdt0} < {quote}")
        return 1

    bar_close_ms = int(time.time() * 1000)
    print(f"[aceptación] COMPRA a mercado por {quote} USDT ...")
    status = executor.submit_market(
        action="ACCEPTANCE_BUY", side="BUY", bar_close_ms=bar_close_ms,
        quote_notional=quote, price_estimate=rest.bid_price(cfg.symbol),
    )
    print(f"[aceptación] estado compra: {status}")
    if status not in ("FILLED", "PARTIALLY_FILLED"):
        executor.reconcile_open_intents()
        executor.poll_fills()
    for _ in range(10):
        if ledger.base_qty() > 0:
            break
        executor.poll_fills()
        time.sleep(1)
    print(f"[aceptación] inventario tras compra: {ledger.base_qty()} BTC")
    if ledger.base_qty() <= 0:
        print("[aceptación] FALLO: la compra no produjo inventario confirmado")
        audit.close()
        return 1

    sell_qty = floor_to_step(ledger.base_qty(), filters.step_size)
    bid = rest.bid_price(cfg.symbol)
    if sell_qty * bid < filters.min_notional:
        print(f"[aceptación] FALLO: venta {sell_qty} BTC < min_notional ({sell_qty * bid} USDT)")
        audit.close()
        return 1
    print(f"[aceptación] VENTA a mercado de {sell_qty} BTC (bid {bid}) ...")
    status = executor.submit_market(
        action="ACCEPTANCE_SELL", side="SELL", bar_close_ms=bar_close_ms + 1,
        quantity=sell_qty, price_estimate=bid,
    )
    print(f"[aceptación] estado venta: {status}")
    for _ in range(15):
        if ledger.base_qty() <= 0:
            break
        executor.poll_fills()
        time.sleep(1)
    executor.poll_fills()

    account = rest.account()
    balances = {b["asset"]: b for b in account.get("balances", [])}
    usdt1 = Decimal(str(balances.get("USDT", {}).get("free", "0")))
    btc1 = Decimal(str(balances.get("BTC", {}).get("free", "0")))
    residual = btc1 - btc0
    equity = ledger.equity(
        budget_usdt=Decimal("100"),
        cash_free_usdt=Decimal("100") + ledger.quote_cash(),
        cash_reserved_usdt=Decimal("0"),
        base_price_usdt=bid,
    )

    print()
    print("========== EVIDENCIA CA-11 ==========")
    print(f"USDT libre:  {usdt0} -> {usdt1}  (delta {usdt1 - usdt0})")
    print(f"BTC libre:   {btc0} -> {btc1}  (delta {residual})")
    print(f"inventario ledger: {ledger.base_qty()} BTC")
    print(f"P&L realizado: {ledger.realized_pnl()} USDT (comisiones incluidas)")
    print(f"comisiones por activo: { {k: str(v) for k, v in ledger.fees_by_asset().items()} }")
    print(f"equity de la prueba (base 100 USDT): {equity.equity_usdt} completo={equity.complete}")
    intents = audit.fetch("order_intents")
    for row in intents:
        print(f"intención {row['key']}: status={row['status']} order_id={row['order_id']}")
    fills = audit.fetch("fills")
    print(f"fills confirmados: {len(fills)}")
    for row in fills:
        print(f"  trade {row['trade_id']}: {row['side']} {row['qty']} @ {row['price']} "
              f"comisión {row['commission']} {row['commission_asset']}")

    ok = (
        len(fills) >= 2
        and all(r["status"] in ("FILLED", "PARTIALLY_FILLED") for r in intents)
        and abs(ledger.base_qty()) < filters.step_size
    )
    manifest = export_run(audit, cfg, cfg.exports_dir, state="ACEPTACION", health="N/A")
    print(f"export: {cfg.exports_dir / 'run_manifest.json'} (id {manifest['export_id']})")
    audit.close()
    logger.close()
    print("RESULTADO:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
