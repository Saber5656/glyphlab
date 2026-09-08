"""True-scale deterministic printable templates (reference labels use CID fonts)."""

import unicodedata
from io import BytesIO
from pathlib import Path

import cv2
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen.canvas import Canvas

from glyphlab.charset import CharsetSpec

from .layout import TemplateLayout, guide_geometry

MARKER_INK_MM = 10.5
MARKER_QUIET_MM = 1.75


def sanitize_project_name(name: str) -> str:
    return "".join(c for c in name if unicodedata.category(c) != "Cc")[:64]


def render_pdf(
    path: Path,
    layout: TemplateLayout,
    charset: CharsetSpec,
    template_id: str,
    project_name: str,
) -> None:
    pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
    canvas = Canvas(str(path), pagesize=A4, invariant=1, pageCompression=1)
    canvas.setTitle("glyphlab template")
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    chars = {c.codepoint: c for c in charset.chars}

    def line(x0: float, y0: float, x1: float, y1: float) -> None:
        canvas.line(x0 * mm, (297 - y0) * mm, x1 * mm, (297 - y1) * mm)

    def text(x: float, y: float, value: str, size: int = 9, font: str = "Helvetica") -> None:
        canvas.setFont(font, size)
        canvas.drawString(x * mm, (297 - y) * mm, value)

    for page in layout.pages:
        canvas.setFillGray(0)
        text(12, 15, sanitize_project_name(project_name), 10, "HeiseiKakuGo-W5")
        text(
            12,
            20,
            f"{charset.charset_id}@{charset.version} | "
            f"{page.index + 1}/{layout.page_count} | {template_id[:8]}",
            8,
        )
        text(
            12,
            26,
            "太めのペンで、枠内の薄いガイドに合わせて書いてください。印刷は必ず100%（実際のサイズ）で。",
            7,
            "HeiseiKakuGo-W5",
        )
        canvas.setStrokeGray(0)
        canvas.setLineWidth(0.25)
        line(145, 31, 195, 31)
        for x in range(145, 196, 10):
            line(x, 30, x, 32)
        text(169, 29, "50mm", 6)
        for marker_id, rect in zip(page.aruco_ids, page.marker_rects_mm(), strict=True):
            bitmap = cv2.aruco.generateImageMarker(dictionary, marker_id, 280)
            stream = BytesIO()
            Image.fromarray(bitmap).save(stream, format="PNG")
            x0, y0, x1, y1 = rect
            # ArUco detects black ink corners, not the quiet-zone rectangle.
            quiet = (x1 - x0) * MARKER_QUIET_MM / 14
            ink = (x1 - x0) * MARKER_INK_MM / 14
            canvas.drawImage(
                ImageReader(stream),
                (x0 + quiet) * mm,
                (297 - y1 + quiet) * mm,
                ink * mm,
                ink * mm,
            )
        for cell in page.cells:
            x0, y0, x1, y1 = page.writing_box_mm(cell.row, cell.col)
            canvas.setStrokeGray(0.6)
            canvas.setLineWidth(0.3)
            canvas.setDash()
            canvas.rect(x0 * mm, (297 - y1) * mm, (x1 - x0) * mm, (y1 - y0) * mm)
            if cell.codepoint is None:
                continue
            char = chars[cell.codepoint]
            canvas.setFillGray(0.45)
            text(
                x0 + 1,
                y0 - 0.6,
                chr(cell.codepoint),
                12,
                "Helvetica" if cell.codepoint < 128 else "HeiseiKakuGo-W5",
            )
            text(x0 + 11, y0 - 0.7, f"U+{cell.codepoint:04X}", 6)
            guides = guide_geometry((x0, y0, x1, y1), char.script_class)
            canvas.setStrokeGray(0.8)
            canvas.setLineWidth(0.2 * mm)
            canvas.setDash(1.5 * mm, 1.5 * mm)
            if guides.baseline is not None:
                line(x0, guides.baseline, x1, guides.baseline)
                if guides.xheight is not None:
                    line(x0, guides.xheight, x1, guides.xheight)
            elif guides.square is not None:
                a, b, c, d = guides.square
                canvas.rect(a * mm, (297 - d) * mm, (c - a) * mm, (d - b) * mm)
        canvas.showPage()
    canvas.save()
