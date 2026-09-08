"""Pen adapters for cubic-only closed domain contours."""

from typing import Any

from fontTools.pens.basePen import BasePen

from glyphlab.model import Contour, CubicSegment, Point


def line_segment(a: Point, b: Point) -> CubicSegment:
    return CubicSegment(
        a,
        Point(a.x + (b.x - a.x) / 3, a.y + (b.y - a.y) / 3),
        Point(a.x + 2 * (b.x - a.x) / 3, a.y + 2 * (b.y - a.y) / 3),
        b,
    )


class ContourPen(BasePen):  # type: ignore[misc]
    def __init__(self) -> None:
        super().__init__(None)
        self.contours: list[Contour] = []
        self.segments: list[CubicSegment] = []
        self.start = Point(0, 0)
        self.current = Point(0, 0)

    def _moveTo(self, p: tuple[float, float]) -> None:
        self.start = self.current = Point(*p)
        self.segments = []

    def _lineTo(self, p: tuple[float, float]) -> None:
        target = Point(*p)
        self.segments.append(line_segment(self.current, target))
        self.current = target

    def _curveToOne(
        self, c1: tuple[float, float], c2: tuple[float, float], p: tuple[float, float]
    ) -> None:
        target = Point(*p)
        self.segments.append(CubicSegment(self.current, Point(*c1), Point(*c2), target))
        self.current = target

    def _closePath(self) -> None:
        if self.current != self.start:
            self._lineTo((self.start.x, self.start.y))
        if self.segments:
            self.contours.append(Contour(tuple(self.segments)))
        self.segments = []

    def _endPath(self) -> None:
        self._closePath()


def draw_contours(contours: list[Contour] | tuple[Contour, ...], pen: Any) -> None:
    for contour in contours:
        if not contour.segments:
            continue
        p = contour.segments[0].p1
        pen.moveTo((p.x, p.y))
        for s in contour.segments:
            pen.curveTo((s.c1.x, s.c1.y), (s.c2.x, s.c2.y), (s.p2.x, s.p2.y))
        pen.closePath()
