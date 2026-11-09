"""Fixtures económicos del spec v2.0 §18 + FIFO, idempotencia y fees por activo."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.accounting.ledger import Ledger
from app.contracts import FillRecord


def make_fill(**overrides) -> FillRecord:
    base = dict(
        symbol="BTCUSDT",
        trade_id=1,
        order_id=10,
        client_order_id="c1",
        side="BUY",
        price=Decimal("100"),
        qty=Decimal("10"),
        quote_qty=Decimal("1000"),
        commission=Decimal("0"),
        commission_asset="USDT",
        time_ms=1_700_000_000_000,
        is_maker=False,
        source="test",
    )
    base.update(overrides)
    return FillRecord(**base)


def test_fixture_a_fees_in_quote():
    ledger = Ledger("BTCUSDT")
    assert ledger.apply_fill(make_fill(trade_id=1, side="BUY", commission=Decimal("1")))
    assert ledger.apply_fill(
        make_fill(
            trade_id=2, side="SELL", price=Decimal("110"), quote_qty=Decimal("1100"),
            commission=Decimal("1.10"), time_ms=1_700_000_100_000,
        )
    )
    assert ledger.realized_pnl() == Decimal("97.90")
    eq = ledger.equity(
        budget_usdt=Decimal("10000"),
        cash_free_usdt=Decimal("10000") + ledger.quote_cash(),
        cash_reserved_usdt=Decimal("0"),
        base_price_usdt=Decimal("110"),
    )
    assert eq.equity_usdt == Decimal("10097.90")
    assert eq.base_qty == Decimal("0")
    assert eq.complete is True
    assert ledger.fees_by_asset() == {"USDT": Decimal("2.10")}


def test_fixture_b_entry_fee_in_base_not_double_counted():
    ledger = Ledger("BTCUSDT")
    assert ledger.apply_fill(make_fill(trade_id=1, side="BUY", commission=Decimal("0.01"), commission_asset="BTC"))
    assert ledger.base_qty() == Decimal("9.99")
    assert ledger.apply_fill(
        make_fill(
            trade_id=2, side="SELL", qty=Decimal("9.99"), price=Decimal("110"),
            quote_qty=Decimal("1098.90"), commission=Decimal("1.0989"),
            commission_asset="USDT", time_ms=1_700_000_100_000,
        )
    )
    assert ledger.realized_pnl() == Decimal("97.8011")
    eq = ledger.equity(
        budget_usdt=Decimal("10000"),
        cash_free_usdt=Decimal("10000") + ledger.quote_cash(),
        cash_reserved_usdt=Decimal("0"),
        base_price_usdt=Decimal("110"),
    )
    assert eq.equity_usdt == Decimal("10097.8011")
    assert ledger.fees_by_asset()["BTC"] == Decimal("0.01")


def test_idempotent_by_trade_id():
    ledger = Ledger("BTCUSDT")
    fill = make_fill()
    assert ledger.apply_fill(fill) is True
    assert ledger.apply_fill(fill) is False
    assert ledger.base_qty() == Decimal("10")
    assert len(ledger.cash_flows()) == 2


def test_fifo_consumes_lots_in_order():
    ledger = Ledger("BTCUSDT")
    ledger.apply_fill(make_fill(trade_id=1, qty=Decimal("10"), quote_qty=Decimal("1000")))
    ledger.apply_fill(make_fill(trade_id=2, qty=Decimal("5"), price=Decimal("120"), quote_qty=Decimal("600")))
    ledger.apply_fill(
        make_fill(trade_id=3, side="SELL", qty=Decimal("12"), price=Decimal("130"), quote_qty=Decimal("1560"))
    )
    assert ledger.realized_pnl() == Decimal("320")
    lots = ledger.open_lots()
    assert len(lots) == 1
    assert lots[0]["qty"] == "3"
    assert lots[0]["cost_per_unit"] == "120"
    assert ledger.base_qty() == Decimal("3")


def test_third_asset_fee_marks_incomplete():
    ledger = Ledger("BTCUSDT")
    ledger.apply_fill(make_fill(trade_id=1, qty=Decimal("1"), quote_qty=Decimal("100"),
                               commission=Decimal("0.001"), commission_asset="BNB"))
    assert ledger.unconverted_fees()
    eq = ledger.equity(
        budget_usdt=Decimal("10000"),
        cash_free_usdt=Decimal("9900"),
        cash_reserved_usdt=Decimal("0"),
        base_price_usdt=Decimal("100"),
    )
    assert eq.complete is False
    assert "comisiones_en_tercer_activo_sin_conversion" in eq.notes


def test_sell_with_base_fee_disposes_extra_units():
    ledger = Ledger("BTCUSDT")
    ledger.apply_fill(make_fill(trade_id=1, qty=Decimal("1.1"), quote_qty=Decimal("110")))
    ledger.apply_fill(
        make_fill(trade_id=2, side="SELL", qty=Decimal("1"), price=Decimal("100"),
                  quote_qty=Decimal("100"), commission=Decimal("0.001"), commission_asset="BTC")
    )
    assert ledger.base_qty() == Decimal("0.099")
    assert ledger.fees_by_asset()["BTC"] == Decimal("0.001")
    assert ledger.realized_pnl() == Decimal("-0.1")


def test_sell_without_lots_raises():
    ledger = Ledger("BTCUSDT")
    with pytest.raises(ValueError):
        ledger.apply_fill(make_fill(side="SELL", qty=Decimal("1"), quote_qty=Decimal("100")))


def test_snapshot_is_serializable():
    import json

    ledger = Ledger("BTCUSDT")
    ledger.apply_fill(make_fill())
    json.dumps(ledger.snapshot())
