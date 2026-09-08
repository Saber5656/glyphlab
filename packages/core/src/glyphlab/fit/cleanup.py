"""Nonzero path union and sub-visible contour cleanup."""

import math

import pathops

from glyphlab.model import Contour, GlyphOutline, GlyphWarning
from glyphlab.vectorize.geometry import ContourPen, draw_contours


def signed_area(contour: Contour) -> float:
    points: list[tuple[float, float]] = []

    def flatten(
        a: tuple[float, ...],
        b: tuple[float, ...],
        c: tuple[float, ...],
        d: tuple[float, ...],
    ) -> None:
        # De Casteljau subdivision with a 0.5-unit flatness bound.
        chord = math.hypot(d[0] - a[0], d[1] - a[1])
        if chord:
            dist = max(
                abs((d[0] - a[0]) * (p[1] - a[1]) - (d[1] - a[1]) * (p[0] - a[0])) / chord
                for p in (b, c)
            )
        else:
            dist = max(math.dist(a, b), math.dist(a, c))
        if dist <= 0.5:
            points.append((d[0], d[1]))
            return
        ab = tuple((x + y) / 2 for x, y in zip(a, b, strict=True))
        bc = tuple((x + y) / 2 for x, y in zip(b, c, strict=True))
        cd = tuple((x + y) / 2 for x, y in zip(c, d, strict=True))
        abc = tuple((x + y) / 2 for x, y in zip(ab, bc, strict=True))
        bcd = tuple((x + y) / 2 for x, y in zip(bc, cd, strict=True))
        mid = tuple((x + y) / 2 for x, y in zip(abc, bcd, strict=True))
        flatten(a, ab, abc, mid)
        flatten(mid, bcd, cd, d)

    for s in contour.segments:
        if not points:
            points.append((s.p1.x, s.p1.y))
        flatten((s.p1.x, s.p1.y), (s.c1.x, s.c1.y), (s.c2.x, s.c2.y), (s.p2.x, s.p2.y))
    return (
        sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(points, points[1:] + points[:1], strict=True))
        / 2
    )


def clean_outline(
    contours: list[Contour], *, min_contour_area: float
) -> tuple[GlyphOutline, list[GlyphWarning]]:
    path = pathops.Path()
    draw_contours(contours, path.getPen())
    simplified = pathops.simplify(path, fix_winding=True, keep_starting_points=True)
    pen = ContourPen()
    simplified.draw(pen)
    kept = [c for c in pen.contours if abs(signed_area(c)) >= min_contour_area]
    warnings = [GlyphWarning.TINY_CONTOURS_REMOVED] if len(kept) != len(pen.contours) else []
    return GlyphOutline(tuple(kept)), warnings
