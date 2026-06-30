"""Render the project strategy plan (markdown) into a styled PDF.

Run:  python scripts/build_strategy_pdf.py
      (needs reportlab — `pip install reportlab` if missing; same dep as build_deploy_pdf.py)

Reads the approved plan markdown and writes The-Narrative-Strategy.pdf to the repo root.
A lightweight markdown subset is supported: # / ## / ### headings, **bold**, `code`,
fenced ``` code blocks, | pipe tables |, - bullets, > blockquotes, and --- rules.
"""
import os
import re
import html

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Preformatted, HRFlowable,
)

# Plan lives in the user's Claude plans dir; output goes into the repo folder.
PLAN = os.path.expanduser(r"~/.claude/plans/osnit-and-vlc-media-rustling-kahan.md")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "The-Narrative-Strategy.pdf")

INK = colors.HexColor("#1A1A1A")
CRIM = colors.HexColor("#C80028")
GREY = colors.HexColor("#6B6B6B")
LINE = colors.HexColor("#D8D4CC")
CODEBG = colors.HexColor("#F4F2EE")
HEADBG = colors.HexColor("#11201E")
ROWBG = colors.HexColor("#F7F5F1")

MARGIN = 0.8 * inch
PAGE_W, PAGE_H = letter
CONTENT_W = PAGE_W - 2 * MARGIN

ss = getSampleStyleSheet()


def style(name, **kw):
    kw.setdefault("parent", ss["Normal"])
    return ParagraphStyle(name, **kw)


TITLE = style("t", fontName="Helvetica-Bold", fontSize=22, textColor=colors.white, leading=26)
SUBT = style("s", fontName="Helvetica", fontSize=10.5, textColor=colors.HexColor("#C9C4BC"), leading=14)
H0 = style("h0", fontName="Helvetica-Bold", fontSize=16, textColor=CRIM, leading=20, spaceBefore=16, spaceAfter=6)
H1 = style("h1", fontName="Helvetica-Bold", fontSize=12.5, textColor=CRIM, leading=16, spaceBefore=12, spaceAfter=5)
H2 = style("h2", fontName="Helvetica-Bold", fontSize=10.5, textColor=INK, leading=14, spaceBefore=7, spaceAfter=3)
BODY = style("b", fontName="Helvetica", fontSize=9.5, textColor=INK, leading=14, spaceAfter=4)
BULLET = style("bl", parent=BODY, leftIndent=14, bulletIndent=3, spaceAfter=2)
QUOTE = style("q", fontName="Helvetica-Oblique", fontSize=9, textColor=GREY, leading=13,
              leftIndent=10, spaceAfter=4)
SMALL = style("sm", fontName="Helvetica", fontSize=8, textColor=GREY, leading=11)
CODEST = style("c", fontName="Courier", fontSize=8.2, textColor=colors.HexColor("#10302B"), leading=11.5)
CELL = style("cell", fontName="Helvetica", fontSize=8.3, textColor=INK, leading=11.5)
CELLB = style("cellb", parent=CELL, fontName="Helvetica-Bold", textColor=colors.white)

# Core fonts lack many unicode glyphs — normalize to safe equivalents.
_UNI = {
    "→": " -> ", "⇒": " => ", "←": " <- ", "≥": ">=", "≤": "<=",
    "—": " - ", "–": "-", "•": "*", "·": " - ", "…": "...",
    "✅": "[x] ", "⚠": "(!) ", "⏭": ">> ", "“": '"', "”": '"',
    "‘": "'", "’": "'", "€": "EUR", "‑": "-",
}


def _norm(t):
    for k, v in _UNI.items():
        t = t.replace(k, v)
    return t


def inline(text):
    text = _norm(text)
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", lambda m: '<font face="Courier" size="8.5">%s</font>' % m.group(1), text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    return text


def code_block(txt):
    p = Preformatted(_norm(txt.strip("\n")), CODEST)
    t = Table([[p]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODEBG),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def make_table(rows):
    data = [[Paragraph(inline(c), CELLB if r == 0 else CELL) for c in row] for r, row in enumerate(rows)]
    ncols = max(len(r) for r in data)
    w = CONTENT_W / ncols
    t = Table(data, colWidths=[w] * ncols, repeatRows=1)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (0, 0), (-1, 0), HEADBG),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ROWBG]),
    ]))
    return t


def parse(md):
    story = []
    lines = md.splitlines()
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        # fenced code
        if stripped.startswith("```"):
            buf = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            story.append(code_block("\n".join(buf)))
            continue

        # table (one or more lines starting with |)
        if stripped.startswith("|"):
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not re.match(r"^[:\-\s|]+$", "|".join(cells)):  # skip |---| separator
                    rows.append(cells)
                i += 1
            if rows:
                story.append(make_table(rows))
                story.append(Spacer(1, 4))
            continue

        if not stripped:
            story.append(Spacer(1, 4))
            i += 1
            continue

        if stripped.startswith("### "):
            story.append(Paragraph(inline(stripped[4:]), H2))
        elif stripped.startswith("## "):
            story.append(Paragraph(inline(stripped[3:]), H1))
        elif stripped.startswith("# "):
            story.append(Paragraph(inline(stripped[2:]), H0))
        elif stripped.startswith(("---", "***", "___")) and len(set(stripped)) <= 2:
            story.append(Spacer(1, 2))
            story.append(HRFlowable(width="100%", color=LINE))
        elif stripped.startswith(">"):
            story.append(Paragraph(inline(stripped.lstrip("> ").rstrip()), QUOTE))
        elif re.match(r"^[-*]\s+", stripped):
            story.append(Paragraph("&bull;&nbsp;&nbsp;" + inline(re.sub(r"^[-*]\s+", "", stripped)), BULLET))
        elif re.match(r"^\d+\.\s+", stripped):
            num = re.match(r"^(\d+)\.", stripped).group(1)
            story.append(Paragraph("%s.&nbsp;&nbsp;" % num + inline(re.sub(r"^\d+\.\s+", "", stripped)), BULLET))
        else:
            story.append(Paragraph(inline(stripped), BODY))
        i += 1
    return story


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(GREY)
    canvas.drawString(MARGIN, 0.5 * inch, "The Narrative - Strategy & Roadmap (confidential)")
    canvas.drawRightString(PAGE_W - MARGIN, 0.5 * inch, "Page %d" % doc.page)
    canvas.setStrokeColor(LINE)
    canvas.line(MARGIN, 0.62 * inch, PAGE_W - MARGIN, 0.62 * inch)
    canvas.restoreState()


def main():
    with open(PLAN, encoding="utf-8") as f:
        md = f.read()

    band = Table([[Paragraph("THE NARRATIVE", TITLE)],
                  [Paragraph("Strategy, Product &amp; Execution Plan", SUBT)],
                  [Paragraph("Confidential &middot; generated from the approved plan", SUBT)]],
                 colWidths=[CONTENT_W])
    band.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HEADBG),
        ("LEFTPADDING", (0, 0), (-1, -1), 18), ("RIGHTPADDING", (0, 0), (-1, -1), 18),
        ("TOPPADDING", (0, 0), (0, 0), 18), ("BOTTOMPADDING", (0, -1), (-1, -1), 16),
        ("TOPPADDING", (0, 1), (-1, -1), 2),
    ]))

    story = [band, Spacer(1, 12)] + parse(md)

    doc = SimpleDocTemplate(OUT, pagesize=letter, leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=0.7 * inch, bottomMargin=0.8 * inch,
                            title="The Narrative - Strategy & Roadmap", author="The Narrative")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print("wrote", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
