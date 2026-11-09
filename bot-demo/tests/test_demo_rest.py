"""Tests de `app.exchange.demo_rest` contra el mock HTTP local (sin red real).

Cubren: firma/ventana, órdenes MARKET con `quoteOrderQty`, filtros y
redondeos, ambigüedad de envíos (timeout/5xx) con un solo intento, rechazos
4xx, reintentos acotados de lecturas, `Retry-After` y `sync_time`.
"""
from __future__ import annotations

import time
from decimal import Decimal

import pytest
import requests

from app.exchange.demo_rest import (
    AmbiguousResult,
    DemoRESTClient,
    DemoRESTError,
    floor_to_step,
    round_price_to_tick,
)
from mock_binance import MockBinanceServer

API_KEY = "demo-key-0123456789abcdef"
API_SECRET = "demo-secret-0123456789abcdef"


@pytest.fixture()
def server():
    srv = MockBinanceServer(
        api_key=API_KEY, api_secret=API_SECRET, symbol="BTCUSDT", start_price="80000.00"
    )
    srv.start()
    try:
        yield srv
    finally:
        srv.stop()


def make_client(server: MockBinanceServer, **overrides) -> DemoRESTClient:
    session = requests.Session()
    session.trust_env = False  # no depender de proxies del entorno
    kwargs = dict(
        base_url=server.base_url,
        api_key=API_KEY,
        api_secret=API_SECRET,
        timeout_s=5.0,
        session=session,
        retry_backoff_s=0.01,
    )
    kwargs.update(overrides)
    return DemoRESTClient(**kwargs)


# 1. firma -------------------------------------------------------------------


def test_firma_correcta_pasa_y_firma_manipulada_da_1022(server):
    client = make_client(server)
    account = client.account()
    assert any(balance["asset"] == "USDT" for balance in account["balances"])

    tampered = make_client(server, api_secret=API_SECRET + "x")
    with pytest.raises(DemoRESTError) as excinfo:
        tampered.account()
    assert excinfo.value.code == -1022
    assert excinfo.value.http_status == 400  # Binance: 400 para firma inválida
    # un 4xx es determinista: no se reintenta
    assert server.count("GET", "/api/v3/account") == 2


# 2. BUY con quote_order_qty -------------------------------------------------


def test_buy_con_quote_order_qty_llena_y_actualiza_balances(server):
    server.fill.price = Decimal("80000.00")
    client = make_client(server)

    result = client.place_market_order("BTCUSDT", "BUY", quote_order_qty=Decimal("1000"))

    assert result["status"] == "FILLED"
    assert result["side"] == "BUY"
    assert result["type"] == "MARKET"
    assert len(result["fills"]) == 1
    fill = result["fills"][0]
    assert Decimal(fill["price"]) == Decimal("80000.00")
    assert Decimal(fill["qty"]) == Decimal("0.0125")
    assert Decimal(fill["commission"]) == Decimal("0.00001")
    assert fill["commissionAsset"] == "BTC"
    assert Decimal(result["executedQty"]) == Decimal("0.0125")
    assert Decimal(result["cummulativeQuoteQty"]) == Decimal("1000")

    assert client.free_balance("USDT") == Decimal("9000")
    assert client.free_balance("BTC") == Decimal("0.01249")
    assert server.order_request_count == 1


# 3. filtros y redondeos -----------------------------------------------------


def test_get_filters_parsea_y_floor_to_step_nunca_sube(server):
    client = make_client(server)
    filters = client.get_filters("BTCUSDT")

    assert filters.symbol == "BTCUSDT"
    assert filters.min_notional == Decimal("5")
    assert filters.step_size == Decimal("0.00001")
    assert filters.tick_size == Decimal("0.01")
    assert filters.min_qty == Decimal("0.00001")
    assert filters.max_qty == Decimal("9000")
    assert filters.max_notional == Decimal("9000000")

    assert floor_to_step(Decimal("0.000019"), Decimal("0.00001")) == Decimal("0.00001")
    cases = [
        ("0.00001", "0.00001", "0.00001"),
        ("0.0000999", "0.00001", "0.00009"),
        ("0.0125", "0.00001", "0.0125"),
        ("1.999", "1", "1"),
        ("0.5", "1", "0"),
        ("-0.000019", "0.00001", "-0.00002"),
    ]
    for value, step, expected in cases:
        got = floor_to_step(Decimal(value), Decimal(step))
        assert got == Decimal(expected), (value, step)
        assert got <= Decimal(value), "floor_to_step jamás debe subir"

    assert round_price_to_tick(Decimal("80000.005"), Decimal("0.01")) == Decimal("80000.01")
    assert round_price_to_tick(Decimal("80000.004"), Decimal("0.01")) == Decimal("80000.00")


# 4. ambigüedad --------------------------------------------------------------


def test_timeout_en_envio_es_ambiguo_y_no_reintenta(server):
    server.order_delay_s = 2.0
    client = make_client(server, timeout_s=1.0)

    with pytest.raises(AmbiguousResult):
        client.place_market_order(
            "BTCUSDT", "BUY", quote_order_qty=Decimal("1000"), client_order_id="amb-1"
        )

    assert server.order_request_count == 1  # exactamente un intento

    recovered = client.query_order("BTCUSDT", client_order_id="amb-1")
    assert recovered["status"] == "FILLED"
    assert recovered["clientOrderId"] == "amb-1"


def test_5xx_en_envio_es_ambiguo_y_no_reintenta(server):
    server.order_http_status = 503
    client = make_client(server)

    with pytest.raises(AmbiguousResult) as excinfo:
        client.place_market_order("BTCUSDT", "BUY", quantity=Decimal("0.001"))

    assert excinfo.value.payload["code"] == -1001
    assert server.order_request_count == 1


def test_timeout_en_cancelacion_es_ambiguo_y_recuperable(server):
    server.fill.ratio = Decimal("0.5")
    client = make_client(server)
    placed = client.place_market_order("BTCUSDT", "BUY", quantity=Decimal("0.01"))

    server.order_delay_s = 2.0
    slow = make_client(server, timeout_s=1.0)
    with pytest.raises(AmbiguousResult):
        slow.cancel_order("BTCUSDT", order_id=placed["orderId"])

    assert server.cancel_request_count == 1
    recovered = slow.query_order("BTCUSDT", order_id=placed["orderId"])
    assert recovered["status"] == "CANCELED"


# 5. rechazo 4xx -------------------------------------------------------------


def test_order_error_code_se_expone_como_demorest_error(server):
    server.order_error_code = -2010
    server.order_error_msg = "Order would immediately match and take."
    client = make_client(server)

    with pytest.raises(DemoRESTError) as excinfo:
        client.place_market_order("BTCUSDT", "SELL", quantity=Decimal("0.001"))

    assert excinfo.value.code == -2010
    assert excinfo.value.http_status == 400
    assert "immediately match" in excinfo.value.message
    assert server.order_request_count == 1


# 6. lecturas ----------------------------------------------------------------


def test_lecturas_reintentan_500_y_luego_triunfan(server):
    client = make_client(server)

    server.read_fail_count = 2
    account = client.account()
    assert "balances" in account
    assert server.count("GET", "/api/v3/account") == 3

    server.read_fail_count = 10_000
    with pytest.raises(DemoRESTError):
        client.account()
    assert server.count("GET", "/api/v3/account") == 3 + 1 + client.max_read_retries


def test_lectura_429_respeta_retry_after(server):
    client = make_client(server)
    server.read_fail_count = 1
    server.read_fail_status = 429
    server.read_fail_retry_after_s = 0.25

    started = time.monotonic()
    assert "balances" in client.account()
    elapsed = time.monotonic() - started

    assert elapsed >= 0.2, f"no respetó Retry-After (elapsed={elapsed:.3f}s)"
    assert server.count("GET", "/api/v3/account") == 2


def test_lectura_4xx_no_se_reintenta(server):
    client = make_client(server)
    with pytest.raises(DemoRESTError) as excinfo:
        client.get_filters("ETHUSDT")
    assert excinfo.value.code == -1121
    assert server.count("GET", "/api/v3/exchangeInfo") == 1


# 7. reloj -------------------------------------------------------------------


def test_sync_time_corrige_reloj_desviado(server):
    client = make_client(server)
    client._time_source = lambda: time.time() + 30.0  # reloj local 30 s adelantado

    with pytest.raises(DemoRESTError) as excinfo:
        client.account()
    assert excinfo.value.code == -1021

    offset = client.sync_time()
    assert -40_000 < offset < -20_000
    assert client.clock_offset_ms == offset

    assert "balances" in client.account()  # ya firma dentro de la ventana


# extras: fill parcial, cancelación, klines/myTrades, validación --------------


def test_fill_parcial_queda_abierta_y_cancelable(server):
    server.fill.ratio = Decimal("0.5")
    client = make_client(server)

    result = client.place_market_order("BTCUSDT", "BUY", quantity=Decimal("0.01"))
    assert result["status"] == "PARTIALLY_FILLED"
    assert Decimal(result["origQty"]) == Decimal("0.01")
    assert Decimal(result["executedQty"]) == Decimal("0.005")

    order_id = result["orderId"]
    open_orders = client.open_orders("BTCUSDT")
    assert [order["orderId"] for order in open_orders] == [order_id]

    canceled = client.cancel_order("BTCUSDT", order_id=order_id)
    assert canceled["status"] == "CANCELED"
    assert client.open_orders("BTCUSDT") == []

    with pytest.raises(DemoRESTError) as excinfo:
        client.cancel_order("BTCUSDT", order_id=order_id)
    assert excinfo.value.code == -2011
    assert server.cancel_request_count == 2


def test_klines_deterministas_y_my_trades(server):
    client = make_client(server)

    klines = client.klines("BTCUSDT", "4h", limit=600)
    assert len(klines) == 600
    assert all(len(row) == 12 for row in klines)
    times = [row[0] for row in klines]
    assert times == sorted(times)
    assert client.klines("BTCUSDT", "4h", limit=600) == klines  # deterministas
    assert len(client.klines("BTCUSDT", "4h", limit=10)) == 10
    filtered = client.klines("BTCUSDT", "4h", limit=600, end_time_ms=times[9])
    assert [row[0] for row in filtered] == times[:10]

    result = client.place_market_order("BTCUSDT", "BUY", quantity=Decimal("0.01"))
    trades = client.my_trades("BTCUSDT")
    assert len(trades) == 1
    assert trades[0]["orderId"] == result["orderId"]
    assert trades[0]["isBuyer"] is True
    assert Decimal(trades[0]["qty"]) == Decimal("0.01")


def test_validacion_local_de_argumentos(server):
    client = make_client(server)

    with pytest.raises(ValueError):
        client.place_market_order("BTCUSDT", "BUY")  # sin quantity ni quote
    with pytest.raises(ValueError):
        client.place_market_order("BTCUSDT", "BUY", quantity=Decimal("1"), quote_order_qty=Decimal("1"))
    with pytest.raises(ValueError):
        client.place_market_order("BTCUSDT", "HOLD", quantity=Decimal("1"))
    with pytest.raises(ValueError):
        client.query_order("BTCUSDT")
    with pytest.raises(ValueError):
        client.query_order("BTCUSDT", client_order_id="a", order_id=1)
    with pytest.raises(ValueError):
        floor_to_step(Decimal("1"), Decimal("0"))
    with pytest.raises(ValueError):
        round_price_to_tick(Decimal("1"), Decimal("0"))

    assert server.order_request_count == 0
