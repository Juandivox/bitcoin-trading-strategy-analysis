"""Convierte docs/tesis_resultados/CAPITULO_RESULTADOS.md a PDF academico en el Escritorio."""
from __future__ import annotations
import re
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
SRC = ROOT / "docs" / "tesis_resultados" / "CAPITULO_RESULTADOS.md"
FIGDIR = ROOT / "docs" / "tesis_resultados"
OUT = Path(r"C:\Users\jugev\Desktop") / "CAPITULO_RESULTADOS_BTC_Trading.pdf"
FONTS = Path(r"C:\Windows\Fonts")

pdfmetrics.registerFont(TTFont("Arial", FONTS / "arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-B", FONTS / "arialbd.ttf"))
pdfmetrics.registerFont(TTFont("Arial-I", FONTS / "ariali.ttf"))
pdfmetrics.registerFont(TTFont("Arial-BI", FONTS / "arialbi.ttf"))
pdfmetrics.registerFont(TTFont("Consola", FONTS / "consola.ttf"))

SANITIZE = {"\u2213": "+/-", "\u200b": "", "\xa0": " "}
PAGE_W, PAGE_H = A4
ML, MR, MT, MB = 22 * mm, 22 * mm, 20 * mm, 20 * mm
USABLE = PAGE_W - ML - MR

stTitle = ParagraphStyle("Title", fontName="Arial-B", fontSize=20, leading=25,
                         alignment=TA_CENTER, textColor=colors.HexColor("#0b2c4d"))
stCoverSub = ParagraphStyle("CoverSub", fontName="Arial", fontSize=11, leading=15, alignment=TA_CENTER)
stCoverMeta = ParagraphStyle("CoverMeta", fontName="Arial-I", fontSize=9.5, leading=13,
                             alignment=TA_CENTER, textColor=colors.HexColor("#444444"))
stH1 = ParagraphStyle("H1", fontName="Arial-B", fontSize=14, leading=18,
                      textColor=colors.HexColor("#0b2c4d"), spaceBefore=14, spaceAfter=6)
stH2 = ParagraphStyle("H2", fontName="Arial-B", fontSize=11.5, leading=15,
                      textColor=colors.HexColor("#134a7c"), spaceBefore=10, spaceAfter=4)
stH3 = ParagraphStyle("H3", fontName="Arial-B", fontSize=10.5, leading=14, spaceBefore=8, spaceAfter=3)
stBody = ParagraphStyle("Body", fontName="Arial", fontSize=10, leading=14.5, alignment=TA_JUSTIFY, spaceAfter=4)
stBullet = ParagraphStyle("Bullet", parent=stBody, leftIndent=14, bulletIndent=4, spaceAfter=2)
stCaption = ParagraphStyle("Caption", fontName="Arial-I", fontSize=8.5, leading=11,
                           alignment=TA_CENTER, textColor=colors.HexColor("#333333"), spaceAfter=8)
stQuote = ParagraphStyle("Quote", fontName="Arial-I", fontSize=9.5, leading=13.5,
                         textColor=colors.HexColor("#333333"), leftIndent=12,
                         borderPadding=(6, 6, 6), spaceAfter=6)
stCode = ParagraphStyle("Code", fontName="Consola", fontSize=8, leading=11, spaceAfter=6)
stCell = ParagraphStyle("Cell", fontName="Arial", fontSize=7, leading=8.5, alignment=TA_CENTER)
stCellH = ParagraphStyle("CellH", fontName="Arial-B", fontSize=7, leading=8.5, alignment=TA_CENTER)


def clean(t: str) -> str:
    for a, b in SANITIZE.items():
        t = t.replace(a, b)
    return t.strip()


def inline(t: str) -> str:
    t = clean(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`([^`]+)`", r'<font face="Consola">\1</font>', t)
    return t


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Arial", 8)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawCentredString(PAGE_W / 2, 12 * mm, f"{doc.page}")
    canvas.restoreState()


def build_table(lines: list[str]):
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines]
    header, body = rows[0], [r for r in rows[1:] if not re.fullmatch(r"[\s:\-|]+", "|".join(r))]
    # drop markdown separator row if present
    body = [r for r in body if not all(re.fullmatch(r":?-{2,}:?", c or "--") for c in r)]
    n = len(header)
    wide = n >= 8
    fs = 6.5 if wide else 8
    cs = ParagraphStyle("c", parent=stCell, fontSize=fs, leading=fs + 1.5)
    ch = ParagraphStyle("ch", parent=stCellH, fontSize=fs, leading=fs + 1.5)
    data = [[Paragraph(inline(c), ch) for c in header]]
    for r in body:
        r = (r + [""] * n)[:n]
        data.append([Paragraph(inline(c), cs) for c in r])
    first = USABLE * (0.20 if wide else 0.28)
    rest = (USABLE - first) / (n - 1)
    tbl = Table(data, colWidths=[first] + [rest] * (n - 1), repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b2c4d")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#999999")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef3f8")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    return tbl


def parse(md: str):
    lines = md.splitlines()
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
        if s.startswith("```"):
            flush_para()
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            story.append(Spacer(1, 2))
            for cl in code:
                story.append(Paragraph(clean(cl).replace(" ", "&nbsp;"), stCode))
            story.append(Spacer(1, 4))
            continue
        if s.startswith("|"):
            flush_para()
            tbl_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                tbl_lines.append(lines[i])
                i += 1
            story.append(Spacer(1, 3))
            story.append(build_table(tbl_lines))
            story.append(Spacer(1, 5))
            continue
        m = re.match(r"!\[(.*?)\]\((.*?)\)", s)
        if m:
            flush_para()
            cap, rel = m.group(1), m.group(2)
            p = FIGDIR / rel
            img = Image(str(p))
            img._restrictSize(USABLE, 135 * mm)
            img.hAlign = "CENTER"
            story.append(Spacer(1, 4))
            story.append(img)
            story.append(Spacer(1, 2))
            story.append(Paragraph(f"<b>{inline(cap.split('.')[0] + '.')}</b> " +
                                   inline(".".join(cap.split(".")[1:]).strip()), stCaption))
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
        if s.startswith("&gt;") or s.startswith(">"):
            flush_para()
            q = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                q.append(lines[i].strip()[1:].strip())
                i += 1
            story.append(Paragraph(inline(" ".join(q)), stQuote))
            continue
        if re.match(r"^(\d+[.)]|[-*])\s+", s):
            flush_para()
            items = []
            while i < len(lines) and re.match(r"^(\d+[.)]|[-*])\s+", lines[i].strip()):
                items.append(re.sub(r"^(\d+[.)]|[-*])\s+", "", lines[i].strip()))
                i += 1
            for it in items:
                story.append(Paragraph(inline(it), stBullet, bulletText="\u2022"))
            continue
        if re.fullmatch(r"-{3,}", s):
            flush_para()
            story.append(Spacer(1, 2))
            story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#0b2c4d")))
            story.append(Spacer(1, 6))
            i += 1
            continue
        buf.append(s)
        i += 1
    flush_para()
    return story


def main():
    md = SRC.read_text(encoding="utf-8")
    # Portada con el H1 + lineas de autoria; el resto fluye normal
    story = parse(md)
    doc = BaseDocTemplate(str(OUT), pagesize=A4,
                          leftMargin=ML, rightMargin=MR, topMargin=MT, bottomMargin=MB,
                          title="Resultados — Trading BTC", author="UNAB Ing. Financiera")
    frame = Frame(ML, MB, USABLE, PAGE_H - MT - MB, id="main")
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=footer)])
    doc.build(story)
    print(f"[OK] {OUT}  {OUT.stat().st_size/1024/1024:.1f} MB")


if __name__ == "__main__":
    main()
