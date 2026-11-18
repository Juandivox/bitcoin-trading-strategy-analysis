"""Figuras raster de la sustentacion (las que PowerPoint no puede dibujar nativas).

Lee docs/sustentacion/build/data/*.csv (generados por export_data.py).
Paleta de la plantilla UNAB: morado 9200EE (E2-A A2), naranja FFA502 (SMA), gris (BH).
"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import polars as pl

HERE = Path(__file__).parent
DATA, IMG = HERE / "data", HERE / "img"
IMG.mkdir(exist_ok=True)
PURPLE, ORANGE, DARK, GREY, TXT = "#9200EE", "#FFA502", "#333333", "#BDBDBD", "#404040"
plt.rcParams.update({
    "font.family": "Arial", "font.size": 13, "text.color": TXT, "axes.labelcolor": TXT,
    "xtick.color": TXT, "ytick.color": TXT, "axes.edgecolor": "#CCCCCC",
    "axes.spines.top": False, "axes.spines.right": False, "savefig.dpi": 220,
    "savefig.transparent": True,
})
pct = lambda v: f"{v:,.0f} %".replace("-", "−")


def es_num(v: float) -> str:
    return f"{v:,.0f}".replace(",", ".")


# ---------------------------------------------------------------- 1. BTC + halvings
wk = pl.read_csv(DATA / "weekly.csv").with_columns(pl.col("timestamp").str.to_date())
t = wk["timestamp"].to_list()
fig, (a1, a2) = plt.subplots(2, 1, figsize=(11.4, 4.9), sharex=True,
                             gridspec_kw={"height_ratios": [2.1, 1], "hspace": 0.08})
a1.plot(t, wk["close"], color=PURPLE, lw=1.8)
a1.set_yscale("log")
a1.set_yticks([3000, 10000, 30000, 100000])
a1.set_yticklabels(["3.000", "10.000", "30.000", "100.000"])
a1.set_ylabel("Precio BTC (USDT)")
for d, lab in [(datetime(2020, 5, 11), "Halving 2020"), (datetime(2024, 4, 20), "Halving 2024")]:
    for ax in (a1, a2):
        ax.axvline(d, color=ORANGE, lw=1.6, ls="--")
    a1.text(d, 2600, f" {lab}", color="#B07000", fontsize=12, fontweight="bold", va="bottom")
a1.grid(axis="y", color="#EEEEEE")
dd = wk["dd_BH"] * 100
a2.fill_between(t, dd, 0, color=DARK, alpha=0.85, lw=0)
a2.set_ylim(-112, 4)
a2.set_yticks([-80, -40, 0]); a2.set_yticklabels(["−80 %", "−40 %", "0 %"])
a2.set_ylabel("Caída desde\nel máximo")
imin = int(dd.arg_min())
a2.annotate("−83,91 %", xy=(t[imin], dd[imin]), xytext=(t[imin + 14], -104),
            fontsize=14, fontweight="bold", color=DARK, va="center")
a2.xaxis.set_major_locator(mdates.YearLocator())
a2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
fig.savefig(IMG / "btc_halvings.png", bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------- 2. Barcode exposicion
dl = pl.read_csv(DATA / "daily.csv").with_columns(pl.col("timestamp").str.to_date())
td = dl["timestamp"].to_list()
fig, ax = plt.subplots(figsize=(11.4, 2.3))
rows = [("SMA", "pos_SMA", ORANGE, 1.0), ("E2-A A2", "pos_E2A_A2", PURPLE, 0.0)]
for name, col, c, y in rows:
    ax.fill_between(td, y, y + 0.72, where=(dl[col] > 0).to_list(), color=c, lw=0, step="post")
    ax.add_patch(plt.Rectangle((mdates.date2num(td[0]), y), mdates.date2num(td[-1]) - mdates.date2num(td[0]),
                               0.72, fill=False, ec="#DDDDDD", lw=0.8))
ax.set_yticks([0.36, 1.36]); ax.set_yticklabels(["E2-A A2", "SMA"], fontsize=14, fontweight="bold")
ax.set_ylim(-0.1, 1.82)
ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
ax.xaxis.set_major_locator(mdates.YearLocator()); ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
fig.savefig(IMG / "barcode_exposicion.png", bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------- 3. Anatomia de una operacion
ind = pl.read_csv(DATA / "a2_indicators.csv", infer_schema_length=None).with_columns(
    pl.col("timestamp").str.to_datetime("%Y-%m-%d %H:%M"))
w0, w1 = datetime(2024, 10, 20), datetime(2024, 11, 18)
s = ind.filter((pl.col("timestamp") >= w0) & (pl.col("timestamp") <= w1))
ts = s["timestamp"].to_list()
e_t, x_t = datetime(2024, 11, 6, 4), datetime(2024, 11, 11, 20)  # lag 1: posicion efectiva
fig, (p1, p2, p3) = plt.subplots(3, 1, figsize=(7.0, 5.3), sharex=True,
                                 gridspec_kw={"height_ratios": [2.2, 1, 1], "hspace": 0.12})
p1.plot(ts, s["close"], color=DARK, lw=1.4, label="Precio")
p1.plot(ts, s["sma_f"], color=ORANGE, lw=2, label="SMA 18")
p1.plot(ts, s["sma_s"], color="#8A8A8A", lw=2, label="SMA 221")
p1.axvspan(e_t, x_t, color=PURPLE, alpha=0.12, lw=0)
pe = s.filter(pl.col("timestamp") == e_t)["close"][0]
px = s.filter(pl.col("timestamp") == x_t)["close"][0]
p1.scatter([e_t], [pe], s=90, color=PURPLE, zorder=5, marker="^")
p1.scatter([x_t], [px], s=90, color=PURPLE, zorder=5, marker="v")
p1.text(e_t, pe * 1.035, "Entrada", color=PURPLE, fontsize=11, fontweight="bold", ha="right")
p1.text(x_t, px * 1.02, "Salida", color=PURPLE, fontsize=11, fontweight="bold", ha="center")
p1.legend(loc="upper left", frameon=False, fontsize=10, ncol=3)
p1.set_ylabel("USDT", fontsize=10)
p1.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: es_num(v)))
p2.plot(ts, s["cci"], color=PURPLE, lw=1.4)
p2.axhline(-3, color=DARK, lw=1, ls="--"); p2.axhline(186, color=DARK, lw=1, ls=":")
p2.text(ts[-1], 205, "salida: CCI > 186", fontsize=9, ha="right"); p2.text(ts[-1], -75, "entrada: CCI cruza −3", fontsize=9, ha="right")
p2.axvspan(e_t, x_t, color=PURPLE, alpha=0.12, lw=0)
p2.set_ylabel("CCI 58", fontsize=10); p2.set_ylim(-110, 300)
p3.bar(ts, s["vz"], width=0.14, color=[PURPLE if v > 0.5816 else GREY for v in s["vz"]])
p3.axhline(0.5816, color=DARK, lw=1, ls="--")
p3.axvspan(e_t, x_t, color=PURPLE, alpha=0.12, lw=0)
p3.set_ylabel("Volumen z", fontsize=10)
p3.xaxis.set_major_locator(mdates.DayLocator(interval=5))
p3.xaxis.set_major_formatter(mdates.DateFormatter("%d-%b"))
for ax in (p1, p2, p3):
    ax.tick_params(labelsize=9)
fig.savefig(IMG / "anatomia_operacion.png", bbox_inches="tight")
plt.close(fig)
print("ok", sorted(p.name for p in IMG.glob("*.png")))
