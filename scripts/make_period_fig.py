"""Figura del periodo 2026-09-28 -> 2026-10-28: SMA, A2 y BH."""
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
import yaml

ROOT = Path(r"E:\bitcoin-trading-research")
sys.path.insert(0, str(ROOT))

from src.backtesting.engine import backtest
from src.ingestion.binance import read_kline_zip
from src.processing.resample import resample
from src.strategies.buy_and_hold import signal_buy_and_hold
from src.strategies.e2a_composite import signal_e2a_long
from src.strategies.individuals import signal_ma_long

UTC = timezone.utc
START = datetime(2026, 9, 28, tzinfo=UTC)
END = datetime(2026, 10, 29, tzinfo=UTC)
RAW = ROOT / "data/raw/spot/daily/klines/BTCUSDT/1m"
FIGS = ROOT / "docs/tesis_resultados_v3/figs"

paths = sorted(RAW.glob("BTCUSDT-1m-2026-09-*.zip")) + sorted(RAW.glob("BTCUSDT-1m-2026-10-*.zip"))
paths = [p for p in paths if "BTCUSDT-1m-2026-09-02.zip" <= p.name <= "BTCUSDT-1m-2026-10-28.zip"]
new1m = pl.concat([read_kline_zip(p) for p in paths]).sort("timestamp")
new4h = resample(new1m, "4h")
old = pl.read_parquet(ROOT / "data/processed/btcusdt_4h.parquet").sort("timestamp")
common = [c for c in old.columns if c in new4h.columns]
df = pl.concat([old.select(common), new4h.select(common)]).unique(subset=["timestamp"], keep="last").sort("timestamp")

cfg = yaml.safe_load((ROOT / "configs/strategies.yaml").read_text(encoding="utf-8"))
p = cfg["v3_selection"]["params"]

df = signal_ma_long(df, kind="sma", **p["sma"]).rename({"signal_sma": "_SMA"})
df = signal_e2a_long(df, **p["e2a"]).rename({"signal_e2a": "_A2"})
df = signal_buy_and_hold(df).rename({"signal_bh": "_BH"})

series = {}
for name, col, color in (("SMA", "_SMA", "#2ca02c"), ("E2-A A2", "_A2", "#8c564b"), ("BH", "_BH", "black")):
    bt = backtest(df.select(["timestamp", "open", "high", "low", "close", col]),
                  signal_col=col, fee_bps=10.0, slippage_bps=5.0, lag=1).sort("timestamp")
    base = bt.filter(pl.col("timestamp") < START).tail(1)
    per = bt.filter((pl.col("timestamp") >= START) & (pl.col("timestamp") < END))
    eq = np.concatenate([[float(base["equity"][0])], per["equity"].to_numpy()])
    ts = [base["timestamp"][0]] + per["timestamp"].to_list()
    series[name] = (ts, eq, color)

fig, axes = plt.subplots(1, 2, figsize=(13, 5), gridspec_kw={"width_ratios": [1.6, 1]})
for name, (ts, eq, color) in series.items():
    axes[0].plot(ts, eq / eq[0] * 100, lw=1.6, color=color, label=name)
    dd = (eq / np.maximum.accumulate(eq) - 1) * 100
    axes[1].plot(ts, dd, lw=1.4, color=color, label=name)

axes[0].axhline(100, color="gray", lw=0.8, ls="--")
axes[0].set_title("Equity normalizada (base = 100)")
axes[0].set_ylabel("Índice")
axes[0].legend()
axes[0].grid(alpha=0.3)

axes[1].axhline(0, color="gray", lw=0.8)
axes[1].set_title("Drawdown (%)")
axes[1].set_ylabel("%")
axes[1].legend()
axes[1].grid(alpha=0.3)

for ax in axes:
    ax.tick_params(axis="x", rotation=30)

fig.suptitle("Ventana 2026-09-28 → 2026-10-28 (4H, costos 15 pb)")
fig.tight_layout()
fig.savefig(FIGS / "periodo_2026_equity.png", dpi=150)
plt.close(fig)
print("OK", FIGS / "periodo_2026_equity.png")
