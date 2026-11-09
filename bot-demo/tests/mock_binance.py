"""Servidor HTTP local que imita Binance Spot DEMO (solo stdlib).

Permite testear ``app.exchange.demo_rest`` sin red ni credenciales reales:

* verifica ``X-MBX-APIKEY`` (-2015), HMAC-SHA256 (-1022) y la ventana
  ``recvWindow`` (-1021);
* ``POST /api/v3/order`` MARKET llena de forma configurable (precio, cantidad,
  comisión, activo de comisión y **fill parcial**) y actualiza balances;
* registra ``myTrades`` y órdenes abiertas, y expone contadores de peticiones
  para comprobar que un envío ambiguo **no** se reintenta;
* permite inyectar fallos de lectura (5xx/429 con ``Retry-After``) y errores de
  orden (``order_error_code``/``order_http_status``).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import sys
import threading
import time
from dataclasses import dataclass
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

__all__ = ["FillConfig", "MockBinanceServer"]

HOUR_MS = 3_600_000
BAR_MS = 4 * HOUR_MS
KLINE_COUNT = 600
STEP = Decimal("0.00001")
TICK = Decimal("0.01")
BASE_OPEN_MS = 1_600_000_000_000 // BAR_MS * BAR_MS


@dataclass
class FillConfig:
    """Configuración del fill de una orden MARKET.

    ``price=None`` usa el cierre de la última vela; ``qty=None`` deriva la
    cantidad del pedido (``quantity`` o ``quoteOrderQty``); ``ratio`` en
    ``(0, 1]`` permite fills parciales (``ratio < 1`` deja la orden abierta).
    """

    price: Decimal | None = None
    qty: Decimal | None = None
    commission: Decimal = Decimal("0.00001")
    commission_asset: str | None = None
    ratio: Decimal = Decimal("1")


class _MockError(Exception):
    def __init__(self, code: int, msg: str, status: int = 400) -> None:
        super().__init__(msg)
        self.code = code
        self.msg = msg
        self.status = status


def _now_ms() -> int:
    return int(time.time() * 1000)


def _one(params: dict[str, list[str]], key: str) -> str | None:
    values = params.get(key)
    return values[-1] if values else None


def _floor_step(value: Decimal, step: Decimal = STEP) -> Decimal:
    return (value / step).to_integral_value(rounding=ROUND_FLOOR) * step


def _build_klines(start_price: Decimal) -> list[list[Any]]:
    """600 velas 4 h deterministas que terminan en el período 4 h actual (misma serie en cada llamada)."""
    price = start_price
    base_open_ms = (int(time.time() * 1000) // BAR_MS) * BAR_MS - KLINE_COUNT * BAR_MS
    rows: list[list[Any]] = []
    for index in range(KLINE_COUNT):
        open_time = base_open_ms + index * BAR_MS
        bias = Decimal(((index * 37) % 101) - 50) / Decimal("10000")
        close = (price * (Decimal("1") + bias)).quantize(TICK, ROUND_HALF_UP)
        high = (max(price, close) * Decimal("1.0007")).quantize(TICK, ROUND_HALF_UP)
        low = (min(price, close) * Decimal("0.9993")).quantize(TICK, ROUND_HALF_UP)
        volume = (Decimal("10") + Decimal(index % 7)).quantize(Decimal("0.00001"))
        quote_volume = (volume * close).quantize(Decimal("0.01"), ROUND_HALF_UP)
        taker_buy = (volume * Decimal("0.51")).quantize(Decimal("0.00001"))
        rows.append(
            [
                open_time,
                format(price, "f"),
                format(high, "f"),
                format(low, "f"),
                format(close, "f"),
                format(volume, "f"),
                open_time + BAR_MS - 1,
                format(quote_volume, "f"),
                100 + (index % 50),
                format(taker_buy, "f"),
                format((taker_buy * close).quantize(Decimal("0.01")), "f"),
                "0",
            ]
        )
        price = close
    return rows


class MockBinanceServer:
    """Servidor local con estado configurable que imita la API Spot DEMO."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        symbol: str = "BTCUSDT",
        start_price: str = "80000.00",
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.symbol = symbol
        self.start_price = Decimal(start_price)
        self.step_size = STEP

        self.balances: dict[str, Decimal] = {
            "USDT": Decimal("10000"),
            "BTC": Decimal("0"),
        }
        self.orders: list[dict] = []
        self.open_orders: list[dict] = []
        self.trades: list[dict] = []
        self.next_order_id = 1000
        self.next_trade_id = 1
        self.klines_data = _build_klines(self.start_price)

        self.order_delay_s = 0.0
        self.order_http_status: int | None = None
        self.order_error_code: int | None = None
        self.order_error_msg = "Order rejected by mock"
        self.fill = FillConfig()

        self.read_fail_count = 0
        self.read_fail_status = 500
        self.read_fail_retry_after_s: float | None = None

        self.order_request_count = 0
        self.cancel_request_count = 0
        self.request_counts: dict[str, int] = {}

        self._lock = threading.RLock()
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.base_url = ""

    # ------------------------------------------------------------ ciclo vida

    def start(self) -> str:
        httpd = _MockHTTPServer(("127.0.0.1", 0), _MockHandler, self)
        self._httpd = httpd
        self._thread = threading.Thread(
            target=httpd.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        )
        self._thread.start()
        self.base_url = f"http://127.0.0.1:{httpd.server_address[1]}"
        return self.base_url

    def stop(self) -> None:
        if self._httpd is None:
            return
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._httpd = None
        self._thread = None

    # ------------------------------------------------------------- utilidades

    @property
    def base_asset(self) -> str:
        return self.symbol[:-4] if self.symbol.endswith("USDT") else self.symbol[:3]

    @property
    def quote_asset(self) -> str:
        return "USDT"

    def count(self, method: str, path: str) -> int:
        with self._lock:
            return self.request_counts.get(f"{method} {path}", 0)

    def _note_request(self, method: str, path: str) -> None:
        with self._lock:
            key = f"{method} {path}"
            self.request_counts[key] = self.request_counts.get(key, 0) + 1

    def _take_read_failure(self) -> tuple[int, float | None] | None:
        with self._lock:
            if self.read_fail_count <= 0:
                return None
            self.read_fail_count -= 1
            return self.read_fail_status, self.read_fail_retry_after_s


class _MockHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], handler: type, mock: MockBinanceServer) -> None:
        super().__init__(address, handler)
        self.mock = mock

    def handle_error(self, request: Any, client_address: Any) -> None:
        # Los clientes que expiran por timeout abortan la conexión: no es un
        # error del mock, se silencia para no ensuciar la salida de pytest.
        if isinstance(sys.exc_info()[1], ConnectionError):
            return
        super().handle_error(request, client_address)


# --------------------------------------------------------------------- auth


def _verify(mock: MockBinanceServer, handler: BaseHTTPRequestHandler, params: dict) -> None:
    key = handler.headers.get("X-MBX-APIKEY") or ""
    if not key or key != mock.api_key:
        raise _MockError(-2015, "Invalid API-key, IP, or permissions for action.", status=401)
    if _one(params, "timestamp") is None:
        raise _MockError(
            -1102, "Mandatory parameter 'timestamp' was not sent, was empty/null, or malformed."
        )
    signature = _one(params, "signature")
    if not signature:
        raise _MockError(
            -1102, "Mandatory parameter 'signature' was not sent, was empty/null, or malformed."
        )
    raw_query = handler.path.split("?", 1)[1] if "?" in handler.path else ""
    payload = "&".join(
        part for part in raw_query.split("&") if part and not part.startswith("signature=")
    )
    expected = hmac.new(
        mock.api_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise _MockError(-1022, "Signature for this request is not valid.")
    try:
        timestamp = int(_one(params, "timestamp"))
        recv_window = int(_one(params, "recvWindow") or 5000)
    except (TypeError, ValueError):
        raise _MockError(-1102, "timestamp/recvWindow malformados")
    if abs(_now_ms() - timestamp) > recv_window:
        raise _MockError(-1021, "Timestamp for this request is outside of the recvWindow.")


# ------------------------------------------------------------------ handlers


def _h_time(mock: MockBinanceServer, handler: BaseHTTPRequestHandler, params: dict, body: bytes) -> None:
    handler._send_json(200, {"serverTime": _now_ms()})


def _symbol_entry(mock: MockBinanceServer, symbol: str) -> dict:
    base = symbol[:-4] if symbol.endswith("USDT") else symbol[:3]
    return {
        "symbol": symbol,
        "status": "TRADING",
        "baseAsset": base,
        "quoteAsset": "USDT",
        "filters": [
            {
                "filterType": "PRICE_FILTER",
                "minPrice": "0.01000000",
                "maxPrice": "1000000.00000000",
                "tickSize": "0.01000000",
            },
            {
                "filterType": "LOT_SIZE",
                "minQty": "0.00001000",
                "maxQty": "9000.00000000",
                "stepSize": "0.00001000",
            },
            {
                "filterType": "NOTIONAL",
                "minNotional": "5.00000000",
                "maxNotional": "9000000.00000000",
                "applyMinToMarket": True,
            },
            {
                "filterType": "MARKET_LOT_SIZE",
                "minQty": "0.00000000",
                "maxQty": "100.00000000",
                "stepSize": "0.00000000",
            },
        ],
    }


def _h_exchange_info(mock: MockBinanceServer, handler: BaseHTTPRequestHandler, params: dict, body: bytes) -> None:
    symbol = _one(params, "symbol") or mock.symbol
    if symbol != mock.symbol:
        raise _MockError(-1121, f"Invalid symbol: {symbol}", status=404)
    handler._send_json(
        200,
        {
            "timezone": "UTC",
            "serverTime": _now_ms(),
            "symbols": [_symbol_entry(mock, symbol)],
        },
    )


def _h_klines(mock: MockBinanceServer, handler: BaseHTTPRequestHandler, params: dict, body: bytes) -> None:
    symbol = _one(params, "symbol")
    if symbol != mock.symbol:
        raise _MockError(-1121, f"Invalid symbol: {symbol}", status=404)
    interval = _one(params, "interval")
    if interval != "4h":
        raise _MockError(-1121, f"Invalid interval: {interval}", status=404)
    try:
        limit = int(_one(params, "limit") or 500)
    except ValueError:
        raise _MockError(-1130, "Illegal characters found in parameter 'limit'.")
    limit = max(1, min(limit, 1000))
    rows = mock.klines_data
    end_time = _one(params, "endTime")
    if end_time is not None:
        end = int(end_time)
        rows = [row for row in rows if row[0] <= end]
    handler._send_json(200, rows[-limit:])


def _h_book_ticker(mock: MockBinanceServer, handler: BaseHTTPRequestHandler, params: dict, body: bytes) -> None:
    symbol = _one(params, "symbol")
    if symbol != mock.symbol:
        raise _MockError(-1121, f"Invalid symbol: {symbol}", status=404)
    price = mock.klines_data[-1][4]
    handler._send_json(
        200,
        {
            "symbol": symbol,
            "bidPrice": price,
            "bidQty": "1.00000000",
            "askPrice": price,
            "askQty": "1.00000000",
        },
    )


def _h_account(mock: MockBinanceServer, handler: BaseHTTPRequestHandler, params: dict, body: bytes) -> None:
    _verify(mock, handler, params)
    with mock._lock:
        balances = [
            {"asset": asset, "free": format(quantity, "f"), "locked": "0"}
            for asset, quantity in sorted(mock.balances.items())
        ]
    handler._send_json(
        200,
        {
            "makerCommission": 10,
            "takerCommission": 10,
            "canTrade": True,
            "canWithdraw": False,
            "canDeposit": False,
            "accountType": "SPOT",
            "updateTime": _now_ms(),
            "balances": balances,
        },
    )


def _h_open_orders(mock: MockBinanceServer, handler: BaseHTTPRequestHandler, params: dict, body: bytes) -> None:
    _verify(mock, handler, params)
    symbol = _one(params, "symbol")
    with mock._lock:
        orders = [dict(order) for order in mock.open_orders if symbol is None or order["symbol"] == symbol]
    handler._send_json(200, orders)


def _h_my_trades(mock: MockBinanceServer, handler: BaseHTTPRequestHandler, params: dict, body: bytes) -> None:
    _verify(mock, handler, params)
    symbol = _one(params, "symbol")
    try:
        limit = int(_one(params, "limit") or 500)
    except ValueError:
        raise _MockError(-1130, "Illegal characters found in parameter 'limit'.")
    limit = max(1, min(limit, 1000))
    from_id = _one(params, "fromId")
    with mock._lock:
        trades = [dict(trade) for trade in mock.trades if trade["symbol"] == symbol]
    if from_id is not None:
        try:
            threshold = int(from_id)
        except ValueError:
            raise _MockError(-1102, "fromId malformado")
        trades = [trade for trade in trades if trade["id"] > threshold]
    handler._send_json(200, trades[:limit])


def _find_order(mock: MockBinanceServer, params: dict, only_open: bool = False) -> dict:
    order_id_raw = _one(params, "orderId")
    client_id = _one(params, "origClientOrderId")
    if (order_id_raw is None) == (client_id is None):
        raise _MockError(-1102, "orderId u origClientOrderId requerido")
    pool = mock.open_orders if only_open else mock.orders
    for order in pool:
        if order_id_raw is not None and str(order["orderId"]) == order_id_raw:
            return order
        if client_id is not None and order["clientOrderId"] == client_id:
            return order
    if only_open:
        raise _MockError(-2011, "Unknown order sent.")
    raise _MockError(-2013, "Order does not exist.")


def _h_query_order(mock: MockBinanceServer, handler: BaseHTTPRequestHandler, params: dict, body: bytes) -> None:
    _verify(mock, handler, params)
    with mock._lock:
        order = dict(_find_order(mock, params))
    handler._send_json(200, order)


def _execute_market_order(mock: MockBinanceServer, params: dict) -> dict:
    symbol = _one(params, "symbol")
    if symbol != mock.symbol:
        raise _MockError(-1121, f"Invalid symbol: {symbol}", status=404)
    side = (_one(params, "side") or "").upper()
    if side not in ("BUY", "SELL"):
        raise _MockError(-1102, "Mandatory parameter 'side' was not sent, was empty/null, or malformed.")
    order_type = (_one(params, "type") or "").upper()
    if order_type != "MARKET":
        raise _MockError(-1102, "mock only supports MARKET orders")
    quantity_raw = _one(params, "quantity")
    quote_raw = _one(params, "quoteOrderQty")
    if (quantity_raw is None) == (quote_raw is None):
        raise _MockError(-1102, "quantity o quoteOrderQty requerido")

    price = mock.fill.price if mock.fill.price is not None else Decimal(str(mock.klines_data[-1][4]))
    if quote_raw is not None:
        requested = _floor_step(Decimal(str(quote_raw)) / price, mock.step_size)
    else:
        requested = Decimal(str(quantity_raw))
    if mock.fill.qty is not None:
        requested = Decimal(str(mock.fill.qty))

    ratio = Decimal(str(mock.fill.ratio))
    if not Decimal(0) < ratio <= 1:
        raise ValueError("fill.ratio debe estar en (0, 1]")
    executed = _floor_step(requested * ratio, mock.step_size)
    if executed <= 0:
        raise _MockError(-2010, "Order would immediately match and take.")
    executed_quote = (executed * price).quantize(Decimal("0.00000001"), ROUND_HALF_UP)

    base_asset, quote_asset = mock.base_asset, mock.quote_asset
    commission_asset = mock.fill.commission_asset or (base_asset if side == "BUY" else quote_asset)
    commission = Decimal(str(mock.fill.commission))

    with mock._lock:
        balances = mock.balances
        balances.setdefault(base_asset, Decimal("0"))
        balances.setdefault(quote_asset, Decimal("0"))
        if side == "BUY":
            balances[quote_asset] -= executed_quote
            balances[base_asset] += executed
            if commission_asset == quote_asset:
                balances[quote_asset] -= commission
            elif commission_asset == base_asset:
                balances[base_asset] -= commission
        else:
            balances[base_asset] -= executed
            balances[quote_asset] += executed_quote
            if commission_asset == base_asset:
                balances[base_asset] -= commission
            elif commission_asset == quote_asset:
                balances[quote_asset] -= commission

        order_id = mock.next_order_id
        mock.next_order_id += 1
        trade_id = mock.next_trade_id
        mock.next_trade_id += 1
        now = _now_ms()
        status = "FILLED" if ratio >= 1 else "PARTIALLY_FILLED"
        client_id = _one(params, "newClientOrderId") or f"mock-{order_id}"
        order = {
            "symbol": symbol,
            "orderId": order_id,
            "orderListId": -1,
            "clientOrderId": client_id,
            "transactTime": now,
            "price": "0.00000000" if order_type == "MARKET" else format(price, "f"),
            "origQty": format(requested, "f"),
            "executedQty": format(executed, "f"),
            "origQuoteOrderQty": (
                format(Decimal(str(quote_raw)), "f") if quote_raw is not None else "0.00000000"
            ),
            "cummulativeQuoteQty": format(executed_quote, "f"),
            "status": status,
            "timeInForce": "GTC",
            "type": order_type,
            "side": side,
            "fills": [
                {
                    "price": format(price, "f"),
                    "qty": format(executed, "f"),
                    "commission": format(commission, "f"),
                    "commissionAsset": commission_asset,
                    "tradeId": trade_id,
                }
            ],
        }
        mock.orders.append(order)
        if status != "FILLED":
            mock.open_orders.append(order)
        mock.trades.append(
            {
                "symbol": symbol,
                "id": trade_id,
                "orderId": order_id,
                "price": format(price, "f"),
                "qty": format(executed, "f"),
                "quoteQty": format(executed_quote, "f"),
                "commission": format(commission, "f"),
                "commissionAsset": commission_asset,
                "time": now,
                "isBuyer": side == "BUY",
                "isMaker": False,
                "isBestMatch": True,
            }
        )
    return order


def _h_place_order(mock: MockBinanceServer, handler: BaseHTTPRequestHandler, params: dict, body: bytes) -> None:
    _verify(mock, handler, params)
    with mock._lock:
        mock.order_request_count += 1
        if mock.order_error_code is not None:
            raise _MockError(
                mock.order_error_code, mock.order_error_msg, status=mock.order_http_status or 400
            )
        if mock.order_http_status is not None and mock.order_http_status >= 500:
            raise _MockError(-1001, "mock order service unavailable", status=mock.order_http_status)
        order = _execute_market_order(mock, params)
        delay = mock.order_delay_s
    if delay > 0:
        time.sleep(delay)
    handler._send_json(200, order)


def _h_cancel_order(mock: MockBinanceServer, handler: BaseHTTPRequestHandler, params: dict, body: bytes) -> None:
    _verify(mock, handler, params)
    with mock._lock:
        mock.cancel_request_count += 1
        order = _find_order(mock, params, only_open=True)
        order["status"] = "CANCELED"
        mock.open_orders = [o for o in mock.open_orders if o["orderId"] != order["orderId"]]
        snapshot = dict(order)
        delay = mock.order_delay_s
    if delay > 0:
        time.sleep(delay)
    handler._send_json(200, snapshot)


_ROUTES: dict[tuple[str, str], Callable[..., None]] = {
    ("GET", "/api/v3/time"): _h_time,
    ("GET", "/api/v3/exchangeInfo"): _h_exchange_info,
    ("GET", "/api/v3/klines"): _h_klines,
    ("GET", "/api/v3/ticker/bookTicker"): _h_book_ticker,
    ("GET", "/api/v3/account"): _h_account,
    ("GET", "/api/v3/openOrders"): _h_open_orders,
    ("GET", "/api/v3/myTrades"): _h_my_trades,
    ("GET", "/api/v3/order"): _h_query_order,
    ("POST", "/api/v3/order"): _h_place_order,
    ("DELETE", "/api/v3/order"): _h_cancel_order,
}


class _MockHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:  # silencio en tests
        return

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")

    def _dispatch(self, method: str) -> None:
        mock: MockBinanceServer = self.server.mock  # type: ignore[attr-defined]
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query, keep_blank_values=True)
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length > 0 else b""
        mock._note_request(method, path)
        try:
            if method == "GET":
                failure = mock._take_read_failure()
                if failure is not None:
                    status, retry_after = failure
                    headers = (
                        {"Retry-After": format(retry_after, "f")}
                        if retry_after is not None
                        else None
                    )
                    self._send_json(status, {"code": -1001, "msg": "mock read failure"}, headers)
                    return
            route = _ROUTES.get((method, path))
            if route is None:
                raise _MockError(-1121, f"Unknown endpoint {method} {path}", status=404)
            route(mock, self, params, body)
        except _MockError as exc:
            self._send_json(exc.status, {"code": exc.code, "msg": exc.msg})
        except Exception as exc:  # pragma: no cover - salvaguarda del mock
            self._send_json(500, {"code": -1001, "msg": f"mock internal error: {exc!r}"})

    def _send_json(self, status: int, payload: Any, extra_headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            for name, value in (extra_headers or {}).items():
                self.send_header(name, value)
            self.end_headers()
            self.wfile.write(body)
        except OSError:
            pass
