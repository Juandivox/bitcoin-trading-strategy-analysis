"""Cliente REST para Binance Spot **DEMO** (spec v2.0, RF-ORD-03 / RF-SEG-01).

Reglas de oro de esta capa:

1. **Lecturas** (``GET``): reintentos acotados con backoff exponencial, solo
   ante timeout, error de conexión, HTTP 5xx o 429. Si el servidor envía
   ``Retry-After`` (segundos), se respeta.
2. **Envíos** (``POST``/``DELETE`` de órdenes): **un único intento**. Un
   timeout, error de conexión, 5xx o 429 en un envío deja el resultado
   *incierto* -> ``AmbiguousResult``; jamás se reintenta a ciegas. Un 4xx es un
   rechazo determinista -> ``DemoRESTError`` con el ``code`` de Binance.
3. Todos los importes cruzan la API pública como ``decimal.Decimal`` y se
   serializan en notación plana (nunca ``float``) al construir el query string.
4. Firma HMAC-SHA256 sobre el query string **exacto** que se envía, con
   ``timestamp`` (ms) y ``recvWindow``; cabecera ``X-MBX-APIKEY``.
5. Nunca se registra el secreto ni la firma: este módulo no usa ``logging`` y
   su ``repr`` sólo expone longitudes.

Sólo depende de ``requests`` + stdlib.
"""
from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal
from typing import Any, Mapping
from urllib.parse import urlencode

import requests

__all__ = [
    "AmbiguousResult",
    "DemoRESTClient",
    "DemoRESTError",
    "Filters",
    "floor_to_step",
    "round_price_to_tick",
]

DEFAULT_BASE_URL = "https://demo-api.binance.com"
DEFAULT_RECV_WINDOW_MS = 10_000
DEFAULT_MAX_READ_RETRIES = 4
DEFAULT_RETRY_BACKOFF_S = 0.5


class DemoRESTError(Exception):
    """Error determinista del exchange (4xx) o de la capa REST."""

    def __init__(
        self,
        message: str,
        code: int | None = None,
        http_status: int | None = None,
        payload: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.http_status = http_status
        self.payload = payload

    def __str__(self) -> str:
        extras = []
        if self.code is not None:
            extras.append(f"code={self.code}")
        if self.http_status is not None:
            extras.append(f"http={self.http_status}")
        return self.message if not extras else f"{self.message} [{' '.join(extras)}]"


class AmbiguousResult(Exception):
    """Resultado incierto en un ENVÍO: prohibido reintentar a ciegas.

    Se lanza cuando un ``POST``/``DELETE`` de orden no obtuvo respuesta
    concluyente (timeout, error de conexión, 5xx o 429). La única recuperación
    válida es consultar el estado (``query_order``) con el ``clientOrderId``.
    """

    def __init__(self, message: str, payload: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.payload = payload


@dataclass(frozen=True)
class Filters:
    """Filtros de trading del símbolo, ya en ``Decimal``."""

    symbol: str
    step_size: Decimal
    min_qty: Decimal
    max_qty: Decimal
    tick_size: Decimal
    min_notional: Decimal
    max_notional: Decimal | None


def _dec_str(value: Decimal) -> str:
    """Notación plana sin exponente (Binance no espera ``1E-5``)."""
    return format(value, "f")


def _serialize(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        return _dec_str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, float):
        return format(value, "f")
    raise TypeError(f"tipo no serializable en query string: {type(value).__name__}")


def floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    """Redondea ``value`` al múltiplo de ``step`` **hacia abajo** (NUNCA sube).

    Sirve para cantidades (``stepSize``): redondear hacia arriba puede exceder
    el saldo o el máximo permitido. Con valores negativos también baja (aleja
    de cero), nunca hacia arriba.
    """
    if step <= 0:
        raise ValueError("step debe ser > 0")
    multiple = (value / step).to_integral_value(rounding=ROUND_FLOOR)
    return multiple * step


def round_price_to_tick(value: Decimal, tick: Decimal) -> Decimal:
    """Redondea ``value`` al múltiplo de ``tick`` más cercano (mitad al alza)."""
    if tick <= 0:
        raise ValueError("tick debe ser > 0")
    multiple = (value / tick).to_integral_value(rounding=ROUND_HALF_UP)
    return multiple * tick


class DemoRESTClient:
    """Cliente REST mínimo y seguro para el venue DEMO de Binance Spot."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        api_key: str = "",
        api_secret: str = "",
        timeout_s: float = 10,
        session: requests.Session | None = None,
        max_read_retries: int = DEFAULT_MAX_READ_RETRIES,
        retry_backoff_s: float = DEFAULT_RETRY_BACKOFF_S,
        clock_offset_ms: int = 0,
    ) -> None:
        self.base_url = str(base_url).rstrip("/")
        self.api_key = api_key
        self.timeout_s = float(timeout_s)
        self.max_read_retries = int(max_read_retries)
        self.retry_backoff_s = float(retry_backoff_s)
        self.clock_offset_ms = int(clock_offset_ms)
        self._api_secret = api_secret
        self._session = session if session is not None else requests.Session()
        self._headers = {"X-MBX-APIKEY": api_key} if api_key else {}
        # Costura privada para tests: permite simular un reloj local desviado.
        self._time_source = time.time

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(base_url={self.base_url!r}, "
            f"api_key_len={len(self.api_key)}, timeout_s={self.timeout_s})"
        )

    # ------------------------------------------------------------------ tiempo

    def _now_ms(self) -> int:
        return int(self._time_source() * 1000) + self.clock_offset_ms

    def sync_time(self) -> int:
        """Sincroniza el reloj con ``GET /api/v3/time`` y devuelve el offset (ms)."""
        server_ms = int(self._get("/api/v3/time")["serverTime"])
        self.clock_offset_ms = server_ms - int(self._time_source() * 1000)
        return self.clock_offset_ms

    # ------------------------------------------------------------- transporte

    def _build_query(self, params: Mapping[str, Any] | None, signed: bool) -> str:
        items: list[tuple[str, str]] = []
        for key, value in (params or {}).items():
            if value is None:
                continue
            items.append((str(key), _serialize(value)))
        if signed:
            items.append(("timestamp", str(self._now_ms())))
            items.append(("recvWindow", str(DEFAULT_RECV_WINDOW_MS)))
        query = urlencode(items)
        if signed:
            signature = hmac.new(
                self._api_secret.encode("utf-8"), query.encode("utf-8"), hashlib.sha256
            ).hexdigest()
            query = f"{query}&signature={signature}"
        return query

    def _do_http(
        self, method: str, path: str, params: Mapping[str, Any] | None, signed: bool
    ) -> requests.Response:
        query = self._build_query(params, signed)
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{query}"
        send = {
            "GET": self._session.get,
            "POST": self._session.post,
            "DELETE": self._session.delete,
        }[method]
        return send(url, headers=self._headers, timeout=self.timeout_s)

    @staticmethod
    def _is_retryable(status: int) -> bool:
        return status == 429 or status >= 500

    @staticmethod
    def _safe_json(response: requests.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return None

    def _error_from_response(
        self,
        response: requests.Response,
        context: str,
        payload: Any = None,
    ) -> DemoRESTError:
        if payload is None:
            payload = self._safe_json(response)
        code: int | None = None
        message: str | None = None
        if isinstance(payload, dict):
            raw_code = payload.get("code")
            try:
                code = int(raw_code) if raw_code is not None else None
            except (TypeError, ValueError):
                code = None
            raw_msg = payload.get("msg")
            message = str(raw_msg) if raw_msg else None
        detail = message or response.reason or "error"
        return DemoRESTError(
            f"{context}: {detail}",
            code=code,
            http_status=response.status_code,
            payload=payload,
        )

    def _payload_or_error(self, response: requests.Response, context: str) -> Any:
        payload = self._safe_json(response)
        if response.status_code >= 400:
            raise self._error_from_response(response, context, payload)
        if isinstance(payload, dict) and isinstance(payload.get("code"), int) and payload["code"] < 0:
            raise self._error_from_response(response, context, payload)
        return payload

    def _sleep_before_retry(self, attempt: int, retry_after: str | None) -> None:
        delay: float | None = None
        if retry_after:
            try:
                delay = max(0.0, float(retry_after))
            except (TypeError, ValueError):
                delay = None
        if delay is None:
            delay = self.retry_backoff_s * (2 ** (attempt - 1))
        if delay > 0:
            time.sleep(delay)

    def _get(self, path: str, params: Mapping[str, Any] | None = None, signed: bool = False) -> Any:
        """Lectura con reintentos acotados (solo timeout/5xx/429)."""
        context = f"GET {path}"
        attempts = 0
        while True:
            attempts += 1
            try:
                response = self._do_http("GET", path, params, signed)
            except (requests.Timeout, requests.ConnectionError) as exc:
                if attempts > self.max_read_retries:
                    raise DemoRESTError(
                        f"{context} falló tras {attempts} intentos: {type(exc).__name__}"
                    ) from exc
                self._sleep_before_retry(attempts, None)
                continue
            if self._is_retryable(response.status_code):
                if attempts > self.max_read_retries:
                    raise self._error_from_response(
                        response, f"{context} falló tras {attempts} intentos"
                    )
                self._sleep_before_retry(attempts, response.headers.get("Retry-After"))
                continue
            return self._payload_or_error(response, context)

    def _send_once(
        self, method: str, path: str, params: Mapping[str, Any], context: str
    ) -> Any:
        """Envío de orden: UN intento; lo incierto nunca se reintenta."""
        try:
            response = self._do_http(method, path, params, signed=True)
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise AmbiguousResult(
                f"{context}: resultado incierto ({type(exc).__name__}); "
                "NO reintentar a ciegas, consultar con query_order",
                payload=None,
            ) from exc
        if self._is_retryable(response.status_code):
            raise AmbiguousResult(
                f"{context}: HTTP {response.status_code} en un ENVÍO; "
                "resultado incierto, NO reintentar a ciegas",
                payload=self._safe_json(response),
            )
        return self._payload_or_error(response, context)

    # ------------------------------------------------------------- endpoints

    def exchange_info(self, symbol: str) -> dict:
        return self._get("/api/v3/exchangeInfo", {"symbol": symbol})

    def get_filters(self, symbol: str) -> Filters:
        info = self.exchange_info(symbol)
        entries = info.get("symbols") if isinstance(info, dict) else None
        if not entries:
            raise DemoRESTError(f"exchangeInfo sin datos para {symbol}", payload=info)
        entry = entries[0]
        by_type: dict[str, dict] = {}
        for item in entry.get("filters", []):
            by_type[item.get("filterType")] = item
        lot = by_type.get("LOT_SIZE") or by_type.get("MARKET_LOT_SIZE")
        price = by_type.get("PRICE_FILTER")
        notional = by_type.get("NOTIONAL") or by_type.get("MIN_NOTIONAL")
        missing = [
            name
            for name, found in (("LOT_SIZE", lot), ("PRICE_FILTER", price), ("NOTIONAL", notional))
            if not found
        ]
        if missing:
            raise DemoRESTError(f"faltan filtros {missing} para {symbol}", payload=entry)
        max_notional_raw = notional.get("maxNotional")
        return Filters(
            symbol=str(entry.get("symbol", symbol)),
            step_size=Decimal(str(lot["stepSize"])),
            min_qty=Decimal(str(lot["minQty"])),
            max_qty=Decimal(str(lot["maxQty"])),
            tick_size=Decimal(str(price["tickSize"])),
            min_notional=Decimal(str(notional["minNotional"])),
            max_notional=(
                Decimal(str(max_notional_raw))
                if max_notional_raw not in (None, "")
                else None
            ),
        )

    def account(self) -> dict:
        return self._get("/api/v3/account", signed=True)

    def free_balance(self, asset: str) -> Decimal:
        """Saldo libre del activo; ``Decimal(0)`` si no aparece en la cuenta."""
        wanted = asset.upper()
        for balance in self.account().get("balances", []):
            if str(balance.get("asset", "")).upper() == wanted:
                return Decimal(str(balance.get("free", "0")))
        return Decimal(0)

    def open_orders(self, symbol: str) -> list:
        return self._get("/api/v3/openOrders", {"symbol": symbol}, signed=True)

    def my_trades(self, symbol: str, limit: int = 500, from_id: int | None = None) -> list:
        params: dict[str, Any] = {"symbol": symbol, "limit": int(limit)}
        if from_id is not None:
            params["fromId"] = int(from_id)
        return self._get("/api/v3/myTrades", params, signed=True)

    def klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        end_time_ms: int | None = None,
    ) -> list[list]:
        params: dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
            "limit": int(limit),
        }
        if end_time_ms is not None:
            params["endTime"] = int(end_time_ms)
        return self._get("/api/v3/klines", params)

    def book_ticker(self, symbol: str) -> dict:
        """Mejor bid/ask actual (para valorar inventario al bid, spec §15.2)."""
        return self._get("/api/v3/ticker/bookTicker", {"symbol": symbol})

    def bid_price(self, symbol: str) -> Decimal:
        data = self.book_ticker(symbol)
        return Decimal(str(data["bidPrice"]))

    def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: Decimal | None = None,
        quote_order_qty: Decimal | None = None,
        client_order_id: str | None = None,
    ) -> dict:
        if (quantity is None) == (quote_order_qty is None):
            raise ValueError("indica exactamente uno de quantity o quote_order_qty")
        normalized_side = str(side).upper()
        if normalized_side not in ("BUY", "SELL"):
            raise ValueError(f"side inválido: {side!r}")
        params: dict[str, Any] = {
            "symbol": symbol,
            "side": normalized_side,
            "type": "MARKET",
        }
        if quantity is not None:
            params["quantity"] = quantity
        else:
            params["quoteOrderQty"] = quote_order_qty
        if client_order_id:
            params["newClientOrderId"] = client_order_id
        return self._send_once("POST", "/api/v3/order", params, context="place_market_order")

    def query_order(
        self,
        symbol: str,
        client_order_id: str | None = None,
        order_id: int | None = None,
    ) -> dict:
        params = self._order_lookup_params(symbol, client_order_id, order_id)
        return self._get("/api/v3/order", params, signed=True)

    def cancel_order(
        self,
        symbol: str,
        client_order_id: str | None = None,
        order_id: int | None = None,
    ) -> dict:
        params = self._order_lookup_params(symbol, client_order_id, order_id)
        return self._send_once("DELETE", "/api/v3/order", params, context="cancel_order")

    @staticmethod
    def _order_lookup_params(
        symbol: str,
        client_order_id: str | None,
        order_id: int | None,
    ) -> dict[str, Any]:
        if (client_order_id is None) == (order_id is None):
            raise ValueError("indica exactamente uno de client_order_id u order_id")
        params: dict[str, Any] = {"symbol": symbol}
        if client_order_id is not None:
            params["origClientOrderId"] = client_order_id
        else:
            params["orderId"] = int(order_id)
        return params
