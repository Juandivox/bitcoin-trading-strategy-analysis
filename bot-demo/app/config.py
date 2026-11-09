"""Configuración efectiva del bot (spec v2.0 §7, RF-SEG-01/04).

Sin secretos: las credenciales llegan por variables de entorno
(BINANCE_DEMO_API_KEY / BINANCE_DEMO_API_SECRET). Este módulo es el único
lugar donde se declaran los destinos permitidos y se rechaza cualquier
configuración que no sea DEMO oficial.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path
from typing import Any

import yaml

DEMO_REST_BASE = "https://demo-api.binance.com"
DEMO_WS_STREAM_BASE = "wss://demo-stream.binance.com"
DEMO_WS_API_BASE = "wss://demo-ws-api.binance.com"

ALLOWED_HOSTS = {
    DEMO_REST_BASE: {"host": "demo-api.binance.com", "scheme": "https"},
    DEMO_WS_STREAM_BASE: {"host": "demo-stream.binance.com", "scheme": "wss"},
    DEMO_WS_API_BASE: {"host": "demo-ws-api.binance.com", "scheme": "wss"},
}

FORBIDDEN_HOST_FRAGMENTS = (
    "api.binance.com",
    "api-gcp.binance.com",
    "api1.binance.com",
    "api2.binance.com",
    "api3.binance.com",
    "api4.binance.com",
    "stream.binance.com",
    "ws-api.binance.com",
    "fapi.binance.com",
    "dapi.binance.com",
    "testnet.binance.vision",
    "testnet.binancefuture.com",
    "binance.us",
    "demo-fapi.binance.com",
    "demo-dapi.binance.com",
)


@dataclass(frozen=True)
class StrategyParams:
    cci_period: int
    cci_entry: float
    cci_exit: float
    sma_fast: int
    sma_slow: int
    vol_window: int
    vol_z_thr: float

    def __post_init__(self) -> None:
        if not self.sma_fast < self.sma_slow:
            raise ValueError("sma_fast debe ser menor que sma_slow")
        if not self.cci_entry < self.cci_exit:
            raise ValueError("cci_entry debe ser menor que cci_exit")
        for name in ("cci_period", "sma_fast", "sma_slow", "vol_window"):
            if getattr(self, name) < 2:
                raise ValueError(f"{name} debe ser >= 2")

    @property
    def warmup_bars(self) -> int:
        return max(self.sma_slow, self.vol_window, self.cci_period) + 2


E2A_PSO = StrategyParams(
    cci_period=10,
    cci_entry=50.0,
    cci_exit=250.0,
    sma_fast=27,
    sma_slow=227,
    vol_window=60,
    vol_z_thr=0.1431,
)

E2A_A2 = StrategyParams(
    cci_period=58,
    cci_entry=-3.0,
    cci_exit=186.0,
    sma_fast=18,
    sma_slow=221,
    vol_window=40,
    vol_z_thr=0.5815632644010449,
)

STRATEGY_VARIANTS: dict[str, StrategyParams] = {"PSO": E2A_PSO, "A2": E2A_A2}


@dataclass(frozen=True)
class Tolerances:
    candle_publish_s: int = 60
    quote_max_age_s: int = 30
    signal_expiry_s: int = 120
    health_interval_s: int = 15
    equity_interval_s: int = 60
    heartbeat_log_s: int = 300
    stale_lock_heartbeat_s: int = 180


@dataclass(frozen=True)
class BotConfig:
    run_id: str
    strategy_variant: str = "PSO"
    strategy_params: StrategyParams = field(default_factory=lambda: STRATEGY_VARIANTS["PSO"])
    symbol: str = "BTCUSDT"
    venue: str = "BINANCE"
    bar_interval: str = "4h"
    bar_minutes: int = 240
    budget_usdt: float = 4900.0
    entry_notional_usdt: float = 1000.0
    max_positions: int = 2
    max_drawdown_pct: float | None = None
    history_bars: int = 600
    demo_rest_base: str = DEMO_REST_BASE
    demo_ws_stream_base: str = DEMO_WS_STREAM_BASE
    demo_ws_api_base: str = DEMO_WS_API_BASE
    runs_dir: str = "runs"
    tolerances: Tolerances = field(default_factory=Tolerances)

    def __post_init__(self) -> None:
        if self.strategy_variant not in STRATEGY_VARIANTS:
            raise ValueError(f"strategy_variant inválido: {self.strategy_variant}")
        expected = STRATEGY_VARIANTS[self.strategy_variant]
        if asdict(self.strategy_params) != asdict(expected):
            raise ValueError(
                f"strategy_params no coinciden con la variante {self.strategy_variant}"
            )
        if self.budget_usdt <= 0 or self.entry_notional_usdt <= 0:
            raise ValueError("budget_usdt y entry_notional_usdt deben ser positivos")
        if self.max_positions < 1:
            raise ValueError("max_positions debe ser >= 1")
        if self.entry_notional_usdt * self.max_positions > self.budget_usdt * 1.000001:
            raise ValueError(
                "entry_notional_usdt * max_positions no puede exceder budget_usdt"
            )
        if self.history_bars < self.strategy_params.warmup_bars + 20:
            raise ValueError("history_bars insuficiente para el calentamiento")

    @property
    def instrument_id(self) -> str:
        return f"{self.symbol}.{self.venue}"

    @property
    def bar_type(self) -> str:
        hours = self.bar_minutes // 60
        return f"{self.instrument_id}-{hours}-HOUR-LAST-EXTERNAL"

    @property
    def run_dir(self) -> Path:
        return Path(self.runs_dir) / self.run_id

    @property
    def db_path(self) -> Path:
        return self.run_dir / "audit.sqlite"

    @property
    def control_path(self) -> Path:
        return self.run_dir / "control.json"

    @property
    def state_path(self) -> Path:
        return self.run_dir / "state.json"

    @property
    def lock_path(self) -> Path:
        return self.run_dir / "writer.lock"

    @property
    def logs_dir(self) -> Path:
        return self.run_dir / "logs"

    @property
    def exports_dir(self) -> Path:
        return self.run_dir / "exports"

    @property
    def manifest_path(self) -> Path:
        return self.run_dir / "run_manifest.json"

    def validate_demo_only(self) -> None:
        """Rechaza cualquier destino que no sea un host oficial de Binance Demo (RF-SEG-01)."""
        for label, base in (
            ("demo_rest_base", self.demo_rest_base),
            ("demo_ws_stream_base", self.demo_ws_stream_base),
            ("demo_ws_api_base", self.demo_ws_api_base),
        ):
            if base not in ALLOWED_HOSTS:
                raise ValueError(
                    f"{label}={base!r} no es un destino DEMO oficial permitido"
                )
        blob = json.dumps(asdict(self), default=str)
        for allowed in ALLOWED_HOSTS:
            blob = blob.replace(allowed, "")
        for fragment in FORBIDDEN_HOST_FRAGMENTS:
            if fragment in blob:
                raise ValueError(
                    f"configuración contiene host prohibido {fragment!r} (solo DEMO)"
                )

    def fingerprint(self) -> str:
        """Hash estable de la configuración efectiva (sin secretos)."""
        blob = json.dumps(asdict(self), default=str, sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def ensure_dirs(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)

    def to_public_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(asdict(self), default=str))

    @classmethod
    def load(cls, path: str | Path | None = None, **overrides: Any) -> BotConfig:
        data: dict[str, Any] = {}
        if path is not None and Path(path).exists():
            loaded = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
            if not isinstance(loaded, dict):
                raise ValueError(f"{path} no contiene un mapeo YAML")
            data.update(loaded)
        data.update({k: v for k, v in overrides.items() if v is not None})
        if "strategy_params" in data and isinstance(data["strategy_params"], dict):
            # Ignora campos retirados (p.ej. atr_* en runs historicos).
            allowed = {f.name for f in fields(StrategyParams)}
            data["strategy_params"] = StrategyParams(
                **{k: v for k, v in data["strategy_params"].items() if k in allowed}
            )
        if "tolerances" in data and isinstance(data["tolerances"], dict):
            data["tolerances"] = Tolerances(**data["tolerances"])
        if "strategy_variant" in data and "strategy_params" not in data:
            data["strategy_params"] = STRATEGY_VARIANTS[data["strategy_variant"]]
        cfg = cls(**data)
        cfg.validate_demo_only()
        return cfg


@dataclass(frozen=True)
class Secrets:
    api_key: str
    api_secret: str

    def __repr__(self) -> str:
        return f"Secrets(api_key='***', api_secret='***', key_len={len(self.api_key)})"

    @classmethod
    def from_env(cls) -> Secrets:
        key = os.environ.get("BINANCE_DEMO_API_KEY", "").strip()
        secret = os.environ.get("BINANCE_DEMO_API_SECRET", "").strip()
        missing = [
            name
            for name, value in (
                ("BINANCE_DEMO_API_KEY", key),
                ("BINANCE_DEMO_API_SECRET", secret),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"faltan credenciales DEMO en el entorno: {missing}")
        if len(key) < 16 or len(secret) < 16:
            raise ValueError("credenciales DEMO sospechosamente cortas; revisar origen")
        return cls(api_key=key, api_secret=secret)
