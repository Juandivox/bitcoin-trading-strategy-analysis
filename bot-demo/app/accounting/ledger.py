"""Contabilidad de la prueba (spec v2.0 §15.1/§15.2).

Reglas duras:
- Idempotencia por (symbol, trade_id).
- Comisión en el activo base de una COMPRA: reduce la cantidad neta recibida y
  queda embebida en el costo por unidad (no se descuenta dos veces).
- Comisión en el activo base de una VENTA: se paga disponiendo de unidades
  adicionales al mismo precio del fill (consume FIFO por qty+comisión).
- Comisión en quote: suma al costo (compra) o resta del ingreso (venta).
- Comisión en un tercer activo: se registra y la valoración queda incompleta.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from decimal import Decimal

from app.contracts import EquityBreakdown, FillRecord

ZERO = Decimal("0")


@dataclass
class Lot:
    qty: Decimal
    total_cost: Decimal
    ts_ms: int

    @property
    def cost_per_unit(self) -> Decimal:
        return self.total_cost / self.qty


class Ledger:
    def __init__(self, symbol: str, base_asset: str = "BTC", quote_asset: str = "USDT") -> None:
        self.symbol = symbol
        self.base_asset = base_asset
        self.quote_asset = quote_asset
        self._applied: set[tuple[str, int]] = set()
        self._lots: deque[Lot] = deque()
        self._realized_pnl = ZERO
        self._fees: dict[str, Decimal] = {}
        self._unconverted: list[dict] = []
        self._flows: list[dict] = []
        self._base_qty = ZERO
        self._quote_cash = ZERO

    # ------------------------------------------------------------------ fills
    def apply_fill(self, fill: FillRecord) -> bool:
        key = (fill.symbol, int(fill.trade_id))
        if key in self._applied:
            return False
        self._applied.add(key)

        commission = Decimal(fill.commission)
        qty = Decimal(fill.qty)
        quote_qty = Decimal(fill.quote_qty)
        price = Decimal(fill.price)
        asset = fill.commission_asset
        side = fill.side.upper()

        if asset not in (self.base_asset, self.quote_asset):
            self._unconverted.append(
                {
                    "trade_id": fill.trade_id,
                    "asset": asset,
                    "amount": str(commission),
                    "ts_ms": fill.time_ms,
                    "reason": "comision_en_tercer_activo_sin_conversion",
                }
            )
            self._add_fee(asset, commission)

        if side == "BUY":
            fee_base = commission if asset == self.base_asset else ZERO
            fee_quote = commission if asset == self.quote_asset else ZERO
            net_qty = qty - fee_base
            if net_qty <= ZERO:
                raise ValueError(f"fill BUY con cantidad neta no positiva: {fill}")
            total_cost = quote_qty + fee_quote
            self._lots.append(Lot(qty=net_qty, total_cost=total_cost, ts_ms=fill.time_ms))
            self._base_qty += net_qty
            self._quote_cash -= total_cost
            self._flows.append(
                {"ts_ms": fill.time_ms, "asset": self.base_asset, "delta": str(net_qty), "reason": "compra_neta"}
            )
            self._flows.append(
                {"ts_ms": fill.time_ms, "asset": self.quote_asset, "delta": str(-total_cost), "reason": "compra_costo"}
            )
            if fee_base > ZERO:
                self._add_fee(self.base_asset, fee_base)
            if fee_quote > ZERO:
                self._add_fee(self.quote_asset, fee_quote)
        elif side == "SELL":
            fee_base = commission if asset == self.base_asset else ZERO
            fee_quote = commission if asset == self.quote_asset else ZERO
            disposed = qty + fee_base
            fifo_cost = self._consume_fifo(disposed)
            proceeds = quote_qty - fee_quote
            self._realized_pnl += proceeds - fifo_cost
            self._base_qty -= disposed
            self._quote_cash += proceeds
            self._flows.append(
                {"ts_ms": fill.time_ms, "asset": self.base_asset, "delta": str(-disposed), "reason": "venta_neta"}
            )
            self._flows.append(
                {"ts_ms": fill.time_ms, "asset": self.quote_asset, "delta": str(proceeds), "reason": "venta_ingreso"}
            )
            if fee_base > ZERO:
                self._add_fee(self.base_asset, fee_base)
            if fee_quote > ZERO:
                self._add_fee(self.quote_asset, fee_quote)
        else:
            raise ValueError(f"side desconocido en fill: {fill.side!r}")
        return True

    def _consume_fifo(self, qty: Decimal) -> Decimal:
        remaining = qty
        cost = ZERO
        while remaining > ZERO:
            if not self._lots:
                raise ValueError("venta sin lotes suficientes: inventario atribuible insuficiente")
            lot = self._lots[0]
            take = min(lot.qty, remaining)
            cost += lot.total_cost * take / lot.qty
            lot.total_cost -= lot.total_cost * take / lot.qty
            lot.qty -= take
            remaining -= take
            if lot.qty <= ZERO:
                self._lots.popleft()
        return cost

    def _add_fee(self, asset: str, amount: Decimal) -> None:
        self._fees[asset] = self._fees.get(asset, ZERO) + amount

    # ------------------------------------------------------------------ vistas
    def applied_trade_ids(self) -> set[int]:
        return {trade_id for (_symbol, trade_id) in self._applied}

    def base_qty(self) -> Decimal:
        return self._base_qty

    def quote_cash(self) -> Decimal:
        return self._quote_cash

    def realized_pnl(self) -> Decimal:
        return self._realized_pnl

    def open_lots(self) -> list[dict]:
        return [
            {"qty": str(lot.qty), "cost_per_unit": str(lot.cost_per_unit), "ts_ms": lot.ts_ms}
            for lot in self._lots
        ]

    def fees_by_asset(self) -> dict[str, Decimal]:
        return dict(self._fees)

    def unconverted_fees(self) -> list[dict]:
        return list(self._unconverted)

    def cash_flows(self) -> list[dict]:
        return list(self._flows)

    def equity(
        self,
        budget_usdt: Decimal,
        cash_free_usdt: Decimal,
        cash_reserved_usdt: Decimal,
        base_price_usdt: Decimal | None,
        pending_costs_usdt: Decimal = ZERO,
    ) -> EquityBreakdown:
        """E(t) = efectivo libre + reservado + valor del inventario − costos pendientes.

        El efectivo lo reporta el exchange (autoridad); el inventario lo reporta el
        ledger atribuible. `pending_costs_usdt` solo debe usarse para costos que aún
        NO estén incorporados en el efectivo ni en el inventario.
        """
        notes: list[str] = []
        complete = True
        inventory_value = ZERO
        if self._base_qty > ZERO:
            if base_price_usdt is None or base_price_usdt <= ZERO:
                complete = False
                notes.append("inventario_sin_valoracion_valida")
            else:
                inventory_value = self._base_qty * base_price_usdt
        if self._unconverted:
            complete = False
            notes.append("comisiones_en_tercer_activo_sin_conversion")
        equity = cash_free_usdt + cash_reserved_usdt + inventory_value - pending_costs_usdt
        if equity <= ZERO:
            complete = False
            notes.append("patrimonio_no_positivo")
        return EquityBreakdown(
            budget_usdt=budget_usdt,
            cash_free_usdt=cash_free_usdt,
            cash_reserved_usdt=cash_reserved_usdt,
            base_qty=self._base_qty,
            base_price_usdt=base_price_usdt if base_price_usdt is not None else ZERO,
            inventory_value_usdt=inventory_value,
            pending_costs_usdt=pending_costs_usdt,
            equity_usdt=equity,
            complete=complete,
            notes=notes,
        )

    def snapshot(self) -> dict:
        return {
            "symbol": self.symbol,
            "base_asset": self.base_asset,
            "quote_asset": self.quote_asset,
            "applied_trade_ids": sorted(self.applied_trade_ids()),
            "base_qty": str(self._base_qty),
            "quote_cash": str(self._quote_cash),
            "realized_pnl": str(self._realized_pnl),
            "open_lots": self.open_lots(),
            "fees_by_asset": {k: str(v) for k, v in self._fees.items()},
            "unconverted_fees": self._unconverted,
        }
