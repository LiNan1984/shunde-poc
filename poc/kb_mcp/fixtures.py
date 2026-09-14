# -*- coding: utf-8 -*-
"""Deterministic small PDFs for knowledge-base tests (not the bank zip)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    Image as RLImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

TOKENS = {
    "alpha": "ALPHAKEY",
    "beta": "BETAKEY",
    "gamma": "GAMMAKEY",
    "scan": "ZEBRASCANPAGE",
    "chart": "RATECHART",
    "mortgage_rate": "3.85",
    "biz_rate": "4.20",
    "missing": "MISSINGUNIQUETOKEN",
}

_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
)


def _cjk_style(size: int = 12) -> ParagraphStyle:
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    return ParagraphStyle(
        "kb-cjk",
        fontName="STSong-Light",
        fontSize=size,
        leading=size + 6,
    )


def _latin_font(size: int) -> ImageFont.ImageFont:
    for candidate in _FONT_CANDIDATES:
        path = Path(candidate)
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def write_native_text_pdf(path: Path) -> Path:
    """Three-page extractable PDF with chapters and unique tokens."""
    path.parent.mkdir(parents=True, exist_ok=True)
    style = _cjk_style()
    filler = "信贷审批需双人复核，落实尽职调查。" * 8
    story = [
        Paragraph("第一章 信贷政策", style),
        Paragraph(
            "本行对公信贷逾期90天认定标准"
            f"{TOKENS['alpha']}适用于所有对公贷款产品。"
            "利率定价遵循风险定价原则。" + filler,
            style,
        ),
        PageBreak(),
        Paragraph("第二章 风险管理", style),
        Paragraph(
            f"资本充足率不得低于{TOKENS['beta']}。"
            "风险管理委员会按季审议。" + filler,
            style,
        ),
        PageBreak(),
        Paragraph("第三章 总体结论", style),
        Paragraph(
            f"全年不良贷款率{TOKENS['gamma']}保持稳定。"
            "全行信贷政策与风险管理总体有效。" + filler,
            style,
        ),
    ]
    SimpleDocTemplate(str(path), pagesize=A4).build(story)
    return path


def write_scan_pdf(path: Path) -> Path:
    """Image-only PDF (native extract empty) with OCR-readable English."""
    path.parent.mkdir(parents=True, exist_ok=True)
    font = _latin_font(48)
    img = Image.new("RGB", (1600, 900), "white")
    draw = ImageDraw.Draw(img)
    draw.text(
        (60, 220),
        f"{TOKENS['scan']} OCR fixture text for page one",
        fill="black",
        font=font,
    )
    img.save(path, "PDF", resolution=150.0)
    return path


def write_table_image_pdf(path: Path) -> Path:
    """One page with a ruled table plus an embedded chart image."""
    path.parent.mkdir(parents=True, exist_ok=True)
    chart_path = path.with_name(path.stem + "_chart.png")
    font = _latin_font(36)
    chart = Image.new("RGB", (400, 200), "white")
    draw = ImageDraw.Draw(chart)
    draw.rectangle((12, 12, 388, 188), outline="black", width=3)
    draw.text((40, 80), TOKENS["chart"], fill="black", font=font)
    chart.save(chart_path)

    style = _cjk_style()
    data = [
        ["产品", "利率", "余额"],
        ["住房按揭", TOKENS["mortgage_rate"], "1200"],
        ["经营贷款", TOKENS["biz_rate"], "860"],
    ]
    tbl = Table(data, colWidths=[50 * mm, 40 * mm, 40 * mm])
    tbl.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                ("FONTSIZE", (0, 0), (-1, -1), 12),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    story = [
        Paragraph("第四章 产品定价", style),
        Spacer(1, 8),
        tbl,
        Spacer(1, 12),
        RLImage(str(chart_path), width=120 * mm, height=60 * mm),
    ]
    SimpleDocTemplate(str(path), pagesize=A4).build(story)
    return path


def write_chapter_carry_pdf(path: Path) -> Path:
    """Page 1 has 第一章; page 2 continues without a new 第X章 heading."""
    path.parent.mkdir(parents=True, exist_ok=True)
    style = _cjk_style()
    story = [
        Paragraph("第一章 信贷政策", style),
        Paragraph(f"本章开篇条款{TOKENS['alpha']}。", style),
        PageBreak(),
        Paragraph(f"本章后续条款CARRYTOKEN不含新的章节标题。{TOKENS['beta']}", style),
    ]
    SimpleDocTemplate(str(path), pagesize=A4).build(story)
    return path


def write_overlap_pdf(path: Path) -> Path:
    """Long single page so a unique token sits in the chunk-overlap region."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    prefix = "甲" * 320
    suffix = "乙" * 320
    body = prefix + TOKENS["missing"] + suffix
    canvas = Canvas(str(path), pagesize=A4)
    canvas.setFont("STSong-Light", 8)
    y = 800
    width = 80
    for i in range(0, len(body), width):
        canvas.drawString(40, y, body[i : i + width])
        y -= 10
        if y < 40:
            canvas.showPage()
            canvas.setFont("STSong-Light", 8)
            y = 800
    canvas.save()
    return path
