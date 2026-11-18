"""Figuras de la formula del Sharpe y de PSO vs TPE (raster, fondo transparente).

Lee data/extra.json (export_extra.py). Escribe img/sharpe_formula.png, img/rf_formula.png,
img/pso_diagrama.png, img/tpe_diagrama.png, img/pso_formula.png, img/tpe_formula.png, img/pso_limites.png
"""
from __future__ import annotations
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).parent
IMG = HERE / "img"
ex = json.load(open(HERE / "data" / "extra.json", encoding="utf-8"))
PURPLE, ORANGE, DARK, GREY, TXT = "#9200EE", "#FFA502", "#333333", "#BDBDBD", "#404040"
plt.rcParams.update({"font.family": "Arial", "mathtext.fontset": "cm", "text.color": TXT,
                     "savefig.dpi": 300, "savefig.transparent": True})


def formula(tex: str, name: str, size: float, w: float = 8, h: float = 1.4, color=DARK):
    fig = plt.figure(figsize=(w, h))
    fig.text(0.5, 0.5, tex, fontsize=size, ha="center", va="center", color=color)
    fig.savefig(IMG / name, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)


formula(r"$\mathrm{Sharpe}\;=\;\dfrac{\bar{R}\;-\;r_f}{\sigma}\;\times\;\sqrt{P}$", "sharpe_formula.png", 44, 9, 2)
formula(r"$r_f\;=\;\dfrac{4\,\%}{2\,190}\;=\;0{,}001826\,\%$", "rf_formula.png", 28, 7, 1.4)
formula(r"$v\;\leftarrow\;w\,v\;+\;c_1 r_1\,(p_{\mathrm{mejor}}-x)\;+\;c_2 r_2\,(g_{\mathrm{mejor}}-x)$", "pso_formula.png", 22, 9, 1)
formula(r"$x_{\mathrm{siguiente}}\;=\;\mathrm{arg\,max}_x\;\dfrac{\ell(x)}{g(x)}$", "tpe_formula.png", 24, 7, 1.3)


for nm, tex in (("sym_R", r"$\bar{R}$"), ("sym_rf", r"$r_f$"), ("sym_sigma", r"$\sigma$"), ("sym_P", r"$P$")):
    formula(tex, nm + ".png", 30, 1, 1, color=PURPLE)

# --------------------------------------------------------------- diagrama PSO
rng = np.random.default_rng(7)
fig, ax = plt.subplots(figsize=(4.6, 3.0))
X, Y = np.meshgrid(np.linspace(0, 10, 200), np.linspace(0, 6, 120))
Z = np.exp(-((X - 7.6) ** 2 / 6 + (Y - 4.2) ** 2 / 3)) + 0.55 * np.exp(-((X - 2.5) ** 2 / 3 + (Y - 1.6) ** 2 / 2))
ax.contourf(X, Y, Z, levels=8, cmap="Greys", alpha=0.35)
g = np.array([7.6, 4.2])
pts = rng.uniform([0.6, 0.5], [9.4, 5.6], size=(12, 2))
for p in pts:
    d = (g - p) * 0.28 + rng.normal(0, 0.25, 2)
    ax.annotate("", xy=p + d, xytext=p, arrowprops=dict(arrowstyle="-|>", color=DARK, lw=1.3))
ax.scatter(pts[:, 0], pts[:, 1], s=55, color=DARK, zorder=3)
ax.scatter([g[0]], [g[1]], s=330, marker="*", color=ORANGE, edgecolor=DARK, zorder=4)
ax.annotate("mejor del grupo", xy=g, xytext=(8.6, 5.55), ha="center", fontsize=13, color=DARK, fontweight="bold",
            arrowprops=dict(arrowstyle="-", color=DARK, lw=1))
ax.set_xlim(0, 10); ax.set_ylim(0, 6)
ax.set_xlabel("parámetro 1", fontsize=11); ax.set_ylabel("parámetro 2", fontsize=11)
ax.set_xticks([]); ax.set_yticks([])
for s_ in ax.spines.values():
    s_.set_color("#CCCCCC")
fig.savefig(IMG / "pso_diagrama.png", bbox_inches="tight")
plt.close(fig)

# --------------------------------------------------------------- diagrama TPE
xs = np.linspace(0, 10, 400)
good = rng.normal(6.6, 0.8, 9)
bad = np.concatenate([rng.uniform(0.3, 9.7, 24)])


def kde(data, bw):
    return np.exp(-((xs[:, None] - data[None, :]) ** 2) / (2 * bw ** 2)).sum(1) / (len(data) * bw * np.sqrt(2 * np.pi))


l, gx = kde(good, 0.9), kde(bad, 1.3)
fig, ax = plt.subplots(figsize=(4.6, 3.0))
ax.fill_between(xs, l, color=PURPLE, alpha=0.25, lw=0)
ax.plot(xs, l, color=PURPLE, lw=2.2)
ax.plot(xs, gx, color="#8A8A8A", lw=2.2)
ax.text(xs[np.argmax(l)] - 1.3, l.max() * 0.95, r"$\ell(x)$: ensayos" + "\n" + "buenos", color=PURPLE, fontsize=13,
        fontweight="bold", ha="right", va="top")
ax.text(0.2, l.max() * 0.42, r"$g(x)$: ensayos" + "\n" + "malos", color="#6B6B6B", fontsize=13, fontweight="bold")
ax.plot(good, np.full_like(good, -0.02), "|", color=PURPLE, ms=14, mew=2)
ax.plot(bad, np.full_like(bad, -0.05), "|", color="#8A8A8A", ms=14, mew=2)
xn = xs[np.argmax(l / gx)]
ax.axvline(xn, color=ORANGE, lw=2, ls="--")
ax.text(xn, l.max() * 1.1, "siguiente ensayo", color="#B07000", fontsize=13, fontweight="bold", ha="center")
ax.set_ylim(-0.08, l.max() * 1.22); ax.set_xlim(0, 10)
ax.set_xlabel("valor del parámetro", fontsize=11)
ax.set_xticks([]); ax.set_yticks([])
for k in ("top", "right"):
    ax.spines[k].set_visible(False)
for k in ("left", "bottom"):
    ax.spines[k].set_color("#CCCCCC")
fig.savefig(IMG / "tpe_diagrama.png", bbox_inches="tight")
plt.close(fig)

# --------------------------------------------------------------- PSO en los limites
sp = ex["pso_space"]
pso, a2 = ex["variants"]["PSO_informe"], ex["variants"]["A2_TPE"]
labels = {"cci_period": "Periodo CCI", "cci_entry": "Entrada CCI", "cci_exit": "Salida CCI",
          "sma_fast": "SMA rápida", "sma_slow": "SMA lenta", "vol_window": "Ventana volumen", "vol_z_thr": "Umbral volumen"}


def fmt(k, v):
    s = f"{v:.2f}" if k == "vol_z_thr" else f"{v:.0f}"
    return s.replace(".", ",").replace("-", "−")


fig, ax = plt.subplots(figsize=(5.6, 4.4))
n = len(sp["dims"])
for i, (k, lo, hi) in enumerate(zip(sp["dims"], sp["lo"], sp["hi"])):
    y = n - 1 - i
    ax.plot([0, 1], [y, y], color="#E3E3E3", lw=11, solid_capstyle="round", zorder=1)
    ax.text(-0.04, y, labels[k], ha="right", va="center", fontsize=14, color=TXT)
    ax.text(0, y - 0.38, fmt(k, lo), ha="center", va="center", fontsize=11, color="#8A8A8A")
    ax.text(1, y - 0.38, fmt(k, hi), ha="center", va="center", fontsize=11, color="#8A8A8A")
    xp, xa = (pso[k] - lo) / (hi - lo), (a2[k] - lo) / (hi - lo)
    at_bound = min(abs(xp), abs(1 - xp)) < 1e-6
    ax.scatter([xa], [y], s=140, color=PURPLE, zorder=3, edgecolor="white", lw=1.2)
    ax.scatter([xp], [y], s=140, color=DARK, zorder=4, edgecolor="white", lw=1.2)
ax.scatter([], [], s=120, color=DARK, label="PSO")
ax.scatter([], [], s=120, color=PURPLE, label="TPE (A2)")
ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.12), ncol=2, frameon=False, fontsize=13)
ax.set_xlim(-0.6, 1.08); ax.set_ylim(-0.8, n - 0.4)
ax.axis("off")
fig.savefig(IMG / "pso_limites.png", bbox_inches="tight")
plt.close(fig)
print("ok")


# --------------------------------------------------------------- esquemas simples PSO / TPE
SLATE = "#5B6B7B"


def frame(ax, edge, ls="-"):
    ax.add_patch(plt.Rectangle((0, 0), 1, 1, fill=False, ec=edge, lw=2.5, ls=ls))
    ax.set_xlim(-0.06, 1.06); ax.set_ylim(-0.12, 1.06); ax.set_aspect("equal"); ax.axis("off")


rng2 = np.random.default_rng(11)
fig, ax = plt.subplots(figsize=(4.2, 3.6))
frame(ax, ORANGE, "--")
pts = rng2.beta(0.28, 0.28, size=(90, 2))
pts = np.clip(pts, 0.03, 0.97)
ax.scatter(pts[:, 0], pts[:, 1], s=60, color=SLATE, alpha=0.85, edgecolor="white", lw=0.5)
ax.text(0.5, -0.09, "bordes del rango de búsqueda", ha="center", fontsize=16, color="#B07000", fontweight="bold")
fig.savefig(IMG / "pso_simple.png", bbox_inches="tight")
plt.close(fig)

fig, ax = plt.subplots(figsize=(4.2, 3.6))
frame(ax, "#CCCCCC")
early = rng2.uniform(0.05, 0.95, size=(28, 2))
late = np.clip(rng2.normal([0.58, 0.52], 0.07, size=(40, 2)), 0.05, 0.95)
ax.add_patch(plt.Circle((0.58, 0.52), 0.2, color=PURPLE, alpha=0.10, lw=0))
ax.scatter(early[:, 0], early[:, 1], s=60, color="#D9B8F7", edgecolor="white", lw=0.5, label="primeros intentos")
ax.scatter(late[:, 0], late[:, 1], s=60, color=PURPLE, edgecolor="white", lw=0.5, label="intentos posteriores")
ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.2), ncol=2, frameon=False, fontsize=15, handletextpad=0.1, columnspacing=0.8)
fig.savefig(IMG / "tpe_simple.png", bbox_inches="tight")
plt.close(fig)
print("simples ok")
