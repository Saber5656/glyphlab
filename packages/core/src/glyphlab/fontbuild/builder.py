"""Assemble reproducible TrueType and WOFF2 fonts from resolved outlines.

Outputs must pass the QA gate before being served as downloadable artifacts.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import newTable
from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

from glyphlab.charset.model import CharsetSpec
from glyphlab.errors import GlyphlabError
from glyphlab.fontbuild.naming import glyph_name, name_table
from glyphlab.model import GlyphOutline
from glyphlab.project.config import ProjectConfig


@dataclass(frozen=True)
class BuildResult:
    ttf_path: Path
    woff2_path: Path
    glyph_count: int
    missing: list[str]


def build_font(
    project: ProjectConfig,
    glyphs: dict[int, tuple[GlyphOutline, int]],
    charset: CharsetSpec,
    out_dir: Path,
) -> BuildResult:
    """Build tables once; selection and SVG parsing belong to the caller."""
    encoded = {char.codepoint for char in charset.chars}
    if set(glyphs) - encoded:
        raise GlyphlabError("E_VALIDATION", "Glyphs outside the project charset")
    stamp = int(os.environ.get("SOURCE_DATE_EPOCH", str(int(time.time()))))
    names = {cp: glyph_name(cp) for cp in encoded if cp in glyphs or cp in (32, 0x3000)}
    order = [".notdef", *(names[cp] for cp in sorted(names))]
    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap(names)
    # FontBuilder only adds format 12 automatically for supplementary codepoints.
    if not any(table.format == 12 for table in builder.font["cmap"].tables):
        table = CmapSubtable.newSubtable(12)
        table.platformID, table.platEncID, table.language = 3, 10, 0
        table.cmap = dict(names)
        builder.font["cmap"].tables.append(table)
    pen = TTGlyphPen(None)
    for points in (
        [(100, -120), (100, 780), (500, 780), (500, -120)],
        [(150, -70), (450, -70), (450, 730), (150, 730)],
    ):
        pen.moveTo(points[0])
        for point in points[1:]:
            pen.lineTo(point)
        pen.closePath()
    outlines = {".notdef": pen.glyph()}
    metrics = {".notdef": (600, 100)}
    for cp, name in names.items():
        pen = TTGlyphPen(None)
        if cp in (32, 0x3000):
            advance = 500 if cp == 32 else 1000
        else:
            outline, advance = glyphs[cp]
            curve_pen = Cu2QuPen(pen, max_err=1.0, reverse_direction=True)
            for contour in outline.contours:
                if not contour.segments:
                    continue
                start = contour.segments[0].p1
                curve_pen.moveTo((start.x, start.y))
                for seg in contour.segments:
                    curve_pen.curveTo(
                        (seg.c1.x, seg.c1.y), (seg.c2.x, seg.c2.y), (seg.p2.x, seg.p2.y)
                    )
                curve_pen.closePath()
        glyph = pen.glyph()
        outlines[name] = glyph
        metrics[name] = (
            advance,
            min((p[0] for p in glyph.coordinates), default=0) if glyph.numberOfContours else 0,
        )
    builder.setupGlyf(outlines)
    builder.setupHorizontalMetrics(metrics)
    builder.setupHorizontalHeader(ascent=880, descent=-120, lineGap=0)
    settings = project.project
    builder.setupNameTable(
        name_table(settings.family_name, settings.version, datetime.fromtimestamp(stamp, UTC).year),
        mac=False,
    )
    codepages = 1 | (1 << 17 if any(c.script_class != "latin" for c in charset.chars) else 0)
    # Windows clipping bounds include all ink; line-layout metrics remain fixed.
    ink_top = max((g.yMax for g in outlines.values() if g.numberOfContours), default=880)
    ink_bottom = min((g.yMin for g in outlines.values() if g.numberOfContours), default=-120)
    builder.setupOS2(
        sTypoAscender=880,
        sTypoDescender=-120,
        sTypoLineGap=0,
        usWinAscent=max(880, ink_top),
        usWinDescent=max(120, -ink_bottom),
        fsType=0,
        ulCodePageRange1=codepages,
        ulCodePageRange2=0,
        fsSelection=0x40,
        sxHeight=500,
        sCapHeight=700,
    )
    builder.setupPost(keepGlyphNames=True)
    builder.setupMaxp()
    builder.setupHead(
        flags=0b11,
        lowestRecPPEM=7,
        created=stamp + 2082844800,
        modified=stamp + 2082844800,
        fontRevision=float(settings.version),
    )
    gasp = newTable("gasp")
    gasp.gaspRange = {0xFFFF: 0b1111}
    builder.font["gasp"] = gasp
    builder.font.recalcTimestamp = False
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"{settings.family_name}-v{settings.version}"
    ttf, woff2 = out_dir / f"{prefix}.ttf", out_dir / f"{prefix}.woff2"
    builder.save(ttf)
    builder.font.flavor = "woff2"
    builder.save(woff2)
    missing = [
        f"U+{c.codepoint:04X}" for c in charset.chars if c.drawn and c.codepoint not in glyphs
    ]
    return BuildResult(ttf, woff2, len(order), missing)
