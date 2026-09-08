"""Measure the final TrueType contour, including integer coordinate rounding."""

import math

from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
from glyphlab.fontbuild.builder import build_font
from glyphlab.model import Contour, CubicSegment, GlyphOutline, Point


class SamplePen(BasePen):
    def __init__(self):
        super().__init__(None)
        self.samples = []

    def _moveTo(self, point):
        self.samples.append(point)

    def _lineTo(self, point):
        start = self._getCurrentPoint()
        for i in range(101):
            t = i / 100
            self.samples.append(
                ((1 - t) * start[0] + t * point[0], (1 - t) * start[1] + t * point[1])
            )

    def _qCurveToOne(self, control, end):
        start = self._getCurrentPoint()
        for i in range(501):
            t = i / 500
            self.samples.append(
                tuple(
                    (1 - t) ** 2 * start[j] + 2 * (1 - t) * t * control[j] + t * t * end[j]
                    for j in (0, 1)
                )
            )


def test_cubic_conversion_deviation(golden_inputs, tmp_path):
    config, glyphs, charset = golden_inputs
    a, b, c, d = Point(100, 0), Point(100, 700), Point(700, 700), Point(700, 0)
    glyphs[65] = (
        GlyphOutline((Contour((CubicSegment(a, b, c, d), CubicSegment(d, d, a, a))),)),
        800,
    )
    result = build_font(config, glyphs, charset, tmp_path)
    with TTFont(result.ttf_path) as font:
        pen = SamplePen()
        font["glyf"][font.getBestCmap()[65]].draw(pen, font["glyf"])
    deviations = []
    for i in range(201):
        t = i / 200
        x = (1 - t) ** 3 * a.x + 3 * (1 - t) ** 2 * t * b.x + 3 * (1 - t) * t * t * c.x + t**3 * d.x
        y = (1 - t) ** 3 * a.y + 3 * (1 - t) ** 2 * t * b.y + 3 * (1 - t) * t * t * c.y + t**3 * d.y
        deviations.append(min(math.hypot(px - x, py - y) for px, py in pen.samples))
    assert max(deviations) <= 1.5
