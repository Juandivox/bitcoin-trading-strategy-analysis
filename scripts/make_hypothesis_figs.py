"""Figura de intervalos de confianza para la prueba de hipotesis."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(r"E:\bitcoin-trading-research")
FIGS = ROOT / "docs" / "tesis_resultados_v3" / "figs"
FIGS.mkdir(parents=True, exist_ok=True)

pairs = ["SMA - A2", "SMA - BH", "A2 - BH"]
full = [0.298, 0.370, 0.072]
full_ci = [(-0.479, 1.051), (-0.132, 0.853), (-0.722, 0.880)]
hold = [0.092, 0.568, 0.476]
hold_ci = [(-1.634, 2.093), (-0.437, 1.827), (-1.573, 2.522)]

fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
for ax, vals, cis, title, color in (
    (axes[0], full, full_ci, "Periodo completo (3.303 dias)", "#08519c"),
    (axes[1], hold, hold_ci, "Holdout 2025-2026 (609 dias)", "#8c564b"),
):
    x = np.arange(len(pairs))
    lower = [v - ci[0] for v, ci in zip(vals, cis)]
    upper = [ci[1] - v for v, ci in zip(vals, cis)]
    ax.errorbar(x, vals, yerr=[lower, upper], fmt="o", color=color,
                ecolor=color, elinewidth=2, capsize=6, markersize=8)
    ax.axhline(0, color="black", lw=1)
    ax.set_xticks(x)
    ax.set_xticklabels(pairs)
    ax.set_title(title)
    ax.set_ylabel("Diferencia de Sharpe anualizado")
    ax.grid(alpha=0.3)
    ax.set_ylim(-2.7, 2.7)

fig.suptitle("Diferencia de Sharpe con intervalo de confianza del 95% (bootstrap de bloques)")
fig.tight_layout()
fig.savefig(FIGS / "hipotesis_ci.png", dpi=150)
plt.close(fig)
print("OK", FIGS / "hipotesis_ci.png")
