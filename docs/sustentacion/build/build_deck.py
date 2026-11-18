"""Construye la presentacion de sustentacion sobre la plantilla UNAB.

Entrada : plantilla UNAB (.pptx), data/*.csv|json (export_data.py), img/*.png (make_figs.py)
Salida  : docs/sustentacion/Sustentacion_Bitcoin_UNAB.pptx

Uso: python build_deck.py <ruta_plantilla.pptx>
Todas las cifras salen del informe final (Tablas 1-6) o del motor canonico, que las reproduce.
"""
from __future__ import annotations
import copy, csv, json, sys
from datetime import date
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData, XyChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION, XL_MARKER_STYLE, XL_TICK_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

HERE = Path(__file__).parent
DATA, IMG = HERE / "data", HERE / "img"
OUT = HERE.parent / "Sustentacion_Bitcoin_UNAB.pptx"

PURPLE, ORANGE = RGBColor(0x92, 0x00, 0xEE), RGBColor(0xFF, 0xA5, 0x02)
DARK, GREY, LIGHT = RGBColor(0x33, 0x33, 0x33), RGBColor(0xB5, 0xB5, 0xB5), RGBColor(0xF2, 0xF2, 0xF2)
TXT, MUTED, WHITE = RGBColor(0x40, 0x40, 0x40), RGBColor(0x80, 0x80, 0x80), RGBColor(0xFF, 0xFF, 0xFF)
LILAC = RGBColor(0xF1, 0xE3, 0xFD)
ORANGE_TXT = RGBColor(0xB0, 0x70, 0x00)
HEAD, BODY = "Open Sans", "Arial"
L, W_CONTENT = 0.75, 11.45

# ------------------------------------------------------------------ helpers


def es(v: float, d: int = 2, sign: bool = False) -> str:
    s = f"{abs(v):,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if v < 0:
        return "−" + s
    return ("+" if sign and v > 0 else "") + s


def text(slide, x, y, w, h, runs, size=16, color=TXT, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, font=BODY, name=None, spacing=None):
    """runs: str | list[str | (str, dict)] ; '\n' separa parrafos."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    if isinstance(runs, str):
        runs = [runs]
    p = tf.paragraphs[0]
    p.alignment = align
    if spacing:
        p.space_after = Pt(spacing)
    for r in runs:
        t, o = (r, {}) if isinstance(r, str) else r
        parts = t.split("\n")
        for i, part in enumerate(parts):
            if i > 0:
                p = tf.add_paragraph()
                p.alignment = align
                if spacing:
                    p.space_after = Pt(spacing)
            if not part:
                continue
            run = p.add_run()
            run.text = part
            f = run.font
            f.size = Pt(o.get("size", size))
            f.bold = o.get("bold", bold)
            f.italic = o.get("italic", False)
            f.name = o.get("font", font)
            f.color.rgb = o.get("color", color)
    return tb


def box(slide, x, y, w, h, fill=LIGHT, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08, name=None):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        s.name = name
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(2)
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    s.shadow.inherit = False
    return s


def shape_text(s, runs, size=14, color=TXT, bold=False, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, font=BODY):
    tf = s.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.08)
    tf.margin_top = tf.margin_bottom = Inches(0.04)
    tf.vertical_anchor = anchor
    if isinstance(runs, str):
        runs = [runs]
    p = tf.paragraphs[0]
    p.alignment = align
    for r in runs:
        t, o = (r, {}) if isinstance(r, str) else r
        for i, part in enumerate(t.split("\n")):
            if i > 0:
                p = tf.add_paragraph()
                p.alignment = align
            if not part:
                continue
            run = p.add_run()
            run.text = part
            run.font.size = Pt(o.get("size", size))
            run.font.bold = o.get("bold", bold)
            run.font.name = o.get("font", font)
            run.font.color.rgb = o.get("color", color)



def math_sym(slide, x, y, w, h, base, sub=None, size=26, color=PURPLE):
    """Simbolo en Cambria Math cursiva con subindice opcional (p. ej. r con f)."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    para_ = tf.paragraphs[0]
    para_.alignment = PP_ALIGN.CENTER
    for t, is_sub in ((base, False), (sub, True)):
        if not t:
            continue
        r = para_.add_run()
        r.text = t
        r.font.size = Pt(size * (0.7 if is_sub else 1))
        r.font.italic = True
        r.font.name = "Cambria Math"
        r.font.color.rgb = color
        if is_sub:
            r.font._element.set("baseline", "-25000")
    return tb

def line(slide, x1, y1, x2, y2, color=GREY, width=2, arrow=False):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(width)
    if arrow:
        ln = c.line._get_or_add_ln()
        etree.SubElement(ln, qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
    return c


def set_bg(slide, img_part):
    rid = slide.part.relate_to(img_part, RT.IMAGE)
    xml = (f'<p:bg xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
           f'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
           f'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
           f'<p:bgPr><a:blipFill dpi="0" rotWithShape="1"><a:blip r:embed="{rid}"/>'
           f'<a:stretch><a:fillRect/></a:stretch></a:blipFill><a:effectLst/></p:bgPr></p:bg>')
    slide._element.cSld.insert(0, etree.fromstring(xml))


def title(slide, t, sub=None):
    ph = slide.shapes.title
    ph.left, ph.top, ph.width, ph.height = Inches(L), Inches(0.42), Inches(W_CONTENT - 0.6), Inches(0.75)
    tf = ph.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.TOP
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    r = p.add_run()
    r.text = t
    r.font.size, r.font.bold, r.font.name, r.font.color.rgb = Pt(28), True, HEAD, PURPLE
    if sub:
        text(slide, L, 1.12, W_CONTENT - 0.6, 0.4, sub, size=16, color=MUTED, name="Subtitulo")


def source(slide, t):
    text(slide, L, 6.62, 4.75, 0.32, t, size=10, color=MUTED, name="Fuente")


def notes(slide, t):
    slide.notes_slide.notes_text_frame.text = t


def style_chart(chart, size=12):
    chart.font.size = Pt(size)
    chart.font.name = BODY
    chart.font.color.rgb = TXT


def quiet_axis(ax, fmt=None, minimum=None, maximum=None, major=None, grid=True):
    if minimum is not None:
        ax.minimum_scale = minimum
    if maximum is not None:
        ax.maximum_scale = maximum
    if major is not None:
        ax.major_unit = major
    if fmt:
        ax.tick_labels.number_format = fmt
        ax.tick_labels.number_format_is_linked = False
    ax.format.line.color.rgb = RGBColor(0xCC, 0xCC, 0xCC)
    ax.has_major_gridlines = grid
    if grid:
        ax.major_gridlines.format.line.color.rgb = RGBColor(0xE6, 0xE6, 0xE6)
        ax.major_gridlines.format.line.width = Pt(0.75)


def log_axis(ax):
    scaling = ax._element.find(qn("c:scaling"))
    lb = etree.SubElement(scaling, qn("c:logBase"))
    lb.set("val", "10")
    scaling.remove(lb)
    scaling.insert(0, lb)


def color_series(series, rgb, width=2.25, marker=False):
    series.format.line.color.rgb = rgb
    series.format.line.width = Pt(width)
    series.smooth = False
    if not marker:
        series.marker.style = XL_MARKER_STYLE.NONE


# ------------------------------------------------------------------ datos
summ = json.load(open(DATA / "summary.json", encoding="utf-8"))["summary"]
weekly = list(csv.DictReader(open(DATA / "weekly.csv", encoding="utf-8")))


def yearfrac(s: str) -> float:
    d = date.fromisoformat(s[:10])
    return d.year + (d.timetuple().tm_yday - 1) / 365.25


NAMES = {"BH": "Buy & Hold", "RSI": "RSI", "MACD": "MACD", "SMA": "SMA", "EMA": "EMA", "CCI": "CCI",
         "E2A_A1": "E2-A A1", "E2A_A2": "E2-A A2", "E2C": "E2-C"}
COL = {"E2A_A2": PURPLE, "SMA": ORANGE, "BH": DARK}
# Informe, Tabla 2 (FULL)
T2 = {"SMA": (1.123, 57.48, 46.54, -70.96), "EMA": (1.065, 53.37, 46.63, -66.72),
      "MACD": (0.924, 42.72, 45.19, -60.05), "E2A_A2": (0.872, 17.08, 14.74, -27.93),
      "BH": (0.749, 37.48, 68.17, -83.91), "CCI": (0.248, 2.89, 53.85, -87.04),
      "RSI": (0.209, 5.49, 33.59, -57.43), "E2C": (-0.262, -1.79, 16.77, -51.08),
      "E2A_A1": (-1.463, -2.92, 4.68, -28.83)}
# Informe, Tabla 3
T3 = {"SMA": (66, 33.33, 4.41), "EMA": (57, 35.09, 3.68), "MACD": (285, 37.19, 1.73),
      "E2A_A2": (39, 76.92, 3.17), "CCI": (118, 75.42, 1.29), "RSI": (361, 69.25, 1.22),
      "E2C": (294, 35.03, 0.99), "E2A_A1": (30, 23.33, 0.34)}
for k, (sh, cg, _, dd) in T2.items():  # el motor reproduce el informe
    assert abs(summ[k]["sharpe"] - sh) < 6e-4 and abs(summ[k]["CAGR_%"] - cg) < 6e-3 and abs(summ[k]["maxDD_%"] - dd) < 6e-3, k

# ------------------------------------------------------------------ plantilla
prs = Presentation(sys.argv[1])
tpl_slides = list(prs.slides)


def image_part_of(slide_idx: int, nth: int = 0):
    parts = [r.target_part for r in tpl_slides[slide_idx].part.rels.values() if r.reltype == RT.IMAGE]
    return parts[nth]


def bg_part(slide_idx):
    s = tpl_slides[slide_idx]
    blip = s._element.cSld.find(qn("p:bg")).find(".//" + qn("a:blip"))
    return s.part.related_part(blip.get(qn("r:embed")))


BG_COVER, BG_SEP, BG_CONTENT, BG_CLOSE = bg_part(0), bg_part(2), bg_part(3), bg_part(4)
LAYOUT = {l.name: l for l in prs.slide_layouts}
TITLE_ONLY, BLANK = LAYOUT["TITLE_ONLY"], LAYOUT["BLANK"]
CHEVRON = IMG.parent / "img" / "_chevron.png"
chev_part = [r.target_part for r in tpl_slides[3].part.rels.values()
             if r.reltype == RT.IMAGE and r.target_part is not BG_CONTENT][0]
CHEVRON.write_bytes(chev_part.blob)


def new(kind="content"):
    s = prs.slides.add_slide(TITLE_ONLY if kind == "content" else BLANK)
    set_bg(s, {"content": BG_CONTENT, "sep": BG_SEP, "cover": BG_COVER, "close": BG_CLOSE}[kind])
    for ph in list(s.placeholders):  # fecha/pie/numero vacios de la plantilla Google
        if ph.placeholder_format.idx in (10, 11, 12):
            ph._element.getparent().remove(ph._element)
    return s


def separator(t, n):
    s = new("sep")
    text(s, 6.67, 2.2, 6.0, 2.9, t, size=54, bold=True, color=WHITE, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 6.67, 5.2, 4.0, 0.5, f"Parte {n}", size=18, color=WHITE)
    return s


# =========================================================== 1. Portada institucional
s = new("cover")
notes(s, "Diapositiva de apertura mientras se prepara el equipo.")

# =========================================================== 2. Titulo
s = new("sep")
text(s, 1.0, 1.1, 10.5, 0.4, "Trabajo de grado · Ingeniería Financiera · Línea Inversiones", size=18, color=WHITE)
text(s, 1.0, 1.75, 11.0, 1.6, "Estrategias de trading\nen Bitcoin", size=50, bold=True, color=WHITE, font=HEAD)
text(s, 1.0, 3.55, 10.8, 1.0,
     "Evaluación, selección y optimización de la estrategia con mejor relación riesgo–rendimiento",
     size=22, color=WHITE)
text(s, 1.0, 5.05, 6.5, 1.0, "Javier Antonio Reyes Espinosa\nJuan David Ramírez Castilla", size=18, bold=True, color=WHITE)
text(s, 7.6, 5.05, 4.5, 1.0, "Asesor\nJosé Luis Flórez Rueda", size=18, color=WHITE)
notes(s, "Presentación de los autores y del asesor. Pregunta guía: ¿qué estrategia de trading ofrece la mejor relación riesgo–rendimiento en Bitcoin?")

# =========================================================== Planteamiento del problema
s = new()
title(s, "Planteamiento del problema",
      "Por qué es difícil elegir una estrategia de trading para Bitcoin")
probs = [("−83,91 %", "Bitcoin es muy volátil",
          "Cambia de comportamiento entre ciclos de halving: una estrategia que gana en un ciclo puede perder en el siguiente."),
         ("5 de 8", "Otros mercados",
          "La mayoría de las estrategias revisadas se probó en Forex, acciones o índices, no en Bitcoin."),
         ("1 min a 1 día", "Otras temporalidades",
          "Cada estudio usa otra temporalidad y otros parámetros, así que sus resultados no se pueden comparar.")]
pw = (W_CONTENT - 0.05 - 2 * 0.3) / 3
for i, (n, h, d_) in enumerate(probs):
    x = L + i * (pw + 0.3)
    box(s, x, 1.7, pw, 2.85, fill=LIGHT, radius=0.08)
    text(s, x + 0.25, 1.85, pw - 0.5, 0.7, n, size=32, bold=True, color=PURPLE, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.25, 2.62, pw - 0.5, 0.4, h, size=17, bold=True, color=TXT)
    text(s, x + 0.25, 3.08, pw - 0.5, 1.4, d_, size=14, color=TXT)
for i in range(3):
    xc = L + i * (pw + 0.3) + pw / 2
    line(s, xc, 4.6, xc, 4.88, color=PURPLE, width=2.5, arrow=True)
b = box(s, L, 4.95, W_CONTENT - 0.05, 1.45, fill=PURPLE, radius=0.08)
shape_text(b, [("Pregunta de investigación\n", {"bold": True, "size": 15, "color": WHITE}),
               ("¿Qué estrategia de trading ofrece la mejor relación riesgo–rendimiento en Bitcoin, y cómo optimizar sus parámetros?",
                {"size": 20, "bold": True, "color": WHITE, "font": HEAD})], align=PP_ALIGN.LEFT)
b.text_frame.margin_left = Inches(0.3)
source(s, "Fuente: Informe final, introducción y Tabla 1")
notes(s, "Bitcoin es muy volátil y cambia de comportamiento entre ciclos de halving: quien compró y mantuvo llegó a perder 83,91 %. La mayoría de las estrategias publicadas se probaron en otros mercados, y cada estudio usa otra temporalidad y otros parámetros. Por eso no sabemos qué estrategia funciona mejor en Bitcoin. Nuestra pregunta es cuál ofrece la mejor relación riesgo–rendimiento y cómo optimizarla.")

# =========================================================== 3. Contexto
s = new()
title(s, "Bitcoin crece mucho, pero también cae mucho",
      "Precio semanal BTC/USDT y caída desde el máximo anterior, ago 2017 – sep 2026")
s.shapes.add_picture(str(IMG / "btc_halvings.png"), Inches(L), Inches(1.65), width=Inches(11.2))
source(s, "Fuente: Binance Data Vision; elaboración propia")
notes(s, "El halving reduce a la mitad la emisión nueva de BTC cada ~4 años. Entre ciclos, el precio cayó hasta 83,91 % desde su máximo. Por eso una estrategia no puede juzgarse solo por lo que gana: también por cuánto puede perder.")

# =========================================================== 4. Literatura
s = new()
title(s, "La literatura usa otros mercados y plazos",
      "Estrategias revisadas según activo y temporalidad de evaluación")
cols = ["1 minuto", "5 minutos", "1 hora", "4 horas", "Diaria"]
rows = [("Bitcoin", 1.15), ("Forex", 0.95), ("Acciones e índices", 1.95)]
x0, cw, y0 = 2.6, 1.91, 1.75
for j, c in enumerate(cols):
    text(s, x0 + j * cw, y0, cw - 0.1, 0.35, c, size=14, bold=True, color=TXT, align=PP_ALIGN.CENTER)
yy = y0 + 0.45
row_y = {}
for name, h in rows:
    box(s, L, yy, W_CONTENT - 0.05, h - 0.08, fill=LILAC if name == "Bitcoin" else LIGHT, radius=0.05)
    text(s, L + 0.2, yy, 1.95, h - 0.08, name, size=15, bold=True, color=PURPLE if name == "Bitcoin" else TXT,
         anchor=MSO_ANCHOR.MIDDLE)
    row_y[name] = (yy, h - 0.08)
    yy += h
refs = [("Bitcoin", 3, "Tomás (2026)", "CNN-LSTM"), ("Bitcoin", 2, "Bello Pérez (2025)", "XGBoost"),
        ("Bitcoin", 4, "Omran (2023)", "Media móvil + PSO"),
        ("Forex", 1, "López Benítez (2023)", "RSI + ML"), ("Forex", 0, "Ozturk et al. (2016)", "24 reglas + AG"),
        ("Acciones e índices", 4, "Corazza et al. (2024)", "4 indicadores + PSO"),
        ("Acciones e índices", 4, "Roncancio y Valenzuela (2010)", "RSI dinámico"),
        ("Acciones e índices", 4, "Fang et al. (2014)", "Sentimiento")]
stack = {}
for row, col, a, m in refs:
    ry, rh = row_y[row]
    k = stack.get((row, col), 0)
    stack[(row, col)] = k + 1
    n = sum(1 for r in refs if r[0] == row and r[1] == col)
    hs = [0.62 if "Roncancio" in r[2] else 0.48 for r in refs if r[0] == row and r[1] == col]
    ch = hs[k]
    top = ry + (rh - (sum(hs) + (n - 1) * 0.06)) / 2 + sum(hs[:k]) + k * 0.06
    if row == "Bitcoin" and col == 3:
        top = ry + 0.06
    b = box(s, x0 + col * cw + 0.03, top, cw - 0.16, ch, fill=WHITE, radius=0.12)
    shape_text(b, [(a + "\n", {"bold": True, "size": 10.5}), (m, {"size": 10, "color": MUTED})], size=11)
    b.text_frame.margin_left = b.text_frame.margin_right = Inches(0.04)
# este trabajo
ry, rh = row_y["Bitcoin"]
b = box(s, x0 + 3 * cw + 0.03, ry + 0.6, cw - 0.16, 0.42, fill=PURPLE, radius=0.12)
shape_text(b, [("Este trabajo", {"bold": True, "color": WHITE, "size": 12})])
source(s, "Fuente: Informe final, Tabla 1")
notes(s, "De ocho referencias, solo tres trabajan con Bitcoin y cada una usa una temporalidad y un método distintos. Los resultados no se pueden comparar entre sí. Este trabajo prueba nueve estrategias en Bitcoin con las mismas condiciones.")


# =========================================================== 5. Objetivos
s = new()
title(s, "Cuatro objetivos, un capítulo cada uno",
      "Objetivo general: seleccionar y optimizar la estrategia con mejor relación riesgo–rendimiento")
steps = [("Caracterizar", "las estrategias reportadas en la literatura"),
         ("Evaluar", "con backtesting y forward testing"),
         ("Seleccionar", "las de mejor relación riesgo–rendimiento"),
         ("Optimizar", "la mejor con inteligencia artificial y automatizarla")]
cx = [L + 1.35 + i * 2.95 for i in range(4)]
line(s, cx[0], 3.2, cx[-1], 3.2, color=GREY, width=3)
for i, (v, d) in enumerate(steps):
    c = box(s, cx[i] - 0.6, 2.6, 1.2, 1.2, fill=PURPLE, shape=MSO_SHAPE.OVAL)
    shape_text(c, [(str(i + 1), {"size": 36, "bold": True, "color": WHITE, "font": HEAD})])
    text(s, cx[i] - 1.35, 4.15, 2.7, 0.5, v, size=22, bold=True, color=PURPLE, align=PP_ALIGN.CENTER, font=HEAD)
    text(s, cx[i] - 1.3, 4.75, 2.6, 1.2, d, size=16, color=TXT, align=PP_ALIGN.CENTER)
source(s, "Fuente: Informe final, objetivos")
notes(s, "Objetivo general: evaluar el comportamiento de Bitcoin con estrategias de trading, seleccionando y optimizando la de mejor desempeño riesgo–rendimiento. Cada objetivo específico corresponde a un capítulo del informe.")

# =========================================================== 6. Protocolo
s = new()
title(s, "Mismas reglas para todas las estrategias",
      "BTC/USDT spot, Binance Data Vision")
bx, by, bw, bh = L, 1.85, W_CONTENT - 0.05, 0.75
b = box(s, bx, by, bw * 0.70, bh, fill=PURPLE, shape=MSO_SHAPE.RECTANGLE)
shape_text(b, [("Backtesting  ·  70 % de los datos", {"bold": True, "color": WHITE, "size": 17})])
b = box(s, bx + bw * 0.70, by, bw * 0.30, bh, fill=ORANGE, shape=MSO_SHAPE.RECTANGLE)
shape_text(b, [("Forward testing  ·  30 %", {"bold": True, "color": DARK, "size": 17})])
for xx, lab, al in [(bx, "17 ago 2017", PP_ALIGN.LEFT), (bx + bw * 0.70 - 1.0, "16 dic 2023", PP_ALIGN.CENTER),
                    (bx + bw - 2.0, "1 sep 2026", PP_ALIGN.RIGHT)]:
    text(s, xx, by + bh + 0.08, 2.0, 0.3, lab, size=13, color=MUTED, align=al)
tiles = [("4 h", "por vela"), ("19.800", "velas"), ("10.000", "USDT de capital"),
         ("0,15 %", "comisión por compra o venta"), ("1 vela", "de retraso"), ("Largos", "sin cortos ni apalancamiento")]
tw = (W_CONTENT - 0.05 - 5 * 0.2) / 6
for i, (n, lab) in enumerate(tiles):
    b = box(s, L + i * (tw + 0.2), 3.3, tw, 1.35, fill=LIGHT, radius=0.1)
    shape_text(b, [(n + "\n", {"size": 26 if len(n) < 8 else 20, "bold": True, "color": PURPLE, "font": HEAD}),
                   (lab, {"size": 13, "color": TXT})])
text(s, L, 4.95, 6, 0.35, "Estrategias evaluadas", size=15, bold=True, color=TXT)
strats = ["Buy & Hold", "RSI", "MACD", "SMA", "EMA", "CCI", "E2-A A2"]
cwid = (W_CONTENT - 0.05 - 6 * 0.15) / 7
for i, n in enumerate(strats):
    fill = PURPLE if n == "E2-A A2" else (ORANGE if n == "SMA" else (DARK if n == "Buy & Hold" else LIGHT))
    tc = WHITE if n in ("E2-A A2", "Buy & Hold") else (DARK if n == "SMA" else TXT)
    b = box(s, L + i * (cwid + 0.15), 5.4, cwid, 0.55, fill=fill, radius=0.3)
    shape_text(b, [(n, {"bold": True, "color": tc, "size": 14})])
    b.text_frame.margin_left = b.text_frame.margin_right = Inches(0.02)
source(s, "Fuente: Informe, cap. II. Comisión 0,10 % + deslizamiento 0,05 %")
notes(s, "Una sola fuente de datos y un solo motor de simulación. El 70 % inicial se usa para construir y el 30 % final, que la estrategia no vio, para validar. Costos de 0,10 % de comisión más 0,05 % de deslizamiento por lado. La señal se ejecuta una vela después para no usar información del futuro. Buy & Hold es la referencia pasiva.")

# =========================================================== 7. Separador
separator("Evaluación", 1)

# =========================================================== 8. Equity
s = new()
title(s, "SMA y Buy & Hold ganaron más que E2-A A2",
      "Evolución de 10.000 USDT, escala logarítmica")
cd = XyChartData()
for k in ["BH", "SMA", "E2A_A2"]:
    se = cd.add_series(NAMES[k])
    for r in weekly:
        se.add_data_point(yearfrac(r["timestamp"]), float(r[f"eq_{k}"]))
gf = s.shapes.add_chart(XL_CHART_TYPE.XY_SCATTER_LINES_NO_MARKERS, Inches(L - 0.1), Inches(1.6),
                        Inches(8.4), Inches(4.95), cd)
ch = gf.chart
style_chart(ch)
ch.has_legend = False
for se, k in zip(ch.series, ["BH", "SMA", "E2A_A2"]):
    color_series(se, COL[k], width=2.75 if k == "E2A_A2" else 2.0)
quiet_axis(ch.category_axis, "0", 2017, 2027, 1, grid=False)
va = ch.value_axis
quiet_axis(va, '#,##0," mil"', 5000, 1000000)
log_axis(va)
cards = [("SMA", "57,48 %", ORANGE, DARK), ("Buy & Hold", "37,48 %", DARK, WHITE), ("E2-A A2", "17,08 %", PURPLE, WHITE)]
text(s, 9.15, 1.7, 3.0, 0.6, "Crecimiento anual\ncompuesto (CAGR)", size=14, color=MUTED)
for i, (n, v, c, tc) in enumerate(cards):
    b = box(s, 9.15, 2.55 + i * 1.3, 3.0, 1.1, fill=c, radius=0.1)
    shape_text(b, [(v + "\n", {"size": 28, "bold": True, "color": tc, "font": HEAD}), (n, {"size": 14, "color": tc, "bold": True})])
source(s, "Fuente: Informe final, Tabla 2; elaboración propia")
notes(s, "Si solo miramos rentabilidad, SMA gana: 57,48 % anual frente a 37,48 % de Buy & Hold y 17,08 % de E2-A A2. Pero esta curva no muestra cuánto sufrió el capital en el camino; eso es la siguiente diapositiva.")

# =========================================================== 9. Drawdown
s = new()
title(s, "Pero SMA cayó 71 % y Buy & Hold 84 %",
      "Caída del capital desde su máximo anterior")
cd = XyChartData()
for k in ["BH", "SMA", "E2A_A2"]:
    se = cd.add_series(NAMES[k])
    for r in weekly:
        se.add_data_point(yearfrac(r["timestamp"]), float(r[f"dd_{k}"]) * 100)
gf = s.shapes.add_chart(XL_CHART_TYPE.XY_SCATTER_LINES_NO_MARKERS, Inches(L - 0.1), Inches(1.6),
                        Inches(7.6), Inches(4.95), cd)
ch = gf.chart
style_chart(ch)
ch.has_legend = True
ch.legend.include_in_layout = False
ch.legend.position = XL_LEGEND_POSITION.BOTTOM
ch.legend.font.size = Pt(13)
for se, k in zip(ch.series, ["BH", "SMA", "E2A_A2"]):
    color_series(se, COL[k], width=2.75 if k == "E2A_A2" else 1.75)
quiet_axis(ch.category_axis, "0", 2017, 2027, 1, grid=False)
ch.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.LOW
quiet_axis(ch.value_axis, '0" %"', -90, 0, 15)
# panel de recuperacion
text(s, 8.45, 1.65, 3.8, 0.75, "Ganancia necesaria para recuperar la caída máxima", size=15, bold=True, color=TXT)
rec = [("Buy & Hold", -83.91, DARK), ("SMA", -70.96, ORANGE), ("E2-A A2", -27.93, PURPLE)]
cd2 = CategoryChartData()
cd2.categories = [r[0] for r in rec]
cd2.add_series("Recuperación", [round((1 / (1 + r[1] / 100) - 1) * 100, 1) for r in rec])
gf2 = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(8.2), Inches(2.45), Inches(4.3), Inches(3.0), cd2)
c2 = gf2.chart
style_chart(c2, 13)
c2.has_legend = False
c2.has_title = False
pl_ = c2.plots[0]
pl_.gap_width = 45
pl_.has_data_labels = True
for i, (n, dd, c) in enumerate(rec):
    pt = pl_.series[0].points[i]
    pt.format.fill.solid()
    pt.format.fill.fore_color.rgb = c
    need = (1 / (1 + dd / 100) - 1) * 100
    tf = pt.data_label.text_frame
    tf.text = "+" + es(need, 1) + "%"
    tf.paragraphs[0].runs[0].font.bold = True
    tf.paragraphs[0].runs[0].font.size = Pt(13)
    pt.data_label.position = XL_LABEL_POSITION.OUTSIDE_END
c2.category_axis.reverse_order = True
c2.category_axis.format.line.fill.background()
c2.value_axis.visible = False
c2.value_axis.has_major_gridlines = False
c2.value_axis.maximum_scale = 760
c2.value_axis.minimum_scale = 0
text(s, 8.45, 5.55, 3.8, 0.9, [("Caída máx.: ", {"bold": True}), "Buy & Hold −83,91 %, SMA −70,96 %, E2-A A2 −27,93 %"],
     size=13, color=TXT)
source(s, "Fuente: Informe final, Tabla 2 y sección 1.3.6")
notes(s, "La caída máxima mide la peor pérdida desde un pico. La relación es asimétrica: quien pierde 84 % necesita ganar 521,5 % para volver al punto de partida; quien pierde 28 % necesita 39 %. E2-A A2 nunca cayó más de 27,93 %.")

# =========================================================== 10. Mapa riesgo-rendimiento
s = new()
title(s, "E2-A A2: la menor caída entre las rentables",
      "Rentabilidad anual frente a caída máxima, 2017–2026")
cd = XyChartData()
order = ["CCI", "RSI", "MACD", "EMA", "BH", "SMA", "E2A_A2"]
for k in order:
    se = cd.add_series(NAMES[k])
    se.add_data_point(T2[k][3], T2[k][1])
gf = s.shapes.add_chart(XL_CHART_TYPE.XY_SCATTER, Inches(L - 0.1), Inches(1.6), Inches(W_CONTENT), Inches(4.95), cd)
ch = gf.chart
style_chart(ch)
ch.has_legend = False
for se, k in zip(ch.series, order):
    c = COL.get(k, GREY)
    se.marker.style = XL_MARKER_STYLE.CIRCLE
    se.marker.size = 22 if k in COL else 14
    se.marker.format.fill.solid()
    se.marker.format.fill.fore_color.rgb = c
    se.marker.format.line.color.rgb = WHITE
    se.format.line.fill.background()
    pt = se.points[0]
    tf = pt.data_label.text_frame
    tf.text = NAMES[k]
    r0 = tf.paragraphs[0].runs[0]
    r0.font.size = Pt(15 if k in COL else 12)
    r0.font.bold = k in COL
    r0.font.color.rgb = c if k in COL else MUTED
    pt.data_label.position = XL_LABEL_POSITION.LEFT if k in ("E2A_A2",) else XL_LABEL_POSITION.RIGHT
    if k in ("E2A_A1",):
        pt.data_label.position = XL_LABEL_POSITION.BELOW
    if k in ("E2C",):
        pt.data_label.position = XL_LABEL_POSITION.RIGHT
quiet_axis(ch.category_axis, '0" %"', -90, 0, 10)
quiet_axis(ch.value_axis, '0" %"', 0, 65, 10)
ch.category_axis.has_title = True
ch.category_axis.axis_title.text_frame.text = "Caída máxima (más a la derecha = menos riesgo)"
ch.value_axis.has_title = True
ch.value_axis.axis_title.text_frame.text = "CAGR"
for t_ in (ch.category_axis.axis_title, ch.value_axis.axis_title):
    r0 = t_.text_frame.paragraphs[0].runs[0]
    r0.font.size, r0.font.bold, r0.font.color.rgb = Pt(13), False, MUTED
ch.value_axis.crosses_at = 0
ch.category_axis.crosses_at = -90
source(s, "Fuente: Informe final, Tabla 2 y Gráfica 1")
notes(s, "Arriba significa más rentabilidad; a la derecha, menos pérdida máxima. SMA, EMA y MACD rinden más pero con caídas de 60 % a 71 %. E2-A A2 está sola a la derecha: 17,08 % anual con −27,93 %.")

# =========================================================== 11. Separador
separator("Selección", 2)

# =========================================================== Calculo del Sharpe
EX = json.load(open(DATA / "extra.json", encoding="utf-8"))
a2x = EX["periods"]["FULL"]["A2_TPE"]
assert abs(a2x["sharpe_check"] - T2["E2A_A2"][0]) < 6e-4
s = new()
title(s, "Cómo se calcula el Sharpe",
      "Cuánto gana la estrategia por encima de una inversión sin riesgo, por cada unidad de volatilidad")
ORANGE_LIGHT = RGBColor(0xFF, 0xF1, 0xD6)
fx, fw_ = L + 1.7, 5.2
text(s, L, 2.05, 1.5, 0.7, "Sharpe =", size=24, bold=True, color=DARK, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
text(s, fx, 1.85, fw_, 0.5, [("Retorno medio", {"color": PURPLE, "bold": True}), ("  −  ", {"color": DARK}),
                             ("Tasa libre de riesgo", {"color": ORANGE_TXT, "bold": True})],
     size=20, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.BOTTOM)
line(s, fx, 2.42, fx + fw_, 2.42, color=DARK, width=2.25)
text(s, fx, 2.5, fw_, 0.5, [("Volatilidad", {"color": DARK, "bold": True}), ("  (desviación estándar)", {"color": MUTED})],
     size=20, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.TOP)
defs = [("Retorno medio", LILAC, PURPLE, "Lo que gana en promedio la estrategia en cada vela de 4 horas"),
        ("Tasa libre de riesgo", ORANGE_LIGHT, ORANGE_TXT, "Lo que daría una inversión sin riesgo: 4 % al año"),
        ("Volatilidad", LIGHT, DARK, "Cuánto suben y bajan los retornos (desviación estándar)")]
for i, (lab, fill, tc, d_) in enumerate(defs):
    y = 3.55 + i * 0.95
    c = box(s, L, y, 2.45, 0.62, fill=fill, radius=0.3)
    shape_text(c, [(lab, {"bold": True, "color": tc, "size": 15})])
    text(s, L + 2.65, y, 4.3, 0.62, d_, size=15, color=TXT, anchor=MSO_ANCHOR.MIDDLE)
# tasa libre de riesgo
rx, rw = 7.95, 4.3
b = box(s, rx, 1.7, rw, 1.75, fill=PURPLE, radius=0.08)
text(s, rx + 0.25, 1.82, rw - 0.5, 0.4, "Tasa libre de riesgo", size=14, bold=True, color=WHITE)
text(s, rx + 0.25, 2.2, 1.7, 0.75, "4 %", size=40, bold=True, color=WHITE, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
text(s, rx + 1.85, 2.27, rw - 2.0, 0.75, "anual\nBonos del Tesoro de EE. UU. a 10 años", size=13, color=WHITE)
text(s, rx + 0.25, 3.0, rw - 0.5, 0.35, "Por vela: 4 % / 2.190 = 0,001826 %", size=13, bold=True, color=WHITE)
# ejemplo
b = box(s, rx, 3.65, rw, 2.82, fill=LIGHT, radius=0.06)
text(s, rx + 0.25, 3.75, rw - 0.5, 0.35, "Ejemplo: E2-A A2, 2017–2026", size=14, bold=True, color=PURPLE)
rows_ = [("Retorno medio por vela", "0,007696 %"), ("− Tasa libre de riesgo", "0,001826 %"),
         ("= Retorno en exceso", "0,005869 %"), ("÷ Volatilidad por vela", "0,3149 %")]
for i, (lab, v) in enumerate(rows_):
    y = 4.15 + i * 0.36
    text(s, rx + 0.25, y, 2.55, 0.34, lab, size=13, color=TXT, bold=lab.startswith("="))
    text(s, rx + 2.65, y, 1.4, 0.34, v, size=13, color=TXT, align=PP_ALIGN.RIGHT, bold=lab.startswith("="))
line(s, rx + 0.25, 5.62, rx + rw - 0.25, 5.62, color=GREY, width=1)
text(s, rx + 0.25, 5.72, 2.6, 0.6, "(0,005869 / 0,3149) × √2.190", size=13, color=TXT, anchor=MSO_ANCHOR.MIDDLE)
text(s, rx + 2.75, 5.67, 1.3, 0.7, "0,872", size=28, bold=True, color=PURPLE, font=HEAD, align=PP_ALIGN.RIGHT,
     anchor=MSO_ANCHOR.MIDDLE)
source(s, "Fuente: Informe final, sección 1.3.6 y Tabla 2; motor del proyecto")
notes(s, "El Sharpe es el retorno medio menos la tasa libre de riesgo, dividido por la volatilidad. Usamos 4 % anual, la referencia de los bonos del Tesoro de EE. UU. a 10 años, que por vela de 4 horas equivale a 0,001826 %. Para pasarlo a años se multiplica por la raíz de 2.190 velas al año. Para E2-A A2: exceso de 0,005869 % por vela entre una volatilidad de 0,3149 %, por raíz de 2.190, da 0,872.")

# =========================================================== 12. Sharpe no basta
s = new()
title(s, "El Sharpe más alto no implica el menor riesgo",
      "Ratio de Sharpe con tasa libre de riesgo de 4 % anual")
srt = sorted([k for k in T2 if k not in ("E2A_A1", "E2C")], key=lambda k: T2[k][0], reverse=True)
cd = CategoryChartData()
cd.categories = [NAMES[k] for k in srt]
cd.add_series("Sharpe", [T2[k][0] for k in srt])
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(L - 0.1), Inches(1.6), Inches(6.2), Inches(4.95), cd)
ch = gf.chart
style_chart(ch, 13)
ch.has_legend = False
ch.has_title = False
p = ch.plots[0]
p.gap_width = 40
p.has_data_labels = True
for i, k in enumerate(srt):
    pt = p.series[0].points[i]
    pt.format.fill.solid()
    pt.format.fill.fore_color.rgb = COL.get(k, GREY)
    pt.data_label.text_frame.text = es(T2[k][0], 3)
    pt.data_label.text_frame.paragraphs[0].runs[0].font.size = Pt(12)
    pt.data_label.text_frame.paragraphs[0].runs[0].font.bold = k in COL
    pt.data_label.position = XL_LABEL_POSITION.OUTSIDE_END
p.series[0].invert_if_negative = False
ch.category_axis.reverse_order = True
ch.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.LOW
ch.category_axis.format.line.color.rgb = RGBColor(0xCC, 0xCC, 0xCC)
ch.value_axis.visible = False
ch.value_axis.has_major_gridlines = False
ch.value_axis.minimum_scale, ch.value_axis.maximum_scale = 0, 1.35
# comparativa
cmp_ = [("SMA", ORANGE, DARK), ("E2-A A2", PURPLE, WHITE), ("Buy & Hold", DARK, WHITE)]
keys = {"SMA": "SMA", "E2-A A2": "E2A_A2", "Buy & Hold": "BH"}
gx = 7.15
text(s, gx + 1.45, 1.75, 1.5, 0.35, "Sharpe", size=13, bold=True, color=MUTED, align=PP_ALIGN.CENTER)
text(s, gx + 3.0, 1.75, 1.6, 0.35, "Caída máx.", size=13, bold=True, color=MUTED, align=PP_ALIGN.CENTER)
for i, (n, c, tc) in enumerate(cmp_):
    k = keys[n]
    y = 2.2 + i * 1.05
    b = box(s, gx, y, 1.35, 0.85, fill=c, radius=0.12)
    shape_text(b, [(n, {"bold": True, "color": tc, "size": 14})])
    text(s, gx + 1.45, y, 1.5, 0.85, es(T2[k][0], 3), size=26, bold=True, color=TXT, align=PP_ALIGN.CENTER,
         anchor=MSO_ANCHOR.MIDDLE, font=HEAD)
    text(s, gx + 3.0, y, 1.6, 0.85, es(T2[k][3]) + " %", size=24, bold=True,
         color=PURPLE if k == "E2A_A2" else TXT, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, font=HEAD)
b = box(s, gx, 5.45, 4.65, 0.95, fill=LILAC, radius=0.1)
shape_text(b, "Criterios de selección: Sharpe, caída máxima, consistencia fuera de muestra y número de operaciones",
           size=13, color=TXT, align=PP_ALIGN.LEFT)
source(s, "Fuente: Informe final, Tablas 2 y 4")
notes(s, "El Sharpe mide rentabilidad por unidad de volatilidad. SMA tiene el mejor (1,123), pero con caída de −70,96 %. E2-A A2 tiene Sharpe 0,872, mejor que Buy & Hold (0,749), con una caída de solo −27,93 %. Por eso el Sharpe se complementa con la caída máxima, la consistencia y el número de operaciones.")

# =========================================================== 13. Perfiles
s = new()
title(s, "Acertar más no siempre significa ganar más",
      "Porcentaje de operaciones ganadoras frente a factor de beneficio")
cd = XyChartData()
order3 = ["MACD", "RSI", "CCI", "EMA", "SMA", "E2A_A2"]
for k in order3:
    se = cd.add_series(NAMES[k])
    se.add_data_point(T3[k][1], T3[k][2])
gf = s.shapes.add_chart(XL_CHART_TYPE.XY_SCATTER, Inches(L - 0.1), Inches(1.6), Inches(7.9), Inches(4.95), cd)
ch = gf.chart
style_chart(ch)
ch.has_legend = False
lab_pos = {"SMA": XL_LABEL_POSITION.RIGHT, "EMA": XL_LABEL_POSITION.RIGHT, "MACD": XL_LABEL_POSITION.RIGHT,
           "E2C": XL_LABEL_POSITION.RIGHT, "E2A_A1": XL_LABEL_POSITION.RIGHT, "RSI": XL_LABEL_POSITION.BELOW,
           "CCI": XL_LABEL_POSITION.ABOVE, "E2A_A2": XL_LABEL_POSITION.LEFT}
for se, k in zip(ch.series, order3):
    c = COL.get(k, GREY)
    se.marker.style = XL_MARKER_STYLE.CIRCLE
    se.marker.size = 22 if k in COL else 14
    se.marker.format.fill.solid()
    se.marker.format.fill.fore_color.rgb = c
    se.marker.format.line.color.rgb = WHITE
    se.format.line.fill.background()
    pt = se.points[0]
    pt.data_label.text_frame.text = NAMES[k]
    r0 = pt.data_label.text_frame.paragraphs[0].runs[0]
    r0.font.size, r0.font.bold = Pt(15 if k in COL else 12), k in COL
    r0.font.color.rgb = c if k in COL else MUTED
    pt.data_label.position = lab_pos[k]
quiet_axis(ch.category_axis, '0" %"', 20, 85, 10)
quiet_axis(ch.value_axis, '0.0', 0, 5, 1)
ch.category_axis.has_title = True
ch.category_axis.axis_title.text_frame.text = "Operaciones ganadoras"
ch.value_axis.has_title = True
ch.value_axis.axis_title.text_frame.text = "Factor de beneficio"
for t_ in (ch.category_axis.axis_title, ch.value_axis.axis_title):
    r0 = t_.text_frame.paragraphs[0].runs[0]
    r0.font.size, r0.font.bold, r0.font.color.rgb = Pt(13), False, MUTED
prof = [("SMA y EMA", "Aciertan 1 de cada 3, pero cada ganancia es grande (factor 4,41 y 3,68)", ORANGE),
        ("CCI y RSI", "Aciertan 3 de cada 4, pero ganan poco (factor 1,29 y 1,22)", GREY),
        ("E2-A A2", "Acierta 76,92 % y gana 3,17 por cada unidad perdida", PURPLE)]
for i, (n, d, c) in enumerate(prof):
    y = 1.75 + i * 1.55
    dot = box(s, 8.75, y + 0.06, 0.3, 0.3, fill=c, shape=MSO_SHAPE.OVAL)
    text(s, 9.2, y, 3.1, 0.4, n, size=17, bold=True, color=PURPLE if c == PURPLE else TXT)
    text(s, 9.2, y + 0.42, 3.1, 1.0, d, size=14, color=TXT)
source(s, "Fuente: Informe final, Tabla 3")
notes(s, "El factor de beneficio es lo que se gana por cada unidad perdida. Acertar mucho no basta: CCI y RSI aciertan más del 69 % pero ganan poco. SMA y EMA aciertan solo un tercio pero sus ganancias son grandes. E2-A A2 combina las dos cosas.")

# =========================================================== 14. Exposicion
s = new()
title(s, "E2-A A2 opera solo el 9,3 % del tiempo",
      "Periodos con posición abierta, 2017–2026")
s.shapes.add_picture(str(IMG / "barcode_exposicion.png"), Inches(L), Inches(1.75), width=Inches(10.0))
text(s, 10.95, 1.95, 1.4, 0.5, "51,8 %", size=22, bold=True, color=ORANGE_TXT, font=HEAD)
text(s, 10.95, 2.9, 1.4, 0.5, "9,3 %", size=22, bold=True, color=PURPLE, font=HEAD)
stats = [("39", "operaciones en 9 años"), ("76,92 %", "de operaciones ganadoras"), ("3,17", "factor de beneficio")]
sw = (W_CONTENT - 0.05 - 2 * 0.3) / 3
for i, (n, lab) in enumerate(stats):
    b = box(s, L + i * (sw + 0.3), 4.35, sw, 1.75, fill=LILAC, radius=0.1)
    shape_text(b, [(n + "\n", {"size": 40, "bold": True, "color": PURPLE, "font": HEAD}), (lab, {"size": 16, "color": TXT})])
source(s, "Fuente: Informe final, Tabla 3; elaboración propia")
notes(s, "Cada franja es un periodo con posición abierta. SMA está dentro la mitad del tiempo; E2-A A2 solo entra cuando coinciden tendencia, impulso y volumen. Por eso hace 39 operaciones en nueve años y queda menos expuesta a los periodos laterales y a las caídas.")

# =========================================================== 15. Anatomia
s = new()
title(s, "E2-A A2 compra solo si tres filtros coinciden",
      "Operación del backtest: 6 al 11 de noviembre de 2024")
filters = [("Tendencia", "SMA 18 por encima de SMA 221"),
           ("Impulso", "CCI 58 cruza −3 hacia arriba"),
           ("Participación", "Volumen z mayor a 0,58")]
chev = str(CHEVRON)
for i, (n, d) in enumerate(filters):
    y = 1.8 + i * 1.05
    b = box(s, L, y, 4.6, 0.9, fill=LIGHT, radius=0.12)
    s.shapes.add_picture(chev, Inches(L + 0.18), Inches(y + 0.22), Inches(0.46), Inches(0.46))
    text(s, L + 0.85, y + 0.1, 3.6, 0.35, f"{i + 1}. {n}", size=16, bold=True, color=PURPLE)
    text(s, L + 0.85, y + 0.47, 3.6, 0.35, d, size=14, color=TXT)
b = box(s, L, 5.05, 4.6, 1.25, fill=PURPLE, radius=0.1)
shape_text(b, [("Salida\n", {"bold": True, "size": 16, "color": WHITE}),
               ("CCI mayor a 186, o SMA 18 cruza bajo SMA 221", {"size": 14, "color": WHITE})],
           align=PP_ALIGN.LEFT)
s.shapes.add_picture(str(IMG / "anatomia_operacion.png"), Inches(5.75), Inches(1.6), height=Inches(4.95))
source(s, "Fuente: Informe final, Tabla 5 (parámetros A2); elaboración propia")
notes(s, "Ejemplo real del backtest. El 6 de noviembre de 2024 la tendencia era alcista, el CCI cruzó hacia arriba y el volumen superó su umbral: la estrategia compró. Salió el 11 de noviembre cuando el CCI pasó de 186. Ganancia bruta de 20,8 %. Los tres filtros reducen las señales falsas.")

# =========================================================== 16. Separador
separator("Optimización\ny bot", 3)

# =========================================================== PSO vs TPE: como funcionan
s = new()
title(s, "Dos formas de buscar los mejores parámetros",
      "Técnicas de inteligencia artificial usadas para calibrar E2-A")
cards_ = [
    (L, RGBColor(0x5B, 0x6B, 0x7B), "PSO · Enjambre de partículas", "pso_simple.png", "✕",
     "Muchas soluciones se mueven juntas hacia la mejor que encuentran. En E2-A terminaron amontonadas "
     "en los bordes del rango: se ajustó demasiado al pasado."),
    (6.8, PURPLE, "TPE · Optimización bayesiana", "tpe_simple.png", "✓",
     "Aprende de cada intento y prueba el siguiente donde hubo mejores resultados. Se calibró con años "
     "que no usó para entrenar: generaliza mejor."),
]
for x, c, head, img, icon, desc in cards_:
    cw_ = 5.45
    card = box(s, x, 1.6, cw_, 4.9, fill=WHITE, line=c, radius=0.04)
    card.line.width = Pt(3)
    text(s, x + 0.3, 1.75, cw_ - 1.2, 0.5, head, size=19, bold=True, color=c, font=HEAD, anchor=MSO_ANCHOR.MIDDLE)
    ic = box(s, x + cw_ - 0.8, 1.75, 0.5, 0.5, fill=c, shape=MSO_SHAPE.OVAL)
    shape_text(ic, [(icon, {"bold": True, "color": WHITE, "size": 18})])
    dp = s.shapes.add_picture(str(IMG / img), Inches(x), Inches(2.35), height=Inches(2.75))
    dp.left = Inches(x + cw_ / 2) - dp.width // 2
    text(s, x + 0.3, 5.2, cw_ - 0.6, 1.2, desc, size=15, color=TXT)
source(s, "Fuente: Informe final, sección 1.3.7 y conclusiones; código del proyecto")
notes(s, "PSO, optimización por enjambre de partículas, es la técnica que usa la literatura. Muchas soluciones candidatas se mueven juntas hacia la mejor que van encontrando. En E2-A se amontonaron en los bordes del rango de búsqueda, señal de sobreajuste. TPE, optimización bayesiana, aprende de cada intento: compara las combinaciones que dieron buenos y malos resultados y prueba la siguiente donde hubo mejores. Además, lo evaluamos con años que no usó para calibrar.")

# =========================================================== PSO vs TPE: resultado
s = new()
title(s, "PSO se ajustó al pasado; TPE generalizó",
      "E2-A con parámetros PSO (Tabla 5) frente a E2-A A2 calibrada con TPE")
EXP = EX["periods"]
cd = CategoryChartData()
cd.categories = ["E2-A PSO", "E2-A A2 (TPE)"]
cd.add_series("Dentro de muestra (70 %)", [EXP["IS70"]["PSO_informe"]["sharpe"], EXP["IS70"]["A2_TPE"]["sharpe"]])
cd.add_series("Fuera de muestra (30 %)", [EXP["OOS30"]["PSO_informe"]["sharpe"], EXP["OOS30"]["A2_TPE"]["sharpe"]])
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(L - 0.1), Inches(1.7), Inches(5.9), Inches(4.0), cd)
ch = gf.chart
style_chart(ch, 13)
ch.has_title = False
ch.has_legend = True
ch.legend.position = XL_LEGEND_POSITION.TOP
ch.legend.include_in_layout = False
ch.legend.font.size = Pt(13)
ch.plots[0].gap_width = 70
ch.plots[0].overlap = -8
for se, c in zip(ch.series, [GREY, PURPLE]):
    se.format.fill.solid(); se.format.fill.fore_color.rgb = c
    for i, v in enumerate(se.values):
        pt = se.points[i]
        pt.data_label.text_frame.text = es(v, 3)
        r0 = pt.data_label.text_frame.paragraphs[0].runs[0]
        r0.font.size, r0.font.bold = Pt(15), True
        pt.data_label.position = XL_LABEL_POSITION.OUTSIDE_END
ch.value_axis.visible = False
ch.value_axis.has_major_gridlines = False
ch.value_axis.minimum_scale, ch.value_axis.maximum_scale = 0, 1.8
ch.category_axis.format.line.color.rgb = RGBColor(0xCC, 0xCC, 0xCC)
ch.category_axis.tick_labels.font.size = Pt(14)
ch.category_axis.tick_labels.font.bold = True
b = box(s, L, 5.8, 5.7, 0.68, fill=LILAC, radius=0.12)
shape_text(b, [("Sharpe de PSO: 1,526 → 0,699.  ", {"bold": True, "size": 13}),
               ("TPE: 0,762 → 1,412", {"bold": True, "size": 13, "color": PURPLE})], align=PP_ALIGN.LEFT)
text(s, 6.85, 1.7, 5.4, 0.4, "4 de 7 parámetros de PSO quedaron en el borde de la búsqueda", size=14, bold=True, color=TXT)
s.shapes.add_picture(str(IMG / "pso_limites.png"), Inches(6.95), Inches(2.1), height=Inches(4.35))
source(s, "Fuente: backtest del proyecto (70/30); parámetros PSO: Informe, Tabla 5")
notes(s, "Con los parámetros de PSO, E2-A tenía Sharpe 1,526 en el 70 % con que se calibró, pero cayó a 0,699 en el 30 % que no vio. Con TPE pasó lo contrario: 0,762 dentro de muestra y 1,412 fuera. A la derecha, el rango de búsqueda de cada parámetro: cuatro de los siete valores de PSO quedaron pegados al borde, señal de que el algoritmo se ajustaba a los datos de entrenamiento y no a un patrón estable. Por eso se descartó PSO.")

# =========================================================== 17. Parametros TPE
s = new()
title(s, "TPE calibró E2-A para Bitcoin",
      "Parámetros del artículo original (A1) frente a la calibración con TPE (A2)")
params = [("Periodo CCI", "20", "58"), ("Entrada CCI", "−100", "−3"), ("Salida CCI", "100", "186"),
          ("SMA rápida / lenta", "20 / 50", "18 / 221"), ("Volumen: ventana / umbral", "20 / 0,50", "40 / 0,58")]
text(s, L + 3.3, 1.7, 1.6, 0.35, "Original", size=14, bold=True, color=MUTED, align=PP_ALIGN.CENTER)
text(s, L + 5.35, 1.7, 1.7, 0.35, "TPE", size=14, bold=True, color=PURPLE, align=PP_ALIGN.CENTER)
for i, (n, a, b_) in enumerate(params):
    y = 2.15 + i * 0.78
    box(s, L, y, 7.15, 0.66, fill=LIGHT, radius=0.15)
    text(s, L + 0.2, y, 3.0, 0.66, n, size=15, bold=True, color=TXT, anchor=MSO_ANCHOR.MIDDLE)
    text(s, L + 3.3, y, 1.6, 0.66, a, size=17, color=MUTED, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    line(s, L + 4.85, y + 0.33, L + 5.4, y + 0.33, color=PURPLE, width=2, arrow=True)
    text(s, L + 5.35, y, 1.7, 0.66, b_, size=19, bold=True, color=PURPLE, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, font=HEAD)
# resultado
rx = 8.35
text(s, rx, 1.7, 3.9, 0.35, "Resultado 2017–2026", size=14, bold=True, color=MUTED)
for i, (lab, a, b_) in enumerate([("Sharpe", "−1,463", "0,872"), ("CAGR", "−2,92 %", "17,08 %"),
                                  ("Operaciones ganadoras", "23,33 %", "76,92 %")]):
    y = 2.15 + i * 1.32
    box(s, rx, y, 3.9, 1.18, fill=LILAC, radius=0.1)
    text(s, rx + 0.2, y + 0.08, 3.5, 0.35, lab, size=14, bold=True, color=TXT)
    text(s, rx + 0.2, y + 0.45, 3.5, 0.62, [(a, {"color": MUTED, "size": 18}), ("   →   ", {"color": PURPLE, "size": 18}),
                                            (b_, {"color": PURPLE, "size": 26, "bold": True, "font": HEAD})], size=18)
text(s, L, 6.0, 7.2, 0.5, "Objetivo de TPE: mediana del Sharpe fuera de muestra 2021–2024. Búsqueda de 150 ensayos; la re-selección con 100 ensayos (semilla 42) confirmó los mismos parámetros",
     size=12, color=MUTED)
source(s, "Fuente: Informe final, Tablas 2, 3 y 5")
notes(s, "TPE (Tree-structured Parzen Estimator) es un optimizador bayesiano: usa los ensayos anteriores para decidir qué combinación probar después. Los parámetros del artículo original daban Sharpe negativo en Bitcoin; calibrados con TPE, la misma lógica pasa a Sharpe 0,872. También sube el porcentaje de operaciones ganadoras, de 23,33 % a 76,92 %.")

# =========================================================== 18. Bot
s = new()
title(s, "Un bot ejecuta la estrategia cada 4 horas",
      "Binance, entorno Demo · velas de 4 horas")
flow = [("Datos", "Velas 4H de Binance"), ("Señal", "Filtros SMA, CCI y volumen"),
        ("Orden", "Compra o venta a mercado por API"), ("Registro", "Órdenes, posición y estado")]
fw = (W_CONTENT - 0.05 - 3 * 0.5) / 4
for i, (n, d) in enumerate(flow):
    x = L + i * (fw + 0.5)
    b = box(s, x, 1.8, fw, 1.35, fill=PURPLE if i == 1 else LIGHT, radius=0.1)
    tc = WHITE if i == 1 else TXT
    shape_text(b, [(n + "\n", {"size": 20, "bold": True, "color": WHITE if i == 1 else PURPLE, "font": HEAD}),
                   (d, {"size": 14, "color": tc})])
    if i < 3:
        line(s, x + fw + 0.07, 2.47, x + fw + 0.43, 2.47, color=PURPLE, width=2.5, arrow=True)
pic = s.shapes.add_picture(str(IMG / "ordenes_binance.png"), Inches(L), Inches(3.55), width=Inches(9.0))
pic.crop_bottom = 0.42
pic.height = int(pic.height * 0.58)
text(s, 10.0, 3.6, 2.2, 2.6, [("Registro real de órdenes\n", {"bold": True, "size": 15, "color": TXT}),
                              ("30 sep: compra\n2 oct: venta\n0,0119 BTC por orden", {"size": 14, "color": TXT})], size=14)
source(s, "Fuente: Informe final, Gráficas 2, 4 y 5; Binance")
notes(s, "El bot repite cada 4 horas el mismo ciclo: descarga la vela, calcula los tres filtros, envía la orden por API y registra lo ocurrido. Funcionó 30 días en el entorno de pruebas de Binance. La captura es el historial de órdenes.")

# =========================================================== 19. Prueba en vivo
s = new()
title(s, "Un corte de energía obligó a cerrar a mano",
      "Prueba de 30 días, septiembre–octubre de 2026")
ev = [("30 sep", "Compra a 84.140,36 USDT", PURPLE), ("1–2 oct", "Cortes de energía: el equipo se reinicia", ORANGE),
      ("2 oct", "Cierre manual a 84.434,00 USDT", DARK)]
line(s, L + 0.3, 2.35, L + 5.0, 2.35, color=GREY, width=3)
for i, (d, t_, c) in enumerate(ev):
    x = L + 0.3 + i * 2.35
    box(s, x - 0.22, 2.13, 0.44, 0.44, fill=c, shape=MSO_SHAPE.OVAL)
    text(s, x - 0.3, 1.62, 2.1, 0.4, d, size=16, bold=True, color=c if c != ORANGE else ORANGE_TXT)
    text(s, x - 0.3, 2.75, 2.1, 1.2, t_, size=14, color=TXT)
b = box(s, L, 4.25, 6.7, 1.9, fill=LILAC, radius=0.08)
shape_text(b, [("Lección operativa\n", {"bold": True, "size": 17, "color": PURPLE}),
               ("Al reiniciarse, el bot debe recuperar su estado y conciliar la posición abierta con el exchange. "
                "La continuidad operativa también es parte del control del riesgo.", {"size": 15, "color": TXT})],
           align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE)
text(s, 8.1, 1.65, 4.2, 0.7, "Pérdida estimada sin intervención manual", size=15, bold=True, color=TXT)
cd = CategoryChartData()
cd.categories = ["Estrategia E2-A", "Buy & Hold"]
cd.add_series("Pérdida", [3.41, 6.30])
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(7.85), Inches(2.4), Inches(4.65), Inches(2.6), cd)
ch = gf.chart
style_chart(ch, 14)
ch.has_legend = False
ch.has_title = False
p = ch.plots[0]
p.gap_width = 45
for i, (c, v) in enumerate([(PURPLE, "−3,41%"), (DARK, "−6,30%")]):
    pt = p.series[0].points[i]
    pt.format.fill.solid()
    pt.format.fill.fore_color.rgb = c
    pt.data_label.text_frame.text = v
    pt.data_label.text_frame.paragraphs[0].runs[0].font.size = Pt(16)
    pt.data_label.text_frame.paragraphs[0].runs[0].font.bold = True
    pt.data_label.position = XL_LABEL_POSITION.OUTSIDE_END
ch.value_axis.visible = False
ch.value_axis.has_major_gridlines = False
ch.value_axis.minimum_scale, ch.value_axis.maximum_scale = 0, 9.5
ch.category_axis.reverse_order = True
ch.category_axis.format.line.color.rgb = RGBColor(0xCC, 0xCC, 0xCC)
text(s, 8.1, 5.15, 4.1, 0.9, "Escenario de la regla de salida, según el informe (Tabla 6)", size=12, color=MUTED)
source(s, "Fuente: Informe final, cap. IV y Tabla 6; registro de órdenes de Binance")
notes(s, "Entrada el 30 de septiembre. Entre el 1 y el 2 de octubre hubo cortes de energía y el equipo se reinició; la posición se cerró a mano el 2 de octubre. Según el informe (Tabla 6), si la estrategia hubiera seguido su regla, la pérdida estimada era −3,41 % frente a −6,30 % de Buy & Hold. La lección es que el bot debe guardar su estado y reconciliar posiciones al reiniciar.")

# =========================================================== 20. Conclusiones
s = new()
title(s, "Conclusiones")
concl = [("Objetivo 1", "3 de 8", "referencias usan Bitcoin, cada una con otra temporalidad y otro método"),
         ("Objetivo 2", "7", "estrategias comparadas con los mismos datos, costos y reglas"),
         ("Objetivo 3", "−27,93 %", "caída máxima de E2-A A2, frente a −70,96 % de SMA y −83,91 % de Buy & Hold"),
         ("Objetivo 4", "0,872", "Sharpe de E2-A tras calibrar con TPE; el bot operó 30 días en Binance Demo")]
cw4 = (W_CONTENT - 0.05 - 3 * 0.25) / 4
for i, (o, n, d) in enumerate(concl):
    x = L + i * (cw4 + 0.25)
    b = box(s, x, 1.5, cw4, 3.55, fill=PURPLE if i == 2 else LIGHT, radius=0.08)
    tc = WHITE if i == 2 else TXT
    text(s, x + 0.25, 1.7, cw4 - 0.5, 0.35, o, size=14, bold=True, color=WHITE if i == 2 else MUTED)
    text(s, x + 0.25, 2.15, cw4 - 0.5, 0.8, n, size=34, bold=True, color=WHITE if i == 2 else PURPLE, font=HEAD)
    text(s, x + 0.25, 3.05, cw4 - 0.5, 1.9, d, size=15, color=tc)
b = box(s, L, 5.3, W_CONTENT - 0.05, 1.1, fill=None, line=ORANGE, radius=0.1)
shape_text(b, [("Trabajo futuro:  ", {"bold": True, "size": 15, "color": ORANGE_TXT}),
               ("reglas de toma de ganancias  ·  validación en otros ciclos de Bitcoin  ·  más tiempo de operación del bot antes de usar capital real",
                {"size": 15, "color": TXT})], align=PP_ALIGN.LEFT)
notes(s, "Conclusión general: E2-A A2 equilibra rentabilidad y control del riesgo. No maximiza la ganancia, pero limita la caída a −27,93 %. Antes de usar capital real hace falta probarla en otros ciclos y mejorar la toma de ganancias.")

# =========================================================== 21. Cierre
s = new("close")
text(s, 1.0, 0.9, 11.33, 1.1, "Gracias", size=60, bold=True, color=WHITE, align=PP_ALIGN.CENTER, font=HEAD)
text(s, 1.0, 2.05, 11.33, 0.6, "Preguntas y comentarios", size=24, color=WHITE, align=PP_ALIGN.CENTER)
text(s, 1.0, 5.75, 11.33, 0.4, "Código: github.com/Juandivox/bitcoin-trading-strategy-analysis", size=15,
     color=WHITE, align=PP_ALIGN.CENTER)
notes(s, "Cierre. A partir de aquí, diapositivas de respaldo para preguntas.")

# =========================================================== Anexos
separator("Anexos", 4)

s = new()
title(s, "Anexo A. Resultados de las estrategias", "Informe final, Tabla 2")
hdr = ["Estrategia", "Sharpe", "CAGR", "Volatilidad anual", "Caída máxima"]
srt = sorted([k for k in T2 if k not in ("E2A_A1", "E2C")], key=lambda k: T2[k][0], reverse=True)
tb = s.shapes.add_table(len(srt) + 1, 5, Inches(L), Inches(1.65), Inches(W_CONTENT - 0.6), Inches(4.7)).table
for j, h in enumerate(hdr):
    c = tb.cell(0, j)
    c.text = h
    c.fill.solid(); c.fill.fore_color.rgb = PURPLE
for i, k in enumerate(srt, start=1):
    sh, cg, vol, dd = T2[k]
    vals = [NAMES[k], es(sh, 3), es(cg) + " %", es(vol) + " %", es(dd) + " %"]
    for j, v in enumerate(vals):
        c = tb.cell(i, j)
        c.text = v
        c.fill.solid()
        c.fill.fore_color.rgb = LILAC if k == "E2A_A2" else (WHITE if i % 2 else LIGHT)
for i in range(len(srt) + 1):
    for j in range(5):
        para = tb.cell(i, j).text_frame.paragraphs[0]
        para.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER
        for r in para.runs:
            r.font.size = Pt(14)
            r.font.name = BODY
            r.font.bold = i == 0 or srt[i - 1] == "E2A_A2" if i else True
            r.font.color.rgb = WHITE if i == 0 else TXT
notes(s, "Tabla completa por si el jurado pregunta por una estrategia en particular.")

s = new()
title(s, "Anexo B. Sharpe dentro y fuera de muestra",
      "Construcción (70 %, 2017–2023) frente a validación (30 %, dic 2023–2026)")
IS = {"BH": 0.800, "RSI": 0.531, "MACD": 0.986, "SMA": 1.154, "EMA": 1.117, "CCI": 0.214, "E2A_A1": -1.397, "E2A_A2": 0.762, "E2C": -0.027}
OOS = {"BH": 0.631, "RSI": -0.772, "MACD": 0.773, "SMA": 1.119, "EMA": 0.975, "CCI": 0.408, "E2A_A1": -1.660, "E2A_A2": 1.412, "E2C": -1.057}
ordb = ["E2A_A2", "SMA", "EMA", "MACD", "BH", "CCI", "RSI"]
cd = CategoryChartData()
cd.categories = [NAMES[k] for k in ordb]
cd.add_series("Dentro de muestra (70 %)", [IS[k] for k in ordb])
cd.add_series("Fuera de muestra (30 %)", [OOS[k] for k in ordb])
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(L - 0.1), Inches(1.6), Inches(W_CONTENT), Inches(4.85), cd)
ch = gf.chart
style_chart(ch, 13)
ch.has_legend = True
ch.legend.position = XL_LEGEND_POSITION.TOP
ch.legend.include_in_layout = False
ch.plots[0].gap_width = 60
ch.plots[0].overlap = -10
for se, c in zip(ch.series, [GREY, PURPLE]):
    se.format.fill.solid(); se.format.fill.fore_color.rgb = c
    se.invert_if_negative = False
quiet_axis(ch.value_axis, '0.0', -1, 1.6, 0.5)
ch.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.LOW
source(s, "Fuente: repositorio del proyecto; no incluido en las tablas del informe")
notes(s, "Respaldo para la pregunta de sobreajuste: E2-A A2 es la única estrategia que mejora fuera de muestra (0,762 a 1,412) y su caída máxima en ese tramo fue −8,82 %. SMA se mantiene estable (1,154 a 1,119). RSI se vuelve negativo.")

# ------------------------------------------------------------------ barras negativas con su color
for sl in prs.slides:
    for shp in sl.shapes:
        if shp.has_chart:
            for bp in shp.chart._chartSpace.iter(qn("a:bodyPr")):
                if bp.getparent().tag == qn("c:rich") and bp.getparent().getparent().getparent().tag == qn("c:dLbl"):
                    bp.set("wrap", "none")
            for dpt in shp.chart._chartSpace.iter(qn("c:dPt")):
                if dpt.find(qn("c:invertIfNegative")) is None:
                    e = etree.SubElement(dpt, qn("c:invertIfNegative"))
                    e.set("val", "0")
                    dpt.remove(e)
                    dpt.insert(1, e)

# ------------------------------------------------------------------ quitar diapositivas de la plantilla
sldIdLst = prs.slides._sldIdLst
for sld in list(sldIdLst)[: len(tpl_slides)]:
    prs.part.drop_rel(sld.get(qn("r:id")))
    sldIdLst.remove(sld)
prs.save(OUT)
print("OK", OUT, len(prs.slides), "diapositivas")
