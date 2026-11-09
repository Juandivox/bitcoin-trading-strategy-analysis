"""Genera figuras adicionales para el dossier de sustentacion."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

ROOT = Path(r"E:\bitcoin-trading-research")
FIGS = ROOT / "docs" / "tesis_resultados_v3" / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

df = pl.read_csv(ROOT / "docs/tesis_resultados_v3/tablas/metricas_por_periodo.csv")
full = df.filter(pl.col("periodo") == "FULL").sort("sharpe", descending=True)

# ---------------------------------------------------------------- 1) Riesgo-retorno
fig, ax = plt.subplots(figsize=(10, 6))
x = full["maxDD_%"].to_numpy()
y = full["CAGR_%"].to_numpy()
s = full["sharpe"].to_numpy()
names = full["estrategia"].to_list()
sc = ax.scatter(x, y, c=s, cmap="viridis", s=120 + 180 * (s - s.min()) / (s.max() - s.min()),
                edgecolor="black", linewidth=0.8)
for xi, yi, ni in zip(x, y, names):
    ax.annotate(ni, (xi, yi), textcoords="offset points", xytext=(7, 6), fontsize=9)
ax.axhline(0, color="gray", lw=0.8)
ax.set_xlabel("Max Drawdown (%)")
ax.set_ylabel("CAGR (%)")
ax.set_title("Rentabilidad vs riesgo: CAGR y MaxDD (FULL, 4H, rf=4%)")
ax.grid(alpha=0.3)
cb = fig.colorbar(sc, ax=ax)
cb.set_label("Sharpe")
fig.tight_layout()
fig.savefig(FIGS / "dossier_riesgo_retorno.png", dpi=150)
plt.close(fig)

# ---------------------------------------------------------------- 2) Retorno anual A2 vs SMA
years = [2021, 2022, 2023, 2024, 2025]
a2 = [49.32, -22.42, 28.65, 43.14, 5.77]
sma = [134.18, -53.20, 111.68, 107.96, 12.69]
x = np.arange(len(years))
fig, ax = plt.subplots(figsize=(10, 5))
ax.bar(x - 0.2, a2, width=0.4, label="E2-A A2", color="#8c564b")
ax.bar(x + 0.2, sma, width=0.4, label="SMA", color="#2ca02c")
ax.axhline(0, color="black", lw=0.8)
ax.set_xticks(x)
ax.set_xticklabels(years)
ax.set_ylabel("Retorno anual (%)")
ax.set_title("Retorno por año calendario: E2-A A2 vs SMA")
ax.legend()
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(FIGS / "dossier_anual.png", dpi=150)
plt.close(fig)

# ---------------------------------------------------------------- 3) Win rate vs payoff
fig, ax = plt.subplots(figsize=(10, 6))
x = full["win_rate_%"].to_numpy()
y = np.array([8.83, 6.81, 2.92, 0.95, 1.84, 0.42, 0.54, 1.11, np.nan])  # orden: full sorted
# recalcular en el orden de full
payoff_map = {"SMA": 8.83, "EMA": 6.81, "MACD": 2.92, "E2A_A2": 0.95,
              "BH": np.nan, "CCI": 0.42, "RSI": 0.54, "E2C": 1.84, "E2A_A1": 1.11}
y = np.array([payoff_map[n] for n in names])
pf = full["profit_factor"].to_list()
size = [60 + 40 * (v if v is not None and v == v else 0) for v in pf]
ax.scatter(x, y, s=size, c="#1f77b4", alpha=0.7, edgecolor="black")
for xi, yi, ni in zip(x, y, names):
    if not np.isnan(yi):
        ax.annotate(ni, (xi, yi), textcoords="offset points", xytext=(7, 6), fontsize=9)
ax.set_yscale("log")
ax.set_xlabel("Win rate (%)")
ax.set_ylabel("Payoff (escala log)")
ax.set_title("Dos perfiles: win rate vs payoff (tamaño = profit factor)")
ax.grid(alpha=0.3, which="both")
fig.tight_layout()
fig.savefig(FIGS / "dossier_perfil.png", dpi=150)
plt.close(fig)

# ---------------------------------------------------------------- 4) Sharpe antes/despues
before = [1.244, 1.152, 0.960, 1.144, 0.808, 0.264, 0.432, -0.024, -0.609]
after = [1.123, 1.065, 0.924, 0.872, 0.749, 0.248, 0.209, -0.262, -1.463]
order = ["SMA", "EMA", "MACD", "E2A_A2", "BH", "CCI", "RSI", "E2C", "E2A_A1"]
x = np.arange(len(order))
fig, ax = plt.subplots(figsize=(11, 5))
ax.bar(x - 0.2, before, width=0.4, label="Antes (rf=0, params viejos)", color="#9ecae1")
ax.bar(x + 0.2, after, width=0.4, label="Despues (rf=4%, params v3)", color="#08519c")
ax.axhline(0, color="black", lw=0.8)
ax.set_xticks(x)
ax.set_xticklabels(order, rotation=20, ha="right")
ax.set_ylabel("Sharpe FULL")
ax.set_title("Sharpe antes y despues de la normalizacion")
ax.legend(fontsize=8)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(FIGS / "dossier_sharpe_antes_despues.png", dpi=150)
plt.close(fig)

print("OK figuras dossier")
