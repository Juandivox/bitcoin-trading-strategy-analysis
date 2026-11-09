r"""
scripts/compile_avances_pdf.py

Convierte C:\Users\jugev\Downloads\avances.md a un PDF academico estructurado
en el Escritorio utilizando la misma infraestructura de ReportLab que scripts/md_to_pdf_v2.py.
"""
from __future__ import annotations
import re
import os
import base64
from pathlib import Path
from datetime import date

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph,
                                Spacer, Table, TableStyle, Image, PageBreak,
                                KeepTogether, HRFlowable)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(r"E:\bitcoin-trading-research")
SRC = Path(r"C:\Users\jugev\Downloads\avances.md")
OUT = Path(r"C:\Users\jugev\Desktop") / "Avances_Proyecto_Tesis_BTC.pdf"
FONTS = Path(r"C:\Windows\Fonts")

pdfmetrics.registerFont(TTFont("Arial", FONTS / "arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-B", FONTS / "arialbd.ttf"))
pdfmetrics.registerFont(TTFont("Arial-I", FONTS / "ariali.ttf"))
pdfmetrics.registerFont(TTFont("Arial-BI", FONTS / "arialbi.ttf"))
pdfmetrics.registerFont(TTFont("Consola", FONTS / "consola.ttf"))

SANITIZE = {"\u2213": "+/-", "\u200b": "", "\xa0": " "}
PAGE_W, PAGE_H = A4
ML, MR, MT, MB = 20 * mm, 20 * mm, 18 * mm, 18 * mm
USABLE = PAGE_W - ML - MR

stTitle = ParagraphStyle("Title", fontName="Arial-B", fontSize=16, leading=20,
                         alignment=TA_CENTER, textColor=colors.HexColor("#0b2c4d"))
stCoverSub = ParagraphStyle("CoverSub", fontName="Arial-B", fontSize=11, leading=15, alignment=TA_CENTER)
stCoverMeta = ParagraphStyle("CoverMeta", fontName="Arial", fontSize=9, leading=13,
                             alignment=TA_CENTER, textColor=colors.HexColor("#444444"))
stH1 = ParagraphStyle("H1", fontName="Arial-B", fontSize=13, leading=17,
                      textColor=colors.HexColor("#0b2c4d"), spaceBefore=12, spaceAfter=5)
stH2 = ParagraphStyle("H2", fontName="Arial-B", fontSize=11, leading=14,
                      textColor=colors.HexColor("#134a7c"), spaceBefore=10, spaceAfter=4)
stH3 = ParagraphStyle("H3", fontName="Arial-B", fontSize=10, leading=13, spaceBefore=8, spaceAfter=3)
stBody = ParagraphStyle("Body", fontName="Arial", fontSize=9, leading=13, alignment=TA_JUSTIFY, spaceAfter=4)
stBullet = ParagraphStyle("Bullet", parent=stBody, leftIndent=12, bulletIndent=4, spaceAfter=2)
stCaption = ParagraphStyle("Caption", fontName="Arial-I", fontSize=8, leading=10,
                           alignment=TA_CENTER, textColor=colors.HexColor("#333333"), spaceAfter=6)
stQuote = ParagraphStyle("Quote", fontName="Arial-I", fontSize=8.5, leading=12,
                         textColor=colors.HexColor("#333333"), leftIndent=10, spaceAfter=5)
stCode = ParagraphStyle("Code", fontName="Consola", fontSize=7.5, leading=10, spaceAfter=4)
stCell = ParagraphStyle("Cell", fontName="Arial", fontSize=7.5, leading=9.5, alignment=TA_CENTER)
stCellH = ParagraphStyle("CellH", fontName="Arial-B", fontSize=7.5, leading=9.5, alignment=TA_CENTER)


def clean(t: str) -> str:
    for a, b in SANITIZE.items():
        t = t.replace(a, b)
    return t.strip()


def inline(t: str) -> str:
    t = clean(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"\*(.+?)\*", r"<i>\1</i>", t)
    t = re.sub(r"`([^`]+)`", r'<font face="Consola">\1</font>', t)
    return t


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Arial", 8)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawCentredString(PAGE_W / 2, 10 * mm, f"Página {doc.page}")
    canvas.restoreState()


def build_table(lines: list[str]):
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines]
    header = rows[0]
    body = [r for r in rows[1:] if not all(re.fullmatch(r":?-{2,}:?", c or "--") for c in r)]
    n = len(header)
    wide = n >= 6
    fs = 6.5 if wide else 7.5
    cs = ParagraphStyle("c", parent=stCell, fontSize=fs, leading=fs + 2)
    ch = ParagraphStyle("ch", parent=stCellH, fontSize=fs, leading=fs + 2, textColor=colors.white)
    data = [[Paragraph(inline(c), ch) for c in header]]
    for r in body:
        r = (r + [""] * n)[:n]
        data.append([Paragraph(inline(c), cs) for c in r])
    
    if n == 3: # Tabla de objetivos
        col_widths = [USABLE * 0.45, USABLE * 0.15, USABLE * 0.40]
    elif n == 5: # Tablas de backtest
        col_widths = [USABLE * 0.32, USABLE * 0.17, USABLE * 0.20, USABLE * 0.15, USABLE * 0.16]
    elif n == 4: # Tabla comparativa E2-A
        col_widths = [USABLE * 0.34, USABLE * 0.22, USABLE * 0.22, USABLE * 0.22]
    else:
        col_widths = [USABLE / n] * n

    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b2c4d")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    return tbl, len(body)


def parse(md: str, img_path: Path | None):
    # Ignorar la referencia final de base64
    lines = [ln for ln in md.splitlines() if not ln.startswith("[image1]:")]
    story, buf, i = [], [], 0

    def flush_para():
        if buf:
            story.append(Paragraph(inline(" ".join(buf)), stBody))
            buf.clear()

    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if not s:
            flush_para()
            i += 1
            continue

        # Header metadata block
        if i == 0 and s.startswith("**Analizar el comportamiento"):
            story.append(Paragraph(inline(s), stTitle))
            story.append(Spacer(1, 4 * mm))
            i += 1
            continue

        if s.startswith("|"):
            flush_para()
            tbl_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                tbl_lines.append(lines[i])
                i += 1
            tbl, nrows = build_table(tbl_lines)
            if (nrows <= 8 and story and isinstance(story[-1], Paragraph)
                    and ("Tabla" in story[-1].text or "Cumplimiento" in story[-1].text)):
                title_para = story.pop()
                story.append(KeepTogether([title_para, Spacer(1, 2 * mm), tbl]))
            else:
                story.append(Spacer(1, 2 * mm))
                story.append(tbl)
            story.append(Spacer(1, 3 * mm))
            continue

        if "![" in s and "image1" in s:
            flush_para()
            if img_path and img_path.exists():
                img = Image(str(img_path))
                img._restrictSize(USABLE * 0.90, 85 * mm)
                img.hAlign = "CENTER"
                story.append(Spacer(1, 3 * mm))
                story.append(img)
                story.append(Spacer(1, 1 * mm))
            i += 1
            continue

        if s.startswith("### "):
            flush_para()
            story.append(Paragraph(inline(s[4:]), stH3))
            i += 1
            continue
        if s.startswith("## "):
            flush_para()
            story.append(Paragraph(inline(s[3:]), stH2))
            i += 1
            continue
        if s.startswith("# "):
            flush_para()
            story.append(Paragraph(inline(s[2:]), stH1))
            i += 1
            continue
        if s.startswith("**") and s.endswith("**") and len(s) < 120 and ("Tabla" in s or "Gráfico" in s or "Grafico" in s or "DESARROLLO" in s):
            flush_para()
            story.append(Paragraph(inline(s), stH2))
            i += 1
            continue
        if s.startswith("**") and s.endswith("**") and len(s) > 100:
            flush_para()
            story.append(Paragraph(inline(s), stH2))
            i += 1
            continue

        if re.match(r"^(\d+[.)]|[-*·])\s+", s):
            flush_para()
            items = []
            while i < len(lines) and re.match(r"^(\d+[.)]|[-*·])\s+", lines[i].strip()):
                clean_it = re.sub(r"^(\d+[.)]|[-*·])\s+", "", lines[i].strip())
                items.append(clean_it)
                i += 1
            for it in items:
                story.append(Paragraph(inline(it), stBullet, bulletText="\u2022"))
            continue

        buf.append(s)
        i += 1

    flush_para()
    return story


def main():
    md = SRC.read_text(encoding="utf-8")
    
    # Extraer imagen base64 si existe
    img_path = ROOT / "temp_avances_img.png"
    m = re.search(r'\[image1\]:\s*<data:image/png;base64,([^>]+)>', md)
    if m:
        b = base64.b64decode(m.group(1))
        with open(img_path, "wb") as f:
            f.write(b)
    elif (ROOT / "docs" / "tesis_resultados_v2" / "figs" / "v2_fig12_barras_sharpe_ISOOS.png").exists():
        img_path = ROOT / "docs" / "tesis_resultados_v2" / "figs" / "v2_fig12_barras_sharpe_ISOOS.png"
    else:
        img_path = None

    story = parse(md, img_path)

    doc = BaseDocTemplate(str(OUT), pagesize=A4,
                          leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
                          title="Avances de Tesis - Trading Bitcoin", author="UNAB")
    frame = Frame(ML, MB, USABLE, PAGE_H - MT - MB, id="main")
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=footer)])
    doc.build(story)

    if img_path and img_path.name == "temp_avances_img.png" and img_path.exists():
        try:
            os.remove(img_path)
        except:
            pass

    size_kb = OUT.stat().st_size / 1024
    print(f"[OK] PDF generado con exito: {OUT} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
