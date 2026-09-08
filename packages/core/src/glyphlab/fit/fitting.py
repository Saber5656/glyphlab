"""Guide-anchored uniform affine fitting into deterministic font units."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from fontTools.pens.boundsPen import BoundsPen

from glyphlab.charset import CharDef
from glyphlab.errors import GlyphlabError

if TYPE_CHECKING:
    from glyphlab.ingest.cells import CellGeometry
from glyphlab.model import (
    Contour,
    CubicSegment,
    Glyph,
    GlyphOutline,
    GlyphStatus,
    GlyphWarning,
    Point,
)
from glyphlab.vectorize.geometry import draw_contours

from .cleanup import clean_outline


def bounds(contours: list[Contour]) -> tuple[float, float, float, float]:
    pen = BoundsPen(None)
    draw_contours(contours, pen)
    return cast(tuple[float, float, float, float], pen.bounds or (0.0, 0.0, 0.0, 0.0))


def transform(contours: list[Contour], fn: Callable[[Point], Point]) -> list[Contour]:
    return [
        Contour(tuple(CubicSegment(fn(s.p1), fn(s.c1), fn(s.c2), fn(s.p2)) for s in c.segments))
        for c in contours
    ]


def fit_glyph(
    bitmap_contours: list[Contour],
    geom: CellGeometry,
    char: CharDef,
    cell_warnings: list[GlyphWarning],
) -> Glyph:
    guides = geom.guides
    latin = char.script_class == "latin"
    if latin:
        if guides.baseline is None or guides.xheight is None or guides.baseline <= guides.xheight:
            raise GlyphlabError("E_VALIDATION", "Latin guide geometry is invalid")
        scale = 460 / (guides.baseline - guides.xheight)
        bottom = guides.baseline
        offset = 0
    else:
        if guides.square is None or guides.square[3] <= guides.square[1]:
            raise GlyphlabError("E_VALIDATION", "Square guide geometry is invalid")
        _, top, _, bottom = guides.square
        scale = 1000 / (bottom - top)
        offset = -120
    contours = transform(
        bitmap_contours, lambda p: Point(p.x * scale, (bottom - p.y) * scale + offset)
    )
    outline, cleanup_warnings = clean_outline(contours, min_contour_area=40)
    contours = list(outline.contours)
    x0, y0, x1, y1 = bounds(contours)
    anchor = 0 if latin else 380
    ratios = [1.0]
    if y0 < -250:
        ratios.append((-250 - anchor) / (y0 - anchor))
    if y1 > 1000:
        ratios.append((1000 - anchor) / (y1 - anchor))
    clamp = min(ratios)
    warnings = list(cell_warnings) + cleanup_warnings
    if clamp < 1:
        center = (x0 + x1) / 2
        contours = transform(
            contours,
            lambda p: Point(center + (p.x - center) * clamp, anchor + (p.y - anchor) * clamp),
        )
        warnings.append(GlyphWarning.OFF_GUIDE)
    x0, _, x1, _ = bounds(contours)
    dx = 60 - x0 if latin else 500 - (x0 + x1) / 2
    contours = transform(contours, lambda p: Point(round(p.x + dx), round(p.y)))
    advance = max(120, round(x1 - x0 + 120)) if latin else 1000
    return Glyph(
        codepoint=char.codepoint,
        status=GlyphStatus.AUTO,
        outline=GlyphOutline(tuple(contours)),
        advance=advance,
        warnings=warnings,
        source=None,
    )
