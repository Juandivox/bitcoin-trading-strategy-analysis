"""Wiring del nodo NautilusTrader (SOLO DATOS) contra Binance DEMO.

Distinción crítica: el nodo corre en `Environment.LIVE` de Nautilus (procesa eventos
actuales) pero el conector Binance SIEMPRE queda en `BinanceEnvironment.DEMO`.

La ejecución no usa el cliente de ejecución del framework: el entorno DEMO de Binance
rechaza claves HMAC en su WebSocket API privada (-2028) y la cuenta opera con HMAC.
Las órdenes van por la capa REST propia (app/execution/rest_executor.py), verificada
contra DEMO. Ver docs/ACEPTACION.md.
"""
from __future__ import annotations

from nautilus_trader.adapters.binance import (
    BinanceDataClientConfig,
    BinanceDataClientFactory,
    BinanceEnvironment,
    BinanceProductType,
    BinanceSpotMarketDataMode,
)
from nautilus_trader.common import Environment
from nautilus_trader.live import LiveNode
from nautilus_trader.model import BarType, InstrumentId, StrategyId, TraderId

from app.config import BotConfig, Secrets
from app.strategy.live import E2ALiveConfig, E2ALiveStrategy

CLIENT_ID = "BINANCE"


def build_node(cfg: BotConfig, secrets: Secrets, ctx) -> LiveNode:
    cfg.validate_demo_only()
    data_cfg = BinanceDataClientConfig(
        product_type=BinanceProductType.SPOT,
        environment=BinanceEnvironment.DEMO,
        api_key=secrets.api_key,
        api_secret=secrets.api_secret,
        spot_market_data_mode=BinanceSpotMarketDataMode.Json,
    )
    trader_tag = "".join(ch for ch in cfg.run_id if ch.isalnum())[-6:] or "001"
    node = (
        LiveNode.builder(f"E2A-{cfg.run_id}", TraderId.from_str(f"E2A-{trader_tag}"), Environment.LIVE)
        .add_data_client(CLIENT_ID, BinanceDataClientFactory(), data_cfg)
        .build()
    )
    strategy_cfg = E2ALiveConfig(
        strategy_id=StrategyId.from_str(f"E2A-{trader_tag}"),
        instrument_id=InstrumentId.from_str(cfg.instrument_id),
        bar_type=BarType.from_str(cfg.bar_type),
        symbol=cfg.symbol,
        params={
            "cci_period": cfg.strategy_params.cci_period,
            "cci_entry": cfg.strategy_params.cci_entry,
            "cci_exit": cfg.strategy_params.cci_exit,
            "sma_fast": cfg.strategy_params.sma_fast,
            "sma_slow": cfg.strategy_params.sma_slow,
            "vol_window": cfg.strategy_params.vol_window,
            "vol_z_thr": cfg.strategy_params.vol_z_thr,
        },
        budget_usdt=cfg.budget_usdt,
        entry_notional_usdt=cfg.entry_notional_usdt,
        max_positions=cfg.max_positions,
        history_bars=cfg.history_bars,
        signal_expiry_s=cfg.tolerances.signal_expiry_s,
    )
    strategy_cfg.ctx = ctx
    node.add_strategy(E2ALiveStrategy(strategy_cfg))
    return node
