"""Integración del supervisor contra un exchange simulado (mock Binance DEMO).

Cubre los caminos críticos sin framework: gates de arranque, residuos, inventario
ajeno, conciliación de fills, snapshots de patrimonio, control y cierre.
"""
from __future__ import annotations

import threading
import time
from decimal import Decimal
from pathlib import Path

import pytest

pytest.importorskip("nautilus_trader", reason="integración: requiere el venv del bot")
from nautilus_trader.live import NodeState  # noqa: E402

from app.config import BotConfig, Secrets  # noqa: E402
from app.exchange.demo_rest import DemoRESTClient
from app.main import Supervisor, StartupError
from app.supervision.lock import LockHeldError
from mock_binance import MockBinanceServer

API_KEY = "k" * 24
API_SECRET = "s" * 24


class FakeHandle:
    def __init__(self) -> None:
        self.state = NodeState.RUNNING
        self.is_running = True
        self.stopped = threading.Event()

    def stop(self) -> None:
        self.state = NodeState.STOPPED
        self.is_running = False
        self.stopped.set()


class FakeNode:
    def __init__(self) -> None:
        self._handle = FakeHandle()

    def handle(self) -> FakeHandle:
        return self._handle

    def run(self) -> None:
        self._handle.stopped.wait(60)

    def stop(self) -> None:
        self._handle.stop()


@pytest.fixture
def mock_server():
    server = MockBinanceServer(api_key=API_KEY, api_secret=API_SECRET)
    server.start()
    yield server
    server.stop()


def make_supervisor(tmp_path: Path, mock_server: MockBinanceServer, monkeypatch, **overrides) -> Supervisor:
    params = {
        "run_id": "test-run-001",
        "runs_dir": str(tmp_path / "runs"),
        "budget_usdt": 4900.0,
        **overrides,
    }
    cfg = BotConfig(**params)
    sup = Supervisor(cfg, Secrets(API_KEY, API_SECRET), echo_logs=False)
    sup.rest = DemoRESTClient(base_url=mock_server.base_url, api_key=API_KEY, api_secret=API_SECRET, timeout_s=5)
    sup.executor.rest = sup.rest
    monkeypatch.setattr("app.main.build_node", lambda cfg, secrets, ctx: FakeNode())
    return sup


def test_startup_gates_pass(tmp_path, mock_server, monkeypatch):
    sup = make_supervisor(tmp_path, mock_server, monkeypatch)
    sup._transition(sup.state.state.VALIDANDO, "test")
    sup._startup_gates()
    assert sup.state.state.value == "VALIDANDO"
    sup.audit.close()


def test_budget_gate_fails_when_balance_too_low(tmp_path, mock_server, monkeypatch):
    sup = make_supervisor(tmp_path, mock_server, monkeypatch, budget_usdt=4900.0)
    mock_server.balances["USDT"] = Decimal("100")
    with pytest.raises(StartupError):
        sup._startup_gates()
    sup.audit.close()


def test_dust_is_declared_residual(tmp_path, mock_server, monkeypatch):
    sup = make_supervisor(tmp_path, mock_server, monkeypatch)
    mock_server.balances["BTC"] = Decimal("0.00000041")
    sup._startup_gates()
    assert sup._declared_residual_qty == Decimal("0.00000041")
    assert sup.state.entries_paused is False
    sup.audit.close()


def test_foreign_inventory_pauses_entries(tmp_path, mock_server, monkeypatch):
    sup = make_supervisor(tmp_path, mock_server, monkeypatch)
    mock_server.balances["BTC"] = Decimal("0.5")
    sup._startup_gates()
    assert sup.state.entries_paused is True
    incidents = sup.audit.fetch("incidents")
    assert any(row["kind"] == "inventario_ajeno" for row in incidents)
    sup.audit.close()


def test_startup_reconciliation_adopts_fills(tmp_path, mock_server, monkeypatch):
    """Simula un reinicio: la orden ya se ejecutó y el proceso nuevo debe recuperar el fill."""
    sup1 = make_supervisor(tmp_path, mock_server, monkeypatch)
    status = sup1.executor.submit_market(
        action="ENTRY", side="BUY", bar_close_ms=int(time.time() * 1000),
        quote_notional=Decimal("100"), price_estimate=Decimal("80000"),
    )
    assert status in ("FILLED", "PARTIALLY_FILLED")
    assert sup1.ledger.base_qty() > 0
    sup1.audit.close()

    sup2 = make_supervisor(tmp_path, mock_server, monkeypatch)
    assert sup2.ledger.base_qty() == 0  # proceso nuevo, ledger vacío
    sup2._startup_reconciliation()
    assert sup2.ledger.base_qty() > 0
    assert sup2.audit.count("fills") >= 1
    intents = sup2.audit.fetch("order_intents")
    assert intents[0]["status"] in ("FILLED", "PARTIALLY_FILLED")
    sup2.audit.close()


def test_equity_snapshot_uses_budget_plus_ledger(tmp_path, mock_server, monkeypatch):
    sup = make_supervisor(tmp_path, mock_server, monkeypatch)
    sup.rest.place_market_order("BTCUSDT", "BUY", quote_order_qty=Decimal("1000"), client_order_id="e2a-test-buy-2")
    from app.exchange.demo_rest import AmbiguousResult, DemoRESTError  # noqa: F401

    order = sup.rest.query_order("BTCUSDT", client_order_id="e2a-test-buy-2")
    trades = [t for t in sup.rest.my_trades("BTCUSDT") if int(t["orderId"]) == int(order["orderId"])]
    from app.contracts import FillRecord

    for trade in trades:
        sup.handle_fill(
            FillRecord(
                symbol="BTCUSDT", trade_id=int(trade["id"]), order_id=int(order["orderId"]),
                client_order_id="e2a-test-buy-2", side="BUY", price=Decimal(str(trade["price"])),
                qty=Decimal(str(trade["qty"])), quote_qty=Decimal(str(trade["quoteQty"])),
                commission=Decimal(str(trade["commission"])), commission_asset=str(trade["commissionAsset"]),
                time_ms=int(trade["time"]), is_maker=False, source="test",
            )
        )
    sup._equity_snapshot()
    snapshot = sup.audit.last_equity()
    assert snapshot is not None
    equity = Decimal(str(snapshot["equity"]))
    assert equity < Decimal("4900")
    assert equity > Decimal("4800")
    assert Decimal(str(snapshot["base_qty"])) > 0
    sup.audit.close()


def test_control_pause_resume_and_export(tmp_path, mock_server, monkeypatch):
    sup = make_supervisor(tmp_path, mock_server, monkeypatch)
    sup._startup_gates()
    sup.state.transition(sup.state.state.VALIDANDO, "test")
    sup._transition(sup.state.state.RECONCILIANDO, "test")
    sup._transition(sup.state.state.CALENTANDO, "test")
    sup._transition(sup.state.state.EJECUTANDO, "test")

    sup.control.submit("pause", {"reason": "test"})
    sup._poll_control()
    assert sup.state.state.value == "ENTRADAS_PAUSADAS"
    assert sup.state.entries_paused is True
    assert sup.control.pending() is None

    sup.control.submit("resume")
    sup._poll_control()
    assert sup.state.state.value == "EJECUTANDO"
    assert sup.state.entries_paused is False

    sup.control.submit("export")
    sup._poll_control()
    assert (sup.cfg.exports_dir / "run_manifest.json").exists()
    assert (sup.cfg.exports_dir / "summary.md").exists()
    assert (sup.cfg.exports_dir / "equity.csv").exists()
    sup.audit.close()


def test_second_writer_is_rejected(tmp_path, mock_server, monkeypatch):
    sup1 = make_supervisor(tmp_path, mock_server, monkeypatch)
    sup1.lock.acquire()
    sup2 = make_supervisor(tmp_path, mock_server, monkeypatch)
    with pytest.raises(LockHeldError):
        sup2.lock.acquire()
    code = sup2.run()
    assert code == 75
    sup1.lock.release()
    sup1.audit.close()
    sup2.audit.close()


def test_full_run_stops_cleanly(tmp_path, mock_server, monkeypatch):
    sup = make_supervisor(tmp_path, mock_server, monkeypatch)
    thread = threading.Thread(target=sup.run, daemon=True)
    thread.start()
    deadline = time.time() + 20
    while time.time() < deadline and sup.state.state.value not in ("CALENTANDO", "EJECUTANDO", "ENTRADAS_PAUSADAS"):
        time.sleep(0.2)
    sup.request_stop()
    thread.join(timeout=30)
    assert not thread.is_alive()
    assert sup.state.state.value == "DETENIDO"
    assert (sup.cfg.exports_dir / "run_manifest.json").exists()
    sup.lock.acquire()
    sup.lock.release()
